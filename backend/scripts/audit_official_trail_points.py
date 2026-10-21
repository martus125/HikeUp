"""Audit every POI against a complete downloaded official TPN walking layer.

Reads data without changing visibility or coordinates. Geometric agreement is
not confirmation of legal access, current opening, or safety in the field.
Run from backend: python scripts/audit_official_trail_points.py
"""
import csv
from collections import Counter
from pathlib import Path
import json
import sys

import numpy as np
from pyproj import Transformer
import shapely
from shapely.geometry import LineString
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.curate_tpn_access_points import CURATED_EXCEPTIONS, source_coordinates

BASE = Path(__file__).resolve().parents[1]
REPORTS = BASE / "reports"


def audit():
    snapshot_path = REPORTS / "tpn_trails_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    pois = json.loads((BASE / "mapa/graph_nodes.json").read_text(encoding="utf-8"))["nodes"]
    verification_path = REPORTS / "poi_verification.json"
    archived = {}
    if verification_path.exists():
        archived = {p["id"]: p for p in json.loads(verification_path.read_text(encoding="utf-8"))["nodes"]}
    graph = json.loads((BASE / "mapa/cala_mapa.json").read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in graph["nodes"]}
    metric = Transformer.from_crs(4326, 32634, always_xy=True)
    parts, attributes = [], []
    walking_features = []
    for feature in snapshot["features"]:
        if "pieszy" not in (feature["attributes"].get("TYP") or ""):
            continue
        walking_features.append(feature)
        for path in feature["geometry"].get("paths", []):
            if len(path) > 1:
                parts.append(transform(metric.transform, LineString(path)))
                attributes.append(feature["attributes"])
    if not parts:
        raise ValueError("No official walking geometry")
    union = unary_union(parts)
    tree = STRtree(parts)

    def point(lng, lat):
        return shapely.Point(*metric.transform(float(lng), float(lat)))

    connected_ids = {edge[key] for edge in graph["edges"] for key in ("from", "to")}
    rows = []
    for poi in pois:
        original = point(*source_coordinates({**archived.get(poi["id"], {}), **poi}))
        marker = point(poi["lng"], poi["lat"])
        nearest = int(tree.nearest(original))
        distance = original.distance(parts[nearest])
        node_id = poi.get("routing_node_id") or poi.get("nearest_routing_node_id")
        node = nodes.get(node_id)
        routing = point(node["lng"], node["lat"]) if node else None
        exception = CURATED_EXCEPTIONS.get(poi["id"])
        tolerance = 30.0
        if exception and exception["name"] == poi["name"]:
            tolerance = exception["max_distance_m"]
        reasons = []
        if distance > tolerance:
            reasons.append("feature_not_on_official_trail")
        if marker.distance(union) > 20:
            reasons.append("marker_off_official_trail")
        if routing is None or node_id not in connected_ids:
            reasons.append("missing_connected_routing_node")
        elif routing.distance(union) > 20:
            reasons.append("routing_node_off_official_trail")
        if routing is not None and marker.distance(routing) > 100:
            reasons.append("marker_too_far_from_routing_node")
        if routing is not None and original.distance(routing) > tolerance + 50:
            reasons.append("access_node_too_far_from_feature")
        attr = attributes[nearest]
        rows.append({
            "id": poi["id"], "name": poi["name"], "type": poi.get("type"),
            "currently_selectable": True,
            "geometric_check_passed": not reasons,
            "feature_distance_to_official_trail_m": round(distance, 2),
            "marker_distance_to_official_trail_m": round(marker.distance(union), 2),
            "routing_node_distance_to_official_trail_m": round(routing.distance(union), 2) if routing is not None else None,
            "feature_to_routing_node_m": round(original.distance(routing), 2) if routing is not None else None,
            "routing_node_id": node_id,
            "nearest_official_section": " - ".join(str(attr[key]) for key in ("PKT_START", "PKT_END") if attr.get(key)),
            "official_color": attr.get("KOLOR_1"),
            "reasons": ";".join(reasons),
        })

    # Endpoint checks do not certify routes. Audit graph geometry separately.
    node_list = graph["nodes"]
    x, y = metric.transform([n["lng"] for n in node_list], [n["lat"] for n in node_list])
    positions = np.column_stack((x, y))
    indexes = {n["id"]: i for i, n in enumerate(node_list)}
    edge_positions = np.asarray([[positions[indexes[e["from"]]], positions[indexes[e["to"]]]] for e in graph["edges"]])
    within_corridor = shapely.covered_by(shapely.linestrings(edge_positions), union.buffer(20))
    selected = [row for row in rows if row["currently_selectable"]]
    summary = {
        "source": snapshot["source"], "retrieved_at": snapshot["retrieved_at"],
        "official_features_total": len(snapshot["features"]),
        "official_walking_features": len(walking_features),
        "poi_total": len(rows), "currently_selectable": len(selected),
        "selectable_geometric_pass": sum(r["geometric_check_passed"] for r in selected),
        "selectable_requires_review": sum(not r["geometric_check_passed"] for r in selected),
        "all_geometric_pass": sum(r["geometric_check_passed"] for r in rows),
        "review_reasons_for_selectable": dict(Counter(reason for r in selected for reason in r["reasons"].split(";") if reason)),
        "graph_edges_total": len(graph["edges"]),
        "graph_edges_within_20m_of_official_walking_geometry": int(np.count_nonzero(within_corridor)),
        "graph_edges_not_fully_within_corridor": int(np.count_nonzero(~within_corridor)),
        "limitations": [
            "30m feature tolerance; documented centroid exceptions retain separate limits.",
            "20m marker/routing corridor is a geometric screen, not legal or field verification.",
            "No verification of temporary/seasonal closures, one-way restrictions or walking safety.",
            "Graph coverage uses straight segments between routing nodes; unmatched edges require review, not automatic classification as illegal.",
            "Official TPN coverage does not certify destinations outside this layer's area.",
        ],
    }
    (REPORTS / "official_trail_points_audit.json").write_text(json.dumps({"summary": summary, "points": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (REPORTS / "official_trail_points_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    audit()
