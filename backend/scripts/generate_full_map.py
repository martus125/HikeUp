import json
import math
import urllib.parse
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
MAP_DIR = BASE_DIR / "mapa"

FULL_MAP_FILE = MAP_DIR / "cala_mapa.json"
GRAPH_NODES_FILE = MAP_DIR / "graph_nodes.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Obszar Tatr: south, west, north, east
BBOX = (49.15, 19.70, 49.36, 20.15)


def haversine_km(lat1, lng1, lat2, lng2):
    earth_radius_km = 6371

    lat1 = math.radians(lat1)
    lng1 = math.radians(lng1)
    lat2 = math.radians(lat2)
    lng2 = math.radians(lng2)

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def difficulty_from_sac_scale(sac_scale):
    levels = {
        "hiking": 1,
        "mountain_hiking": 2,
        "demanding_mountain_hiking": 3,
        "alpine_hiking": 4,
        "demanding_alpine_hiking": 5,
        "difficult_alpine_hiking": 6,
    }

    return levels.get(sac_scale, 1)


def fetch_osm_data():
    south, west, north, east = BBOX

    query = f"""
    [out:json][timeout:180];
    (
      way["highway"~"path|footway|track|steps|pedestrian"]["access"!~"private|no"]({south},{west},{north},{east});
      way["sac_scale"]({south},{west},{north},{east});
    );
    (._;>;);
    out body;
    """

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    request = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={
            "User-Agent": "HikeUp engineering project",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    with urllib.request.urlopen(request, timeout=240) as response:
        return json.loads(response.read().decode("utf-8"))


def build_full_map(osm_data):
    osm_nodes = {}
    osm_ways = []

    for element in osm_data.get("elements", []):
        element_type = element.get("type")

        if element_type == "node":
            node_id = f"node/{element['id']}"
            osm_nodes[node_id] = {
                "id": node_id,
                "name": element.get("tags", {}).get("name", f"Punkt {element['id']}"),
                "type": "waypoint",
                "lat": element["lat"],
                "lng": element["lon"],
                "elevation": 0.0,
            }

        if element_type == "way":
            osm_ways.append(element)

    used_node_ids = set()
    edges = []
    seen_edges = set()

    for way in osm_ways:
        tags = way.get("tags", {})
        way_nodes = [f"node/{node_id}" for node_id in way.get("nodes", [])]

        difficulty = difficulty_from_sac_scale(tags.get("sac_scale"))
        trail_name = tags.get("name", "")
        osm_way_id = f"way/{way['id']}"

        for start_id, end_id in zip(way_nodes, way_nodes[1:]):
            if start_id not in osm_nodes or end_id not in osm_nodes:
                continue

            edge_key = tuple(sorted([start_id, end_id]))

            if edge_key in seen_edges:
                continue

            seen_edges.add(edge_key)
            used_node_ids.add(start_id)
            used_node_ids.add(end_id)

            start_node = osm_nodes[start_id]
            end_node = osm_nodes[end_id]

            distance_km = haversine_km(
                start_node["lat"],
                start_node["lng"],
                end_node["lat"],
                end_node["lng"],
            )

            edges.append(
                {
                    "from": start_id,
                    "to": end_id,
                    "distance_km": round(distance_km, 4),
                    "time_min": round(max(distance_km * 15, 0.1), 2),
                    "elevation_gain_m": 0,
                    "difficulty": difficulty,
                    "osm_way_id": osm_way_id,
                    "trail_name": trail_name,
                    "geometry": [
                        [start_node["lat"], start_node["lng"]],
                        [end_node["lat"], end_node["lng"]],
                    ],
                }
            )

    nodes = [osm_nodes[node_id] for node_id in sorted(used_node_ids)]

    return {
        "nodes": nodes,
        "edges": edges,
    }


def find_nearest_node(point, routing_nodes):
    nearest_id = None
    nearest_distance_km = float("inf")

    for node in routing_nodes:
        distance_km = haversine_km(
            point["lat"],
            point["lng"],
            node["lat"],
            node["lng"],
        )

        if distance_km < nearest_distance_km:
            nearest_distance_km = distance_km
            nearest_id = node["id"]

    return nearest_id, nearest_distance_km


def update_graph_nodes_nearest_routing_nodes(full_map):
    if not GRAPH_NODES_FILE.exists():
        print("Nie znaleziono graph_nodes.json — pomijam aktualizację punktów.")
        return

    with open(GRAPH_NODES_FILE, "r", encoding="utf-8") as file:
        graph_nodes_data = json.load(file)

    points = graph_nodes_data.get("nodes", [])

    for point in points:
        nearest_id, distance_km = find_nearest_node(point, full_map["nodes"])
        point["nearest_routing_node_id"] = nearest_id
        point["distance_to_trail_m"] = round(distance_km * 1000)

    with open(GRAPH_NODES_FILE, "w", encoding="utf-8") as file:
        json.dump({"nodes": points}, file, ensure_ascii=False, indent=2)

    print(f"Zaktualizowano {len(points)} punktów w graph_nodes.json.")


def main():
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    print("Pobieram dane z OpenStreetMap...")
    osm_data = fetch_osm_data()

    print("Buduję pełny graf szlaków...")
    full_map = build_full_map(osm_data)

    with open(FULL_MAP_FILE, "w", encoding="utf-8") as file:
        json.dump(full_map, file, ensure_ascii=False, indent=2)

    print(f"Zapisano: {FULL_MAP_FILE}")
    print(f"Liczba węzłów: {len(full_map['nodes'])}")
    print(f"Liczba krawędzi: {len(full_map['edges'])}")

    print("Aktualizuję najbliższe węzły szlaków dla punktów...")
    update_graph_nodes_nearest_routing_nodes(full_map)

    print("Gotowe.")


if __name__ == "__main__":
    main()