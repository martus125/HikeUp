"""
Uzupełnia dane wysokościowe wszystkich krawędzi grafu.

Dla każdej krawędzi zapisuje:
- elevation_change_m – zmiana wysokości od from do to,
- elevation_gain_m – suma podejścia w kierunku from -> to,
- elevation_loss_m – suma zejścia w kierunku from -> to,
- slope_percent – średnia stromizna odcinka.
"""

import json
import os
from pathlib import Path


# Folder backend
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Plik faktycznie używany przez aplikację
INPUT_FILE = BACKEND_DIR / "mapa" / "cala_mapa.json"
OUTPUT_FILE = BACKEND_DIR / "mapa" / "cala_mapa.json"


def as_number(value, default=None):
    """
    Bezpiecznie zamienia wartość na liczbę.
    """

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
    """
    Tworzy słownik węzłów według ich ID.
    Obsługuje zarówno listę, jak i słownik nodes.
    """

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
            "Pole nodes w pliku cala_mapa.json "
            "musi być listą albo słownikiem."
        )

    return nodes_by_id


def calculate_slope_percent(
    elevation_difference_m,
    distance_km,
):
    """
    Oblicza średnie nachylenie odcinka w procentach.

    Przykład:
    różnica wysokości 10 m,
    długość odcinka 100 m,
    nachylenie = 10%.
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
    """
    Przelicza dane wysokościowe wszystkich krawędzi.
    """

    nodes = map_data.get("nodes", [])
    edges = map_data.get("edges", [])

    if not isinstance(edges, list):
        raise TypeError(
            "Pole edges w pliku cala_mapa.json "
            "musi być listą."
        )

    nodes_by_id = build_nodes_by_id(nodes)

    statistics = {
        "all_nodes": len(nodes_by_id),
        "nodes_with_elevation": 0,
        "nodes_without_elevation": 0,
        "all_edges": len(edges),
        "updated": 0,
        "missing_node": 0,
        "missing_elevation": 0,
        "invalid_distance": 0,
        "suspicious_slope": 0,
    }

    # Sprawdzenie wszystkich wysokości w nodes
    for node in nodes_by_id.values():
        elevation = as_number(node.get("elevation"))

        if elevation is not None and elevation > 0:
            statistics["nodes_with_elevation"] += 1
        else:
            statistics["nodes_without_elevation"] += 1

    # Przeliczenie wszystkich edges
    for edge in edges:
        if not isinstance(edge, dict):
            continue

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

        if slope_percent > 100:
            statistics["suspicious_slope"] += 1

        edge["elevation_change_m"] = elevation_change
        edge["elevation_gain_m"] = elevation_gain
        edge["elevation_loss_m"] = elevation_loss
        edge["slope_percent"] = slope_percent

        statistics["updated"] += 1

    return statistics


def main():
    """
    Wczytuje cala_mapa.json, przelicza krawędzie
    i bezpiecznie zapisuje wynik.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku: {INPUT_FILE}"
        )

    print("=" * 60)
    print("UZUPEŁNIANIE DANYCH WYSOKOŚCIOWYCH KRAWĘDZI")
    print("=" * 60)
    print(f"Plik wejściowy: {INPUT_FILE}")
    print()

    print("Wczytywanie dużego pliku JSON...")

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        map_data = json.load(file)

    print("Plik został wczytany.")
    print("Sprawdzanie węzłów i przeliczanie krawędzi...")
    print()

    statistics = update_edges(map_data)

    # Najpierw zapis do pliku tymczasowego.
    # Dzięki temu oryginalny plik nie zostanie uszkodzony,
    # gdyby zapis został przerwany.
    temporary_file = OUTPUT_FILE.with_suffix(".tmp")

    print("Zapisywanie pliku tymczasowego...")

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

    os.replace(
        temporary_file,
        OUTPUT_FILE,
    )

    print()
    print("=" * 60)
    print("WYNIKI")
    print("=" * 60)

    print(
        f"Wszystkie węzły: "
        f"{statistics['all_nodes']}"
    )

    print(
        f"Węzły z wysokością: "
        f"{statistics['nodes_with_elevation']}"
    )

    print(
        f"Węzły bez wysokości: "
        f"{statistics['nodes_without_elevation']}"
    )

    print()
    print(
        f"Wszystkie krawędzie: "
        f"{statistics['all_edges']}"
    )

    print(
        f"Uzupełnione krawędzie: "
        f"{statistics['updated']} / "
        f"{statistics['all_edges']}"
    )

    print(
        f"Krawędzie z brakującym węzłem: "
        f"{statistics['missing_node']}"
    )

    print(
        f"Krawędzie bez wysokości węzłów: "
        f"{statistics['missing_elevation']}"
    )

    print(
        f"Krawędzie z nieprawidłową długością: "
        f"{statistics['invalid_distance']}"
    )

    print(
        f"Podejrzane nachylenie powyżej 100%: "
        f"{statistics['suspicious_slope']}"
    )

    print()
    print(f"Zapisany plik: {OUTPUT_FILE}")
    print("=" * 60)

    if statistics["nodes_without_elevation"] > 0:
        print()
        print(
            "UWAGA: Nie wszystkie węzły mają wysokość. "
            "Krawędzie połączone z tymi węzłami "
            "nie mogły zostać przeliczone."
        )

    if statistics["missing_elevation"] > 0:
        print()
        print(
            "UWAGA: Część krawędzi nadal nie ma "
            "poprawnych danych wysokościowych."
        )

    if (
        statistics["nodes_without_elevation"] == 0
        and statistics["missing_node"] == 0
        and statistics["missing_elevation"] == 0
        and statistics["invalid_distance"] == 0
    ):
        print()
        print(
            "Wszystkie węzły i krawędzie zostały "
            "poprawnie przetworzone."
        )


if __name__ == "__main__":
    main()