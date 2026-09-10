"""Move selectable POI markers onto verified TPN walking-trail graph nodes.

The natural feature coordinates are retained as ``feature_lat`` and
``feature_lng``.  Marker coordinates (``lat``/``lng``) are replaced with the
coordinates of a routing node that:

* is no farther than 20 m from the public TPN walking-trail geometry, and
* belongs to the largest connected component of ``cala_mapa.json``.

Non-peak POIs without a verified access point remain in ``graph_nodes.json``
with ``selectable: false``. Peaks are deliberately left unchanged for a later
audit.

This maintenance script requires Shapely and pyproj. Run it without
``--write`` to see a summary without modifying data.
"""

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

import numpy as np
from pyproj import Transformer
import shapely
from shapely.geometry import LineString
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree


BASE_DIR = Path(__file__).resolve().parents[1]
POI_FILE = BASE_DIR / "mapa" / "graph_nodes.json"
FULL_MAP_FILE = BASE_DIR / "mapa" / "cala_mapa.json"

TPN_TRAILS_URL = (
    "https://gis.tpn.pl/server/rest/services/"
    "Topografia___wektor_MIL1/MapServer/9"
)
TPN_TRAILS_QUERY_URL = f"{TPN_TRAILS_URL}/query"

DIRECT_ACCESS_DISTANCE_M = 30.0
ROUTING_NODE_TRAIL_DISTANCE_M = 20.0

# These are verified exceptions where the OSM point is the centre of a
# building/water polygon, while the public TPN layer provides a nearby walking
# approach. They are still capped by the distances below.
CURATED_EXCEPTIONS = {
    "way/171648212": {
        "name": "Smreczyński Staw",
        "max_distance_m": 60.0,
        "reason": "named TPN trail destination",
    },
    "way/581704894": {
        "name": "Żabie Oko",
        "max_distance_m": 100.0,
        "reason": "named TPN trail destination",
    },
    "way/241024507": {
        "name": "Schronisko PTTK na Hali Ornak",
        "max_distance_m": 60.0,
        "reason": "building centroid; trail reaches the shelter",
    },
    "way/303740443": {
        "name": "Schronisko PTTK na Polanie Chochołowskiej",
        "max_distance_m": 70.0,
        "reason": "building centroid; trail reaches the shelter",
    },
}

ACCESS_FIELDS = {
    "access_point_distance_to_official_trail_m",
    "access_point_elevation",
    "access_point_name",
    "access_point_routing_node_id",
    "distance_from_feature_to_access_point_m",
    "official_trail_color",
    "official_trail_section",
    "verification_note",
}


def fetch_json(url, attempts=3):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "HikeUp official-trail marker curator"},
    )
    last_error = None

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)
        except Exception as error:  # pragma: no cover - depends on remote GIS
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"Could not download the TPN trail layer: {last_error}")


def fetch_walking_trails():
    params = urllib.parse.urlencode(
        {
            "where": "1=1",
            "outFields": "OBJECTID,TYP,KOLOR_1,PKT_START,PKT_END",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        }
    )
    payload = fetch_json(f"{TPN_TRAILS_QUERY_URL}?{params}")
    features = payload.get("features", [])
    return [
        feature
        for feature in features
        if "pieszy" in (feature.get("attributes", {}).get("TYP") or "")
    ]


def build_union_find(nodes, edges):
    node_indexes = {node["id"]: index for index, node in enumerate(nodes)}
    parent = list(range(len(nodes)))
    sizes = [1] * len(nodes)

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first, second):
        first_root = find(first)
        second_root = find(second)
        if first_root == second_root:
            return
        if sizes[first_root] < sizes[second_root]:
            first_root, second_root = second_root, first_root
        parent[second_root] = first_root
        sizes[first_root] += sizes[second_root]

    for edge in edges:
        first = node_indexes.get(edge.get("from"))
        second = node_indexes.get(edge.get("to"))
        if first is not None and second is not None:
            union(first, second)

    roots = Counter(find(index) for index in range(len(nodes)))
    largest_root = roots.most_common(1)[0][0]
    return find, largest_root


def access_point_label(point):
    point_type = point.get("type")
    if point_type == "water":
        return "Punkt dojścia do stawu na znakowanym szlaku TPN"
    if point_type == "waterfall":
        return "Punkt dojścia do wodospadu na znakowanym szlaku TPN"
    if point_type in {"alpine_hut", "guest_house"}:
        return "Punkt dojścia do obiektu na znakowanym szlaku TPN"
    return "Punkt osiągalny znakowanym szlakiem TPN"


def source_coordinates(point):
    return (
        float(point.get("feature_lng", point["lng"])),
        float(point.get("feature_lat", point["lat"])),
    )


def clear_access_fields(point):
    for field in ACCESS_FIELDS:
        point.pop(field, None)


