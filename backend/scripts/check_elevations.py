import json
from pathlib import Path

#python scripts/check_elevations.py
#Nadal elevation = 0: 0

BACKEND_DIR = Path(__file__).resolve().parent.parent

MAP_FILE = (
    BACKEND_DIR
    / "mapa"
    / "cala_mapa_with_elevation.json"
)


with MAP_FILE.open("r", encoding="utf-8") as file:
    data = json.load(file)


nodes = data["nodes"]

if isinstance(nodes, dict):
    nodes = list(nodes.values())


completed = 0
missing = 0

for node in nodes:
    elevation = node.get("elevation", 0)

    try:
        elevation = float(elevation)
    except (TypeError, ValueError):
        elevation = 0

    if elevation > 0:
        completed += 1
    else:
        missing += 1


print("Wszystkie węzły:", len(nodes))
print("Z wysokością:", completed)
print("Nadal elevation = 0:", missing)