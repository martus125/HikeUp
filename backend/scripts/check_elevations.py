import json
from collections import Counter
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
MAP_FILE = BACKEND_DIR / "mapa" / "cala_mapa.json"


def as_number(value, default=None):
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


print(f"Sprawdzany plik: {MAP_FILE}")

with MAP_FILE.open("r", encoding="utf-8") as file:
    data = json.load(file)


nodes = data.get("nodes", [])
edges = data.get("edges", [])

if isinstance(nodes, dict):
    nodes = list(nodes.values())


nodes_by_id = {
    node.get("id"): node
    for node in nodes
    if isinstance(node, dict) and node.get("id")
}


# --------------------------------------------------
# 1. KONTROLA WYSOKOŚCI WĘZŁÓW
# --------------------------------------------------

nodes_with_elevation = 0
nodes_without_elevation = []

for node in nodes:
    elevation = as_number(node.get("elevation"))

    if elevation is not None and elevation > 0:
        nodes_with_elevation += 1
    else:
        nodes_without_elevation.append({
            "id": node.get("id"),
            "name": node.get("name"),
            "elevation": node.get("elevation"),
        })


# --------------------------------------------------
# 2. KONTROLA KRAWĘDZI
# --------------------------------------------------

edges_with_gain_field = 0
edges_without_gain_field = []
edges_with_zero_gain = 0
edges_with_positive_gain = 0
edges_with_missing_node_elevation = []
edges_with_wrong_values = []

expected_positive_gain = 0
expected_zero_gain = 0

for edge in edges:
    start_id = edge.get("from")
    end_id = edge.get("to")

    start_node = nodes_by_id.get(start_id)
    end_node = nodes_by_id.get(end_id)

    if "elevation_gain_m" in edge:
        edges_with_gain_field += 1
    else:
        edges_without_gain_field.append(edge)

    stored_gain = as_number(edge.get("elevation_gain_m"))

    if stored_gain is None:
        stored_gain = 0

    if stored_gain > 0:
        edges_with_positive_gain += 1
    else:
        edges_with_zero_gain += 1

    if start_node is None or end_node is None:
        edges_with_missing_node_elevation.append({
            "from": start_id,
            "to": end_id,
            "reason": "brak węzła",
        })
        continue

    start_elevation = as_number(start_node.get("elevation"))
    end_elevation = as_number(end_node.get("elevation"))

    if (
        start_elevation is None
        or end_elevation is None
        or start_elevation <= 0
        or end_elevation <= 0
    ):
        edges_with_missing_node_elevation.append({
            "from": start_id,
            "to": end_id,
            "start_elevation": start_elevation,
            "end_elevation": end_elevation,
        })
        continue

    expected_change = round(end_elevation - start_elevation, 1)
    expected_gain = round(max(0, expected_change), 1)

    if expected_gain > 0:
        expected_positive_gain += 1
    else:
        expected_zero_gain += 1

    if abs(stored_gain - expected_gain) > 0.1:
        edges_with_wrong_values.append({
            "from": start_id,
            "to": end_id,
            "stored_gain": stored_gain,
            "expected_gain": expected_gain,
            "start_elevation": start_elevation,
            "end_elevation": end_elevation,
        })


# --------------------------------------------------
# 3. PODSUMOWANIE
# --------------------------------------------------

print()
print("=" * 60)
print("WĘZŁY")
print("=" * 60)

print(f"Wszystkie węzły:             {len(nodes)}")
print(f"Z prawidłową wysokością:      {nodes_with_elevation}")
print(f"Bez prawidłowej wysokości:    {len(nodes_without_elevation)}")

print()
print("=" * 60)
print("KRAWĘDZIE")
print("=" * 60)

print(f"Wszystkie krawędzie:          {len(edges)}")
print(f"Z polem elevation_gain_m:     {edges_with_gain_field}")
print(f"Bez pola elevation_gain_m:    {len(edges_without_gain_field)}")
print(f"Z przewyższeniem większym 0:  {edges_with_positive_gain}")
print(f"Z przewyższeniem równym 0:    {edges_with_zero_gain}")
print(f"Powinny mieć przewyższenie >0:{expected_positive_gain}")
print(f"Powinny mieć przewyższenie 0: {expected_zero_gain}")

print()
print("=" * 60)
print("BŁĘDY")
print("=" * 60)

print(
    "Krawędzie bez dostępnych wysokości węzłów: "
    f"{len(edges_with_missing_node_elevation)}"
)

print(
    "Krawędzie z błędnym elevation_gain_m:      "
    f"{len(edges_with_wrong_values)}"
)


if nodes_without_elevation:
    print()
    print("Pierwsze węzły bez wysokości:")

    for node in nodes_without_elevation[:20]:
        print(node)


if edges_with_wrong_values:
    print()
    print("Pierwsze błędnie przeliczone krawędzie:")

    for edge in edges_with_wrong_values[:20]:
        print(edge)


if edges_with_missing_node_elevation:
    print()
    print("Pierwsze krawędzie bez danych wysokościowych:")

    for edge in edges_with_missing_node_elevation[:20]:
        print(edge)


print()
print("=" * 60)

if (
    len(nodes_without_elevation) == 0
    and len(edges_without_gain_field) == 0
    and len(edges_with_wrong_values) == 0
    and len(edges_with_missing_node_elevation) == 0
):
    print("Plik wysokościowy jest kompletny i spójny.")
else:
    print("Plik wymaga ponownego przeliczenia lub uzupełnienia.")

print("=" * 60)