def curate_points(poi_data, full_map, trail_features):
    nodes = full_map["nodes"]
    edges = full_map["edges"]
    points = poi_data["nodes"]

    to_metric = Transformer.from_crs(4326, 32634, always_xy=True)

    trail_parts = []
    trail_attributes = []
    for feature in trail_features:
        attributes = feature.get("attributes", {})
        for path in feature.get("geometry", {}).get("paths", []):
            if len(path) < 2:
                continue
            trail_parts.append(
                transform(to_metric.transform, LineString(path))
            )
            trail_attributes.append(attributes)

    if not trail_parts:
        raise RuntimeError("The TPN response did not contain walking-trail geometry.")

    trail_union = unary_union(trail_parts)
    trail_tree = STRtree(trail_parts)

    find_component, largest_component = build_union_find(nodes, edges)
    node_x, node_y = to_metric.transform(
        [float(node["lng"]) for node in nodes],
        [float(node["lat"]) for node in nodes],
    )
    node_geometries = shapely.points(node_x, node_y)
    node_trail_distances = np.asarray(
        shapely.distance(node_geometries, trail_union)
    )
    eligible_node_indexes = np.asarray(
        [
            index
            for index in range(len(nodes))
            if find_component(index) == largest_component
            and node_trail_distances[index] <= ROUTING_NODE_TRAIL_DISTANCE_M
        ],
        dtype=int,
    )
    if not len(eligible_node_indexes):
        raise RuntimeError("No routing nodes match the official TPN trail layer.")

    routing_tree = STRtree(node_geometries[eligible_node_indexes])
    counters = Counter()

    for point in points:
        if point.get("type") == "peak":
            counters["peaks_unchanged"] += 1
            continue

        clear_access_fields(point)
        source_lng, source_lat = source_coordinates(point)
        point_geometry = shapely.Point(
            *to_metric.transform(source_lng, source_lat)
        )
        nearest_trail_index = int(trail_tree.nearest(point_geometry))
        nearest_trail = trail_parts[nearest_trail_index]
        trail_attributes_for_point = trail_attributes[nearest_trail_index]
        feature_trail_distance = float(point_geometry.distance(nearest_trail))

        point.setdefault(
            "original_distance_to_routing_node_m",
            point.get("distance_to_trail_m"),
        )
        point["feature_lat"] = source_lat
        point["feature_lng"] = source_lng
        point["feature_distance_to_official_trail_m"] = round(
            feature_trail_distance
        )
        point["verification_source"] = TPN_TRAILS_URL
        point["verified_at"] = date.today().isoformat()

        exception = CURATED_EXCEPTIONS.get(point.get("id"))
        directly_accessible = feature_trail_distance <= DIRECT_ACCESS_DISTANCE_M
        accepted_exception = bool(
            exception
            and point.get("name") == exception["name"]
            and feature_trail_distance <= exception["max_distance_m"]
        )

        if not directly_accessible and not accepted_exception:
            point["lat"] = source_lat
            point["lng"] = source_lng
            point["distance_to_trail_m"] = round(feature_trail_distance)
            point["selectable"] = False
            point["verification_status"] = "requires_manual_access_review"
            counters["hidden_pending_review"] += 1
            continue

        closest_position_on_trail = nearest_trail.interpolate(
            nearest_trail.project(point_geometry)
        )
        local_routing_index = int(routing_tree.nearest(closest_position_on_trail))
        routing_node_index = int(eligible_node_indexes[local_routing_index])
        routing_node = nodes[routing_node_index]
        routing_geometry = node_geometries[routing_node_index]
        distance_from_feature = float(point_geometry.distance(routing_geometry))
        marker_trail_distance = float(node_trail_distances[routing_node_index])

        point["lat"] = float(routing_node["lat"])
        point["lng"] = float(routing_node["lng"])
        point["nearest_routing_node_id"] = routing_node["id"]
        point["access_point_routing_node_id"] = routing_node["id"]
        point["distance_to_trail_m"] = round(marker_trail_distance)
        point["access_point_distance_to_official_trail_m"] = round(
            marker_trail_distance
        )
        point["distance_from_feature_to_access_point_m"] = round(
            distance_from_feature
        )
        point["access_point_elevation"] = routing_node.get("elevation")
        point["access_point_name"] = access_point_label(point)
        start = trail_attributes_for_point.get("PKT_START")
        end = trail_attributes_for_point.get("PKT_END")
        point["official_trail_section"] = " – ".join(
            value for value in (start, end) if value
        )
        point["official_trail_color"] = trail_attributes_for_point.get("KOLOR_1")
        point["selectable"] = True
        point["verification_status"] = "verified_official_trail_access"
        if accepted_exception:
            point["verification_note"] = exception["reason"]
            counters["curated_exceptions"] += 1
        else:
            point.pop("verification_note", None)
        counters["verified_access_points"] += 1

    poi_data["poi_access_metadata"] = {
        "source": TPN_TRAILS_URL,
        "verified_at": date.today().isoformat(),
        "direct_access_distance_m": DIRECT_ACCESS_DISTANCE_M,
        "routing_node_trail_distance_m": ROUTING_NODE_TRAIL_DISTANCE_M,
        "verified_non_peak_points": counters["verified_access_points"],
        "hidden_non_peak_points": counters["hidden_pending_review"],
        "peaks_unchanged": counters["peaks_unchanged"],
        "note": (
            "lat/lng of verified non-peak POIs identify the reachable routing "
            "marker; feature_lat/feature_lng retain the natural object position"
        ),
    }
    return counters


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="write curated coordinates and visibility flags to graph_nodes.json",
    )
    args = parser.parse_args()

    poi_data = json.loads(POI_FILE.read_text(encoding="utf-8"))
    full_map = json.loads(FULL_MAP_FILE.read_text(encoding="utf-8"))
    counters = curate_points(poi_data, full_map, fetch_walking_trails())

    print(f"Verified non-peak access markers: {counters['verified_access_points']}")
    print(f"Hidden pending review: {counters['hidden_pending_review']}")
    print(f"Curated centroid exceptions: {counters['curated_exceptions']}")
    print(f"Peaks left unchanged: {counters['peaks_unchanged']}")

    if not args.write:
        print("Dry run only. Pass --write to update graph_nodes.json.")
        return

    temporary_file = POI_FILE.with_suffix(".json.tmp")
    temporary_file.write_text(
        json.dumps(poi_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(POI_FILE)
    print(f"Updated {POI_FILE}")


if __name__ == "__main__":
    main()
