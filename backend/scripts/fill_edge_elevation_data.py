"""Przelicza kierunkowe elevation i slope w ``cala_mapa.json``.

Wysokości węzłów pochodzą z modelu Copernicus DEM udostępnianego przez
Open-Meteo Elevation API. Model ma rozdzielczość 90 m, podczas gdy niemal
wszystkie krawędzie grafu są krótsze. Bezpośrednie dzielenie różnicy wysokości
końców przez długość mikro-krawędzi tworzy sztuczne zera i nachylenia liczone
w tysiącach procent.

Skrypt wyznacza więc lokalny gradient w centrowanym oknie 180 m (dwie komórki
DEM, po jednej z każdej strony analizowanego miejsca)
wzdłuż kolejnych krawędzi tego samego OSM way. Gradient jest rozprowadzany na
mikro-krawędzie i służy również do spójnego wyliczenia gain/loss oraz czasu.
Krótsze całe fragmenty OSM używają swojej pełnej długości, ale mianownika 180 m,
co jawnie ogranicza pewność danych poniżej rozdzielczości źródła.
"""

import argparse
import bisect
import json
import math
import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
MAP_FILE = BACKEND_DIR / "mapa" / "cala_mapa.json"

# Oficjalna dokumentacja źródła: https://open-meteo.com/en/docs/elevation-api
ELEVATION_MODEL_RESOLUTION_M = 90.0
SLOPE_WINDOW_M = ELEVATION_MODEL_RESOLUTION_M * 2.0
MAX_PLAUSIBLE_SLOPE_PERCENT = 100.0
SLOPE_METHOD = "centered_180m_window_along_osm_way"
SLOPE_CALCULATION_VERSION = 2


def as_number(value, default=None):
    """Bezpiecznie zamienia wartość na skończoną liczbę."""
    try:
        if value is None:
            return default
        if isinstance(value, str) and value.strip().lower() in {
            "",
            "unknown",
            "none",
            "null",
        }:
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def build_nodes_by_id(nodes):
    """Tworzy słownik węzłów według ich ID."""
    nodes_by_id = {}
    if isinstance(nodes, list):
        iterator = ((node.get("id"), node) for node in nodes if isinstance(node, dict))
    elif isinstance(nodes, dict):
        iterator = (
            (node.get("id", node_key), node)
            for node_key, node in nodes.items()
            if isinstance(node, dict)
        )
    else:
        iterator = ()

    for node_id, node in iterator:
        if node_id:
            nodes_by_id[node_id] = node

    return nodes_by_id


def calculate_slope_percent(elevation_difference_m, distance_km):
    """Liczy surowe nachylenie; funkcja pozostaje użyteczna w testach."""
    distance = as_number(distance_km)
    difference = as_number(elevation_difference_m)
    if distance is None or difference is None or distance <= 0:
        return None
    return round(abs(difference) / (distance * 1000.0) * 100.0, 2)


def calculate_hiking_time_minutes(distance_km, elevation_gain_m):
    """Szacuje czas: 5 km/h po płaskim i 600 m podejścia na godzinę."""
    flat_time = distance_km / 5.0 * 60.0
    ascent_time = elevation_gain_m / 600.0 * 60.0
    estimated_time = flat_time + ascent_time
    # W pliku zapisujemy dwie cyfry po przecinku. Dodatni czas mikro-krawędzi
    # nie może po zaokrągleniu zmienić się w zero.
    return max(0.01, round(estimated_time, 2))


def _initial_statistics(edges):
    return {
        "all_edges": len(edges),
        "updated": 0,
        "missing_node": 0,
        "missing_elevation": 0,
        "invalid_distance": 0,
        "raw_zero_slope": 0,
        "raw_slope_above_100": 0,
        "corrected_zero_slope": 0,
        "corrected_slope_above_100": 0,
        "corrected_slope_capped": 0,
        "corrected_capped_resolution_limited": 0,
        "corrected_capped_full_window": 0,
        "max_corrected_slope_before_cap": 0.0,
        "capped_way_ids": set(),
        "capped_examples": [],
        "resolution_limited_runs": 0,
        "resolution_limited_edges": 0,
        # Kompatybilność ze starszym raportem i testami.
        "suspicious_slope": 0,
    }


def _prepare_edges(edges, nodes_by_id, statistics):
    prepared = []

    for edge in edges:
        start_node = nodes_by_id.get(edge.get("from"))
        end_node = nodes_by_id.get(edge.get("to"))

        if start_node is None or end_node is None:
            statistics["missing_node"] += 1
            prepared.append(None)
            continue

        start_elevation = as_number(start_node.get("elevation"))
        end_elevation = as_number(end_node.get("elevation"))
        if (
            start_elevation is None
            or end_elevation is None
            or start_elevation <= 0
            or end_elevation <= 0
        ):
            statistics["missing_elevation"] += 1
            prepared.append(None)
            continue

        distance_km = as_number(edge.get("distance_km"))
        if distance_km is None or distance_km <= 0:
            statistics["invalid_distance"] += 1
            prepared.append(None)
            continue

        raw_change = end_elevation - start_elevation
        raw_slope = calculate_slope_percent(raw_change, distance_km)
        statistics["raw_zero_slope"] += raw_slope == 0
        statistics["raw_slope_above_100"] += raw_slope > 100
        prepared.append(
            {
                "edge": edge,
                "distance_m": distance_km * 1000.0,
                "start_elevation": start_elevation,
                "end_elevation": end_elevation,
            }
        )

    statistics["suspicious_slope"] = statistics["raw_slope_above_100"]
    return prepared


