"""
Oblicza elevation_gain_m dla krawędzi bezpośrednio na cala_mapa.json.
Modyfikacja fill_edge_elevation_data.py żeby pracowała z istniejącym plikiem.
"""

import json
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MAP_FILE = BACKEND_DIR / "mapa" / "cala_mapa.json"


def as_number(value, default=None):
    """Bezpiecznie zamienia wartość na liczbę."""
    try:
        if value is None:
            return default
        if isinstance(value, str) and value.strip().lower() in {"", "unknown", "none", "null"}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_nodes_by_id(nodes):
    """Tworzy słownik węzłów według ich ID."""
    nodes_by_id = {}
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict):
                node_id = node.get("id")
                if node_id:
                    nodes_by_id[node_id] = node
    elif isinstance(nodes, dict):
        for node_key, node in nodes.items():
            if isinstance(node, dict):
                node_id = node.get("id", node_key)
                nodes_by_id[node_id] = node
    return nodes_by_id


def calculate_slope_percent(elevation_difference_m, distance_km):
    """Oblicza średnie nachylenie odcinka."""
    distance_m = distance_km * 1000
    if distance_m <= 0:
        return None
    absolute_difference = abs(elevation_difference_m)
    slope_percent = (absolute_difference / distance_m) * 100
    return round(slope_percent, 2)


def update_edges(map_data):
    nodes = map_data.get("nodes", [])
    edges = map_data.get("edges", [])

    nodes_by_id = build_nodes_by_id(nodes)

    statistics = {
        "all_edges": len(edges),
        "updated": 0,
        "missing_node": 0,
        "missing_elevation": 0,
        "invalid_distance": 0,
        "suspicious_slope": 0,
    }

    for edge in edges:
        start_id = edge.get("from")
        end_id = edge.get("to")

        start_node = nodes_by_id.get(start_id)
        end_node = nodes_by_id.get(end_id)

        if start_node is None or end_node is None:
            statistics["missing_node"] += 1
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
            continue

        distance_km = as_number(edge.get("distance_km"))

        if distance_km is None or distance_km <= 0:
            statistics["invalid_distance"] += 1
            continue

        elevation_change = round(end_elevation - start_elevation, 1)
        elevation_gain = round(max(0, elevation_change), 1)
        elevation_loss = round(max(0, -elevation_change), 1)
        slope_percent = calculate_slope_percent(elevation_change, distance_km)

        if slope_percent is None:
            statistics["invalid_distance"] += 1
            continue

        if slope_percent > 100:
            statistics["suspicious_slope"] += 1

        edge["elevation_change_m"] = elevation_change
        edge["elevation_gain_m"] = elevation_gain
        edge["elevation_loss_m"] = elevation_loss
        edge["slope_percent"] = slope_percent

        statistics["updated"] += 1

    return statistics


def main():
    if not MAP_FILE.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku: {MAP_FILE}")

    print(f"Wczytywanie: {MAP_FILE}")

    with MAP_FILE.open("r", encoding="utf-8") as file:
        map_data = json.load(file)

    print("Obliczam elevation_gain_m dla wszystkich krawędzi...")
    statistics = update_edges(map_data)

    # Bezpiecznie zapisz plik
    temporary_file = MAP_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(map_data, file, ensure_ascii=False, indent=2)

    os.replace(temporary_file, MAP_FILE)

    print()
    print("✓ Uzupełnianie krawędzi zakończone.")
    print(f"  Uzupełnione: {statistics['updated']} / {statistics['all_edges']}")
    print(f"  Brak węzła: {statistics['missing_node']}")
    print(f"  Brak wysokości węzła: {statistics['missing_elevation']}")
    print(f"  Nieprawidłowa długość: {statistics['invalid_distance']}")
    print(f"  Podejrzane nachylenie >100%: {statistics['suspicious_slope']}")
    print(f"\n✓ Plik zapisany: {MAP_FILE}")


if __name__ == "__main__":
    main()
