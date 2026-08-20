"""Diagnostyka danych routingu bez modyfikowania plików mapy."""

import argparse
import heapq
import json
import math
from collections import Counter
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MAP_FILE = BACKEND_DIR / "mapa" / "cala_mapa.json"
DEFAULT_POI_FILE = BACKEND_DIR / "mapa" / "graph_nodes.json"
EXPECTED_EDGE_FIELDS = (
    "distance_km",
    "time_min",
    "elevation_gain_m",
    "elevation_loss_m",
    "difficulty",
    "slope_percent",
)
NONNEGATIVE_FIELDS = set(EXPECTED_EDGE_FIELDS) | {"elevation"}
SHELTER_TYPES = {"alpine_hut", "shelter"}


def as_number(value):
    try:
        if value is None or isinstance(value, bool):
            return None

        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def normalize_collection(data, key):
    collection = data.get(key, []) if isinstance(data, dict) else data

    if isinstance(collection, list):
        return collection

    if isinstance(collection, dict):
        return [
            {"id": item_id, **item}
            for item_id, item in collection.items()
            if isinstance(item, dict)
        ]

    return []


def analyze_data(map_data, poi_data=None):
    """Zwraca pełny raport w postaci słownika, dogodny także dla testów."""
    nodes = normalize_collection(map_data, "nodes")
    edges = normalize_collection(map_data, "edges")
    points = normalize_collection(poi_data or {}, "nodes")
    node_ids = {
        node.get("id")
        for node in nodes
        if isinstance(node, dict) and node.get("id") is not None
    }
    node_id_counts = Counter(
        node.get("id")
        for node in nodes
        if isinstance(node, dict) and node.get("id") is not None
    )

    node_report = {
        "total": len(nodes),
        "missing_id": 0,
        "duplicate_id": sum(count - 1 for count in node_id_counts.values()),
        "missing_elevation": 0,
        "zero_elevation": 0,
        "invalid_lat_lng": 0,
    }
    edge_report = {
        "total": len(edges),
        "missing_from_or_to": 0,
        "missing_node_reference": 0,
        "missing_distance": 0,
        "distance_le_zero": 0,
        "missing_time": 0,
        "time_le_zero": 0,
        "missing_elevation_gain": 0,
        "missing_elevation_loss": 0,
        "missing_difficulty": 0,
        "missing_slope": 0,
        "slope_zero": 0,
        "slope_gt_30": 0,
        "slope_gt_50": 0,
        "slope_gt_100": 0,
        "max_slope": 0.0,
        "average_slope": 0.0,
        "parallel_edges": 0,
    }
    general_report = {
        "none_values": 0,
        "nan_or_infinite_values": 0,
        "negative_values": 0,
        "negative_values_by_field": Counter(),
    }

    for node in nodes:
        if not isinstance(node, dict):
            node_report["missing_id"] += 1
            continue

        if node.get("id") is None:
            node_report["missing_id"] += 1

        elevation = as_number(node.get("elevation"))
        if elevation is None:
            node_report["missing_elevation"] += 1
        elif elevation == 0:
            node_report["zero_elevation"] += 1

        lat = as_number(node.get("lat", node.get("latitude")))
        lng = as_number(
            node.get("lng", node.get("lon", node.get("longitude")))
        )
        if (
            lat is None
            or lng is None
            or not -90 <= lat <= 90
            or not -180 <= lng <= 180
        ):
            node_report["invalid_lat_lng"] += 1

        _scan_top_level_values(node, general_report)

    slopes = []
    extreme_edges = []
    edge_pair_counts = Counter()

    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            for field in EXPECTED_EDGE_FIELDS:
                _increment_missing_edge_field(edge_report, field)
            edge_report["missing_from_or_to"] += 1
            continue

        start = edge.get("from")
        end = edge.get("to")
        if start is None or end is None:
            edge_report["missing_from_or_to"] += 1
        else:
            edge_pair_counts[tuple(sorted((str(start), str(end))))] += 1
            if start not in node_ids or end not in node_ids:
                edge_report["missing_node_reference"] += 1

        values = {}
        for field in EXPECTED_EDGE_FIELDS:
            value = as_number(edge.get(field))
            values[field] = value
            if value is None:
                _increment_missing_edge_field(edge_report, field)

        distance = values["distance_km"]
        route_time = values["time_min"]
        slope = values["slope_percent"]

        if distance is not None and distance <= 0:
            edge_report["distance_le_zero"] += 1
        if route_time is not None and route_time <= 0:
            edge_report["time_le_zero"] += 1

        if slope is not None:
            absolute_slope = abs(slope)
            slopes.append(absolute_slope)
            edge_report["slope_zero"] += absolute_slope == 0
            edge_report["slope_gt_30"] += absolute_slope > 30
            edge_report["slope_gt_50"] += absolute_slope > 50
            edge_report["slope_gt_100"] += absolute_slope > 100
            heapq.heappush(
                extreme_edges,
                (
                    absolute_slope,
                    index,
                    {
                        "from": start,
                        "to": end,
                        "distance_km": distance,
                        "slope_percent": slope,
                    },
                ),
            )
            if len(extreme_edges) > 5:
                heapq.heappop(extreme_edges)

        _scan_top_level_values(edge, general_report)

    edge_report["parallel_edges"] = sum(
        count - 1 for count in edge_pair_counts.values() if count > 1
    )
    if slopes:
        edge_report["max_slope"] = round(max(slopes), 2)
        edge_report["average_slope"] = round(sum(slopes) / len(slopes), 2)

    shelter_report = {
        "total_poi": len(points),
        "shelters": sum(
            isinstance(point, dict) and point.get("type") in SHELTER_TYPES
            for point in points
        ),
    }
    routing_metadata = map_data.get("routing_data_metadata", {})
    elevation_metadata = routing_metadata.get("elevation", {})
    slope_metadata = routing_metadata.get("slope_calculation", {})
    metadata_report = {
        "elevation_source": elevation_metadata.get("source"),
        "model_resolution_m": as_number(
            elevation_metadata.get("model_resolution_m")
        ),
        "slope_method": slope_metadata.get("method"),
        "slope_version": slope_metadata.get("version"),
        "slope_window_m": as_number(slope_metadata.get("window_m")),
        "raw_zero_slope_edges": slope_metadata.get("raw_zero_slope_edges"),
        "raw_slope_above_100_edges": slope_metadata.get(
            "raw_slope_above_100_edges"
        ),
        "corrected_zero_slope_edges": slope_metadata.get(
            "corrected_zero_slope_edges"
        ),
        "corrected_values_capped": slope_metadata.get(
            "corrected_values_capped"
        ),
        "resolution_limited_edges": slope_metadata.get(
            "resolution_limited_edges"
        ),
    }
    blockers = _benchmark_blockers(
        node_report,
        edge_report,
        general_report,
        metadata_report,
    )

    return {
        "nodes": node_report,
        "edges": edge_report,
        "general": {
            **general_report,
            "negative_values_by_field": dict(
                general_report["negative_values_by_field"]
            ),
        },
        "poi": shelter_report,
        "metadata": metadata_report,
        "extreme_edges": [
            item[2]
            for item in sorted(extreme_edges, reverse=True)
        ],
        "blockers": blockers,
        "ready_for_benchmark": not blockers,
    }


