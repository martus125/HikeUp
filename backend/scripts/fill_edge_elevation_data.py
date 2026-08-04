"""
Uzupełnia dane wysokościowe krawędzi grafu.

Dla każdej krawędzi zapisuje:
- elevation_change_m - podpisana zmiana wysokości from -> to,
- elevation_gain_m - suma podejścia w kierunku from -> to,
- elevation_loss_m - suma zejścia w kierunku from -> to,
- slope_percent - średnia bezwzględna stromizna odcinka.
"""

import json
import math
import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent

# Ustaw tutaj plik, w którym wszystkie węzły mają już wysokość.
INPUT_FILE = (
    BACKEND_DIR
    / "mapa"
    / "cala_mapa_with_elevation.json"
)

OUTPUT_FILE = (
    BACKEND_DIR
    / "mapa"
    / "cala_mapa_with_elevation.json"
)


def as_number(value, default=None):
    """Bezpiecznie zamienia wartość na liczbę."""
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

        return float(value)

    except (TypeError, ValueError):
        return default


def build_nodes_by_id(nodes):
    """Tworzy słownik węzłów według ich ID."""
    nodes_by_id = {}

    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue

            node_id = node.get("id")

            if node_id:
                nodes_by_id[node_id] = node

    elif isinstance(nodes, dict):
        for node_key, node in nodes.items():
            if not isinstance(node, dict):
                continue

            node_id = node.get("id", node_key)
            nodes_by_id[node_id] = node

    else:
        raise TypeError(
            "Pole nodes musi być listą albo słownikiem."
        )

    return nodes_by_id


def calculate_slope_percent(
    elevation_difference_m,
    distance_km,
):
    """
    Oblicza średnie nachylenie odcinka.

    distance_km jest długością odcinka szlaku.
    Przy bardzo krótkich albo błędnych odcinkach
    wynik jest ograniczany do rozsądnej wartości.
    """
    distance_m = distance_km * 1000

    if distance_m <= 0:
        return None

    absolute_difference = abs(elevation_difference_m)

    slope_percent = (
        absolute_difference / distance_m
    ) * 100

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

        start_elevation = as_number(
            start_node.get("elevation")
        )
        end_elevation = as_number(
            end_node.get("elevation")
        )

        if (
            start_elevation is None
            or end_elevation is None
            or start_elevation <= 0
            or end_elevation <= 0
        ):
            statistics["missing_elevation"] += 1
            continue

        distance_km = as_number(
            edge.get("distance_km")
        )

        if distance_km is None or distance_km <= 0:
            statistics["invalid_distance"] += 1
            continue

        elevation_change = round(
            end_elevation - start_elevation,
            1,
        )

        elevation_gain = round(
            max(0, elevation_change),
            1,
        )

        elevation_loss = round(
            max(0, -elevation_change),
            1,
        )

        slope_percent = calculate_slope_percent(
            elevation_change,
            distance_km,
        )

        if slope_percent is None:
            statistics["invalid_distance"] += 1
            continue

        # Wartość bardzo wysoka może wskazywać na:
        # - bardzo krótki odcinek,
        # - niedokładność modelu wysokościowego,
        # - błędne dane mapy.
        if slope_percent > 100:
            statistics["suspicious_slope"] += 1

        edge["elevation_change_m"] = elevation_change
        edge["elevation_gain_m"] = elevation_gain
        edge["elevation_loss_m"] = elevation_loss
        edge["slope_percent"] = slope_percent

        statistics["updated"] += 1

    return statistics


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku: {INPUT_FILE}"
        )

    print(f"Wczytywanie: {INPUT_FILE}")

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        map_data = json.load(file)

    statistics = update_edges(map_data)

    temporary_file = OUTPUT_FILE.with_suffix(".tmp")

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            map_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temporary_file, OUTPUT_FILE)

    print()
    print("Uzupełnianie krawędzi zakończone.")
    print(
        f"Uzupełnione: "
        f"{statistics['updated']} / "
        f"{statistics['all_edges']}"
    )
    print(
        f"Brak węzła: "
        f"{statistics['missing_node']}"
    )
    print(
        f"Brak wysokości: "
        f"{statistics['missing_elevation']}"
    )
    print(
        f"Nieprawidłowa długość: "
        f"{statistics['invalid_distance']}"
    )
    print(
        f"Podejrzane nachylenie > 100%: "
        f"{statistics['suspicious_slope']}"
    )
    print()
    print(f"Nowy plik: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()