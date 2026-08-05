"""Sprawdza kompletność i wiarygodność danych wysokościowych mapy."""

import json
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
MAP_FILE = BACKEND_DIR / "mapa" / "cala_mapa.json"
MAX_REASONABLE_SLOPE_PERCENT = 100


def as_number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main():
    with MAP_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if isinstance(nodes, dict):
        nodes = list(nodes.values())

    completed_nodes = sum(
        as_number(node.get("elevation"), 0) > 0
        for node in nodes
    )
    missing_edge_data = sum(
        any(
            key not in edge
            for key in (
                "elevation_change_m",
                "elevation_gain_m",
                "elevation_loss_m",
                "slope_percent",
            )
        )
        for edge in edges
    )
    suspicious_slopes = [
        as_number(edge.get("slope_percent"), 0)
        for edge in edges
        if as_number(edge.get("slope_percent"), 0)
        > MAX_REASONABLE_SLOPE_PERCENT
    ]

    print(f"Plik: {MAP_FILE}")
    print(f"Wszystkie węzły: {len(nodes)}")
    print(f"Węzły z wysokością: {completed_nodes}")
    print(
        "Węzły bez wysokości: "
        f"{len(nodes) - completed_nodes}"
    )
    print(f"Wszystkie krawędzie: {len(edges)}")
    print(
        "Krawędzie bez kompletu danych wysokościowych: "
        f"{missing_edge_data}"
    )
    print(
        f"Nachylenia > {MAX_REASONABLE_SLOPE_PERCENT}%: "
        f"{len(suspicious_slopes)}"
    )

    if suspicious_slopes:
        print(
            "Największe zapisane nachylenie: "
            f"{max(suspicious_slopes):.2f}%"
        )
        print(
            "Algorytm ogranicza wpływ tych wartości w czasie działania. "
            "Aby trwale naprawić dane, ponownie pobierz wysokości, a potem "
            "uruchom fill_edge_elevation_data.py."
        )


if __name__ == "__main__":
    main()