def _increment_missing_edge_field(report, field):
    key_by_field = {
        "distance_km": "missing_distance",
        "time_min": "missing_time",
        "elevation_gain_m": "missing_elevation_gain",
        "elevation_loss_m": "missing_elevation_loss",
        "difficulty": "missing_difficulty",
        "slope_percent": "missing_slope",
    }
    report[key_by_field[field]] += 1


def _scan_top_level_values(item, report):
    for field, value in item.items():
        if value is None:
            report["none_values"] += 1
            continue

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue

        if not math.isfinite(float(value)):
            report["nan_or_infinite_values"] += 1
        elif value < 0:
            report["negative_values"] += 1
            report["negative_values_by_field"][field] += 1


def _benchmark_blockers(nodes, edges, general, metadata):
    checks = [
        (nodes["missing_id"], "węzły bez ID"),
        (nodes["duplicate_id"], "zduplikowane ID węzłów"),
        (nodes["missing_elevation"], "węzły bez poprawnej wysokości"),
        (nodes["zero_elevation"], "węzły z zerową wysokością"),
        (nodes["invalid_lat_lng"], "węzły z niepoprawnymi współrzędnymi"),
        (edges["missing_from_or_to"], "krawędzie bez końców"),
        (edges["missing_node_reference"], "krawędzie do nieistniejących węzłów"),
        (edges["missing_distance"], "krawędzie bez dystansu"),
        (edges["distance_le_zero"], "krawędzie z dystansem <= 0"),
        (edges["missing_time"], "krawędzie bez czasu"),
        (edges["time_le_zero"], "krawędzie z czasem <= 0"),
        (edges["missing_elevation_gain"], "krawędzie bez elevation gain"),
        (edges["missing_elevation_loss"], "krawędzie bez elevation loss"),
        (edges["missing_difficulty"], "krawędzie bez trudności"),
        (edges["missing_slope"], "krawędzie bez nachylenia"),
        (edges["slope_gt_100"], "krawędzie z nachyleniem > 100%"),
        (general["nan_or_infinite_values"], "wartości NaN lub nieskończone"),
    ]
    negative_critical = sum(
        count
        for field, count in general["negative_values_by_field"].items()
        if field in NONNEGATIVE_FIELDS
    )
    checks.append((negative_critical, "ujemne wartości w polach nieujemnych"))
    blockers = [f"{label}: {count}" for count, label in checks if count]

    if not metadata["elevation_source"]:
        blockers.append("brak metadanych źródła elevation")
    if not metadata["slope_method"]:
        blockers.append("brak metadanych metody obliczenia slope")
    if (
        metadata["model_resolution_m"] is None
        or metadata["slope_window_m"] is None
        or metadata["slope_window_m"] < metadata["model_resolution_m"] * 2
    ):
        blockers.append(
            "okno slope jest krótsze niż dwie komórki modelu elevation"
        )

    return blockers


