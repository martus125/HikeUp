"""Analizuje wpływ rozdzielczości DEM na nachylenia krawędzi."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MAP_FILE = BACKEND_DIR / "mapa" / "cala_mapa.json"

# Open-Meteo Elevation API deklaruje model Copernicus DEM o rozdzielczości 90 m:
# https://open-meteo.com/en/docs/elevation-api
ELEVATION_MODEL_RESOLUTION_M = 90.0
DISTANCE_BINS_M = (0, 1, 2, 5, 10, 20, 30, 50, 90, 180, math.inf)


def percentile(values, percent):
    if not values:
        return 0.0

    ordered = sorted(values)
    index = (len(ordered) - 1) * percent / 100.0
    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return ordered[lower]

    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def analyze(map_data):
    nodes = map_data.get("nodes", [])
    edges = map_data.get("edges", [])
    nodes_by_id = {node["id"]: node for node in nodes}
    elevations = [float(node["elevation"]) for node in nodes]
    fractional_elevations = sum(
        not math.isclose(elevation, round(elevation), abs_tol=1e-9)
        for elevation in elevations
    )
    bins = {
        (lower, upper): {
            "total": 0,
            "zero_slope": 0,
            "slope_gt_100": 0,
            "same_endpoint_elevation": 0,
        }
        for lower, upper in zip(DISTANCE_BINS_M, DISTANCE_BINS_M[1:])
    }
    distances = []
    elevation_differences = []
    short_edges = 0
    short_zero_edges = 0
    short_extreme_edges = 0
    all_zero_edges = 0
    zero_with_equal_elevation = 0
    all_extreme_edges = 0
    way_counts = Counter(edge.get("osm_way_id") for edge in edges)
    way_distances = Counter()
    way_runs = 0
    previous_way_id = object()
    previous_edge = None
    disconnected_edges_within_way_run = 0

    for edge in edges:
        way_id = edge.get("osm_way_id")
        if way_id != previous_way_id:
            way_runs += 1
            previous_way_id = way_id
        elif previous_edge is not None and previous_edge.get("to") != edge.get("from"):
            disconnected_edges_within_way_run += 1
        previous_edge = edge
        distance_m = float(edge["distance_km"]) * 1000.0
        way_distances[way_id] += distance_m
        slope = abs(float(edge["slope_percent"]))
        start_elevation = float(nodes_by_id[edge["from"]]["elevation"])
        end_elevation = float(nodes_by_id[edge["to"]]["elevation"])
        elevation_difference = abs(end_elevation - start_elevation)
        same_elevation = math.isclose(
            start_elevation,
            end_elevation,
            abs_tol=1e-9,
        )
        distances.append(distance_m)
        elevation_differences.append(elevation_difference)
        all_zero_edges += slope == 0
        zero_with_equal_elevation += slope == 0 and same_elevation
        all_extreme_edges += slope > 100

        if distance_m < ELEVATION_MODEL_RESOLUTION_M:
            short_edges += 1
            short_zero_edges += slope == 0
            short_extreme_edges += slope > 100

        for (lower, upper), statistics in bins.items():
            if lower <= distance_m < upper:
                statistics["total"] += 1
                statistics["zero_slope"] += slope == 0
                statistics["slope_gt_100"] += slope > 100
                statistics["same_endpoint_elevation"] += same_elevation
                break

    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "unique_elevations": len(set(elevations)),
        "fractional_elevations": fractional_elevations,
        "distance_percentiles_m": {
            key: round(percentile(distances, value), 2)
            for key, value in (("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))
        },
        "elevation_difference_percentiles_m": {
            key: round(percentile(elevation_differences, value), 2)
            for key, value in (("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90), ("p99", 99))
        },
        "short_edges": short_edges,
        "short_zero_edges": short_zero_edges,
        "short_extreme_edges": short_extreme_edges,
        "all_zero_edges": all_zero_edges,
        "zero_with_equal_elevation": zero_with_equal_elevation,
        "all_extreme_edges": all_extreme_edges,
        "unique_way_ids": len(way_counts),
        "missing_way_id": way_counts.get(None, 0),
        "way_runs": way_runs,
        "disconnected_edges_within_way_run": disconnected_edges_within_way_run,
        "short_way_ids": sum(
            distance < ELEVATION_MODEL_RESOLUTION_M
            for distance in way_distances.values()
        ),
        "edges_in_short_ways": sum(
            way_counts[way_id]
            for way_id, distance in way_distances.items()
            if distance < ELEVATION_MODEL_RESOLUTION_M
        ),
        "bins": bins,
    }


def format_bin(lower, upper):
    if math.isinf(upper):
        return f">= {lower:g} m"
    return f"{lower:g}–{upper:g} m"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_file", nargs="?", type=Path, default=DEFAULT_MAP_FILE)
    args = parser.parse_args()

    with args.map_file.open("r", encoding="utf-8") as file:
        report = analyze(json.load(file))

    print(f"DEM resolution: {ELEVATION_MODEL_RESOLUTION_M:.0f} m")
    print(f"Nodes: {report['nodes']}")
    print(f"Edges: {report['edges']}")
    print(f"Unique elevation values: {report['unique_elevations']}")
    print(f"Fractional elevation values: {report['fractional_elevations']}")
    print(f"Unique OSM way IDs: {report['unique_way_ids']}")
    print(f"Edges without OSM way ID: {report['missing_way_id']}")
    print(f"Contiguous OSM way runs: {report['way_runs']}")
    print(
        "Disconnected transitions inside way runs: "
        f"{report['disconnected_edges_within_way_run']}"
    )
    print(
        "OSM ways shorter than DEM resolution: "
        f"{report['short_way_ids']} (edges: {report['edges_in_short_ways']})"
    )
    print(f"Edge distance percentiles: {report['distance_percentiles_m']}")
    print(
        "Endpoint elevation difference percentiles: "
        f"{report['elevation_difference_percentiles_m']}"
    )
    print(
        f"Edges shorter than DEM resolution: {report['short_edges']} / "
        f"{report['edges']}"
    )
    print(f"Zero slopes on short edges: {report['short_zero_edges']}")
    print(f">100% slopes on short edges: {report['short_extreme_edges']}")
    print(
        "Zero slopes explained by equal endpoint DEM elevation: "
        f"{report['zero_with_equal_elevation']} / {report['all_zero_edges']}"
    )
    print("\nBY EDGE LENGTH:")

    for (lower, upper), statistics in report["bins"].items():
        total = statistics["total"]
        if not total:
            continue
        zero_percent = statistics["zero_slope"] / total * 100
        extreme_percent = statistics["slope_gt_100"] / total * 100
        print(
            f"  {format_bin(lower, upper):>10}: total={total:6d}, "
            f"zero={statistics['zero_slope']:6d} ({zero_percent:5.1f}%), "
            f">100={statistics['slope_gt_100']:5d} ({extreme_percent:5.1f}%)"
        )


if __name__ == "__main__":
    main()