def _group_contiguous_way_runs(prepared):
    runs = []
    current_run = []

    for edge_data in prepared:
        if edge_data is None:
            if current_run:
                runs.append(current_run)
                current_run = []
            continue

        edge = edge_data["edge"]
        if current_run:
            previous_edge = current_run[-1]["edge"]
            same_way = previous_edge.get("osm_way_id") == edge.get("osm_way_id")
            connected = previous_edge.get("to") == edge.get("from")
            if not (same_way and connected):
                runs.append(current_run)
                current_run = []

        current_run.append(edge_data)

    if current_run:
        runs.append(current_run)

    return runs


def _interpolate_elevation(position_m, positions_m, elevations_m):
    if position_m <= positions_m[0]:
        return elevations_m[0]
    if position_m >= positions_m[-1]:
        return elevations_m[-1]

    right_index = bisect.bisect_right(positions_m, position_m)
    left_index = right_index - 1
    left_position = positions_m[left_index]
    right_position = positions_m[right_index]
    segment_length = right_position - left_position
    if segment_length <= 0:
        return elevations_m[left_index]

    fraction = (position_m - left_position) / segment_length
    return (
        elevations_m[left_index]
        + fraction * (elevations_m[right_index] - elevations_m[left_index])
    )


def _window_bounds(midpoint_m, total_distance_m):
    if total_distance_m < SLOPE_WINDOW_M:
        return 0.0, total_distance_m, SLOPE_WINDOW_M

    half_window = SLOPE_WINDOW_M / 2.0
    left = max(0.0, midpoint_m - half_window)
    right = min(total_distance_m, midpoint_m + half_window)

    if right - left < SLOPE_WINDOW_M:
        if left <= 0:
            right = SLOPE_WINDOW_M
        else:
            left = total_distance_m - SLOPE_WINDOW_M

    return left, right, right - left


def _process_run(run, statistics):
    positions = [0.0]
    elevations = [run[0]["start_elevation"]]
    for edge_data in run:
        positions.append(positions[-1] + edge_data["distance_m"])
        elevations.append(edge_data["end_elevation"])

    total_distance = positions[-1]
    resolution_limited = total_distance < SLOPE_WINDOW_M
    if resolution_limited:
        statistics["resolution_limited_runs"] += 1
        statistics["resolution_limited_edges"] += len(run)

    for index, edge_data in enumerate(run):
        edge = edge_data["edge"]
        edge_distance_m = edge_data["distance_m"]
        midpoint = (positions[index] + positions[index + 1]) / 2.0
        left, right, effective_window = _window_bounds(midpoint, total_distance)
        left_elevation = _interpolate_elevation(left, positions, elevations)
        right_elevation = _interpolate_elevation(right, positions, elevations)
        signed_gradient = (right_elevation - left_elevation) / effective_window
        corrected_slope = abs(signed_gradient) * 100.0
        statistics["max_corrected_slope_before_cap"] = max(
            statistics["max_corrected_slope_before_cap"],
            corrected_slope,
        )

        if corrected_slope > MAX_PLAUSIBLE_SLOPE_PERCENT:
            statistics["corrected_slope_above_100"] += 1
            statistics["corrected_slope_capped"] += 1
            if resolution_limited:
                statistics["corrected_capped_resolution_limited"] += 1
            else:
                statistics["corrected_capped_full_window"] += 1
            statistics["capped_way_ids"].add(edge.get("osm_way_id"))
            if len(statistics["capped_examples"]) < 10:
                statistics["capped_examples"].append(
                    {
                        "from": edge.get("from"),
                        "to": edge.get("to"),
                        "osm_way_id": edge.get("osm_way_id"),
                        "trail_name": edge.get("trail_name"),
                        "slope_before_cap": round(corrected_slope, 2),
                    }
                )
            signed_gradient = math.copysign(
                MAX_PLAUSIBLE_SLOPE_PERCENT / 100.0,
                signed_gradient,
            )
            corrected_slope = MAX_PLAUSIBLE_SLOPE_PERCENT

        smoothed_change = signed_gradient * edge_distance_m
        elevation_gain = max(0.0, smoothed_change)
        elevation_loss = max(0.0, -smoothed_change)
        rounded_slope = round(corrected_slope, 2)

        edge["elevation_change_m"] = round(smoothed_change, 2)
        edge["elevation_gain_m"] = round(elevation_gain, 2)
        edge["elevation_loss_m"] = round(elevation_loss, 2)
        edge["slope_percent"] = rounded_slope
        edge["time_min"] = calculate_hiking_time_minutes(
            edge_distance_m / 1000.0,
            elevation_gain,
        )

        statistics["corrected_zero_slope"] += rounded_slope == 0
        statistics["updated"] += 1