def print_report(report, map_file, poi_file):
    nodes = report["nodes"]
    edges = report["edges"]
    general = report["general"]
    metadata = report["metadata"]

    print(f"MAP FILE: {map_file}")
    print(f"POI FILE: {poi_file}")
    print("\nNODES:")
    print(f"  total: {nodes['total']}")
    print(f"  missing elevation: {nodes['missing_elevation']}")
    print(f"  zero elevation: {nodes['zero_elevation']}")
    print(f"  invalid lat/lng: {nodes['invalid_lat_lng']}")
    print(f"  missing id: {nodes['missing_id']}")
    print(f"  duplicate id: {nodes['duplicate_id']}")

    print("\nEDGES:")
    print(f"  total: {edges['total']}")
    print(f"  missing distance: {edges['missing_distance']}")
    print(f"  distance <= 0: {edges['distance_le_zero']}")
    print(f"  missing time: {edges['missing_time']}")
    print(f"  time <= 0: {edges['time_le_zero']}")
    print(f"  missing elevation gain: {edges['missing_elevation_gain']}")
    print(f"  missing elevation loss: {edges['missing_elevation_loss']}")
    print(f"  missing difficulty: {edges['missing_difficulty']}")
    print(f"  missing slope: {edges['missing_slope']}")
    print(f"  slope = 0: {edges['slope_zero']}")
    print(f"  slope > 30%: {edges['slope_gt_30']}")
    print(f"  slope > 50%: {edges['slope_gt_50']}")
    print(f"  slope > 100%: {edges['slope_gt_100']}")
    print(f"  maximum slope: {edges['max_slope']:.2f}%")
    print(f"  average slope: {edges['average_slope']:.2f}%")
    print(f"  parallel edge records: {edges['parallel_edges']}")
    print(f"  missing node references: {edges['missing_node_reference']}")

    print("\nGENERAL:")
    print(f"  None values: {general['none_values']}")
    print(f"  NaN/infinite values: {general['nan_or_infinite_values']}")
    print(f"  negative values: {general['negative_values']}")
    print(
        "  negative values by field: "
        f"{general['negative_values_by_field']}"
    )
    print(f"  POI: {report['poi']['total_poi']}")
    print(f"  shelters: {report['poi']['shelters']}")

    print("\nSLOPE METHODOLOGY:")
    print(f"  elevation source: {metadata['elevation_source']}")
    print(f"  model resolution: {metadata['model_resolution_m']} m")
    print(f"  method: {metadata['slope_method']}")
    print(f"  version: {metadata['slope_version']}")
    print(f"  window: {metadata['slope_window_m']} m")
    print(f"  raw slope = 0: {metadata['raw_zero_slope_edges']}")
    print(f"  raw slope > 100%: {metadata['raw_slope_above_100_edges']}")
    print(f"  corrected slope = 0: {metadata['corrected_zero_slope_edges']}")
    print(f"  corrected values capped: {metadata['corrected_values_capped']}")
    print(f"  resolution-limited edges: {metadata['resolution_limited_edges']}")

    print("\nHIGHEST SLOPES (short edges can amplify elevation noise):")
    for edge in report["extreme_edges"]:
        print(
            "  "
            f"{edge['from']} -> {edge['to']}: "
            f"slope={edge['slope_percent']}%, "
            f"distance={edge['distance_km']} km"
        )

    print("\nBLOCKERS:")
    if report["blockers"]:
        for blocker in report["blockers"]:
            print(f"  - {blocker}")
    else:
        print("  none")

    ready = "YES" if report["ready_for_benchmark"] else "NO"
    print(f"\nDATA READY FOR BENCHMARK: {ready}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_file", nargs="?", type=Path, default=DEFAULT_MAP_FILE)
    parser.add_argument("--poi-file", type=Path, default=DEFAULT_POI_FILE)
    args = parser.parse_args()

    with args.map_file.open("r", encoding="utf-8") as file:
        map_data = json.load(file)

    poi_data = {}
    if args.poi_file.exists():
        with args.poi_file.open("r", encoding="utf-8") as file:
            poi_data = json.load(file)

    report = analyze_data(map_data, poi_data)
    print_report(report, args.map_file, args.poi_file)


if __name__ == "__main__":
    main()
