import osmnx as ox
import json

# --- 1. ROZSZERZENIE KONFIGURACJI ---
# Dodajemy tagi, które OSMnx standardowo ignoruje, a które zawierają ważne dane o terenie
tags_to_keep = ['ele', 'natural', 'tourism', 'place', 'waterway', 'name', 'name:pl', 'alt_name']
for tag in tags_to_keep:
    if tag not in ox.settings.useful_tags_node:
        ox.settings.useful_tags_node.append(tag)

custom_filter = '["highway"~"path|footway|track"]["foot"!~"no"]'

print("Pobieranie grafu szlaków z OpenStreetMap dla Tatrzańskiego Parku Narodowego...")
print("(To może potrwać kilkanaście sekund...)")

G = ox.graph_from_place(
    "Tatrzański Park Narodowy, Polska", 
    custom_filter=custom_filter, 
    retain_all=True
)

print(f"Pobrano graf! Liczba węzłów przed optymalizacją: {len(G.nodes)}")

# Funkcja obliczająca czas przejścia regułą Naismitha
def calculate_hiking_time(distance_meters, elevation_gain_meters):
    if elevation_gain_meters < 0: 
        elevation_gain_meters = 0
    
    # 5 km/h na płaskim + 1h na każde 600m podejścia
    time_flat_min = (distance_meters / 5000.0) * 60.0
    time_climb_min = (elevation_gain_meters / 600.0) * 60.0
    
    return round(time_flat_min + time_climb_min)

# Funkcja bezpiecznego parsowania wysokości
def parse_elevation(ele_data):
    if ele_data:
        try:
            return float(ele_data)
        except ValueError:
            return 0.0
    return 0.0

print("Konwersja na JSON...")

nodes_dict = {}
edges_list = []

# --- 2. ULEPSZONE MAPOWANIE WĘZŁÓW ---
for node_id, data in G.nodes(data=True):
    # Logika wyciągania nazwy: polska nazwa -> główna -> alternatywna -> ID
    node_name = data.get("name:pl") or data.get("name") or data.get("alt_name") or f"Punkt {node_id}"
    
    # Logika wyciągania typu: turystyka -> natura -> infrastruktura
    node_type = (
        data.get("tourism") or 
        data.get("natural") or 
        data.get("place") or 
        data.get("waterway") or
        data.get("highway") or 
        "waypoint"
    )

    nodes_dict[node_id] = {
        "id": f"node/{node_id}",
        "name": node_name,
        "type": node_type,
        "lat": data['y'],
        "lng": data['x'],
        "elevation": parse_elevation(data.get("ele"))
    }

# --- 3. MAPOWANIE KRAWĘDZI ---
for u, v, key, data in G.edges(keys=True, data=True):
    ele_start = nodes_dict[u]["elevation"]
    ele_end = nodes_dict[v]["elevation"]
    
    # Obliczamy przewyższenie (zawsze dodatnie dla podejścia)
    elevation_gain = max(0, ele_end - ele_start)
    
    distance_km = round(data.get("length", 0) / 1000.0, 3)
    time_min = calculate_hiking_time(data.get("length", 0), elevation_gain)
    
    edge_entry = {
        "from": f"node/{u}",
        "to": f"node/{v}",
        "distance_km": distance_km,
        "time_min": time_min,
        "elevation_gain_m": round(elevation_gain),
        "difficulty": "unknown"
    }
    edges_list.append(edge_entry)

# --- 4. ZAPIS ---
output_data = {
    "nodes": list(nodes_dict.values()),
    "edges": edges_list
}

with open("tatry_graph.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f"Sukces! Wygenerowano 'tatry_graph.json'.")
print(f"Ilość węzłów: {len(output_data['nodes'])}")
print(f"Ilość krawędzi: {len(output_data['edges'])}")