def _set_calculation_metadata(map_data, statistics):
    metadata = map_data.setdefault("routing_data_metadata", {})
    metadata["elevation"] = {
        "source": "Open-Meteo Elevation API / Copernicus DEM",
        "source_url": "https://open-meteo.com/en/docs/elevation-api",
        "model_resolution_m": ELEVATION_MODEL_RESOLUTION_M,
    }
    metadata["slope_calculation"] = {
        "version": SLOPE_CALCULATION_VERSION,
        "method": SLOPE_METHOD,
        "window_m": SLOPE_WINDOW_M,
        "max_plausible_slope_percent": MAX_PLAUSIBLE_SLOPE_PERCENT,
        "raw_zero_slope_edges": statistics["raw_zero_slope"],
        "raw_slope_above_100_edges": statistics["raw_slope_above_100"],
        "corrected_zero_slope_edges": statistics["corrected_zero_slope"],
        "corrected_values_capped": statistics["corrected_slope_capped"],
        "corrected_capped_resolution_limited": statistics[
            "corrected_capped_resolution_limited"
        ],
        "corrected_capped_full_window": statistics[
            "corrected_capped_full_window"
        ],
        "corrected_capped_way_count": len(statistics["capped_way_ids"]),
        "max_corrected_slope_before_cap": round(
            statistics["max_corrected_slope_before_cap"],
            2,
        ),
        "resolution_limited_edges": statistics["resolution_limited_edges"],
    }


def update_edges(map_data):
    """Modyfikuje krawędzie w pamięci i zwraca statystyki audytowe."""
    nodes = map_data.get("nodes", [])
    edges = map_data.get("edges", [])
    nodes_by_id = build_nodes_by_id(nodes)
    statistics = _initial_statistics(edges)
    prepared = _prepare_edges(edges, nodes_by_id, statistics)

    for run in _group_contiguous_way_runs(prepared):
        _process_run(run, statistics)

    _set_calculation_metadata(map_data, statistics)
    return statistics


def save_map(map_data, map_file):
    """Zapisuje atomowo, aby przerwanie nie uszkodziło mapy."""
    temporary_file = map_file.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(map_data, file, ensure_ascii=False, indent=2)
    os.replace(temporary_file, map_file)


def print_statistics(statistics):
    print(f"  Wszystkie krawędzie: {statistics['all_edges']}")
    print(f"  Przeliczone: {statistics['updated']}")
    print(f"  Brak węzła: {statistics['missing_node']}")
    print(f"  Brak wysokości: {statistics['missing_elevation']}")
    print(f"  Nieprawidłowy dystans: {statistics['invalid_distance']}")
    print(f"  Surowy slope = 0: {statistics['raw_zero_slope']}")
    print(f"  Surowy slope > 100%: {statistics['raw_slope_above_100']}")
    print(f"  Skorygowany slope = 0: {statistics['corrected_zero_slope']}")
    print(
        "  Skorygowany slope > 100% przed limitem: "
        f"{statistics['corrected_slope_above_100']}"
    )
    print(f"  Wartości ograniczone do 100%: {statistics['corrected_slope_capped']}")
    print(
        "    w OSM ways < 180 m: "
        f"{statistics['corrected_capped_resolution_limited']}"
    )
    print(
        "    w pełnym oknie 180 m: "
        f"{statistics['corrected_capped_full_window']}"
    )
    print(
        "    liczba OSM ways: "
        f"{len(statistics['capped_way_ids'])}"
    )
    print(
        "    maksymalny slope przed limitem: "
        f"{statistics['max_corrected_slope_before_cap']:.2f}%"
    )
    print(
        "  Krawędzie w całych OSM ways krótszych niż okno 180 m: "
        f"{statistics['resolution_limited_edges']}"
    )
    if statistics["capped_examples"]:
        print("  Przykłady wartości ograniczonych:")
        for example in statistics["capped_examples"]:
            print(f"    {example}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_file", nargs="?", type=Path, default=MAP_FILE)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Przelicz w pamięci i pokaż statystyki bez zapisu.",
    )
    args = parser.parse_args()

    if not args.map_file.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku: {args.map_file}")

    print(f"Wczytywanie: {args.map_file}")
    with args.map_file.open("r", encoding="utf-8") as file:
        map_data = json.load(file)

    print(
        "Przeliczam slope w oknie 180 m (dwie komórki DEM)..."
    )
    statistics = update_edges(map_data)
    print_statistics(statistics)

    if args.dry_run:
        print("DRY RUN: plik nie został zmodyfikowany.")
        return

    save_map(map_data, args.map_file)
    print(f"Zapisano: {args.map_file}")


if __name__ == "__main__":
    main()
