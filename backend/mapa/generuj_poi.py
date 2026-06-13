import osmnx as ox
import pandas as pd
import json
import math

# --- 1. FUNKCJA DO OBLICZANIA ODLEGŁOŚCI ---
# Oblicza odległość w linii prostej między dwoma punktami na kuli ziemskiej (Haversine)
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Promień Ziemi w metrach
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- 2. WCZYTANIE GRAFU TRAS ---
print("Wczytywanie grafu tras z pliku 'tatry_graph.json'...")
try:
    with open("tatry_graph.json", "r", encoding="utf-8") as f:
        routing_data = json.load(f)
    routing_nodes = routing_data.get("nodes", [])
    print(f"Pomyślnie wczytano {len(routing_nodes)} węzłów tras.")
except FileNotFoundError:
    print("BŁĄD: Nie znaleziono pliku 'tatry_graph.json'. Najpierw uruchom pierwszy skrypt!")
    exit()

# --- 3. POBRANIE PUNKTÓW POI Z OSM ---
print("Pobieranie punktów charakterystycznych (POI) z obszaru Tatr...")
# Definiujemy, czego dokładnie szukamy
tags_to_find = {
    'natural': ['peak', 'saddle', 'water'], # Szczyty, przełęcze, jeziora (np. Morskie Oko)
    'tourism': ['alpine_hut', 'guest_house', 'viewpoint'], # Schroniska, punkty widokowe
    'waterway': ['waterfall'] # Wodospady (np. Wodogrzmoty Mickiewicza)
}

pois = ox.features_from_place("Tatrzański Park Narodowy, Polska", tags=tags_to_find)
print(f"Pobrano {len(pois)} obiektów. Przetwarzanie i parowanie z trasami...")

# --- 4. PRZETWARZANIE DANYCH ---
poi_list = []

for idx, row in pois.iterrows():
    # Odczytujemy typ (element_type) i osmid z MultiIndexu
    element_type, osmid = idx
    
    # Przechwytujemy nazwę. Odrzucamy obiekty bez nazwy, bo użytkownik i tak ich nie wyszuka.
    name = row.get("name:pl")
    if pd.isna(name): name = row.get("name")
    if pd.isna(name): name = row.get("alt_name")
    
    if pd.isna(name):
        continue  # Pomijamy bezimienne kamienie czy małe jeziorka

    # Ustalamy typ POI na podstawie dostępnych kolumn
    poi_type = "poi"
    if not pd.isna(row.get("natural")): poi_type = row.get("natural")
    elif not pd.isna(row.get("tourism")): poi_type = row.get("tourism")
    elif not pd.isna(row.get("waterway")): poi_type = row.get("waterway")

    # Ujednolicamy geometrię do jednego punktu (centroid dla wielokątów, np. schronisk)
    geom = row.geometry.centroid
    lat = geom.y
    lng = geom.x

    # Parsujemy wysokość
    ele = 0.0
    if 'ele' in row and not pd.isna(row['ele']):
        try:
            ele = float(row['ele'])
        except ValueError:
            ele = 0.0

    # --- ZNAJDOWANIE NAJBLIŻSZEGO WĘZŁA TRASY ---
    # Szukamy, do którego węzła z pliku 'tatry_graph.json' mamy najbliżej w linii prostej
    nearest_node_id = None
    min_distance = float('inf')
    
    for r_node in routing_nodes:
        dist = haversine_distance(lat, lng, r_node["lat"], r_node["lng"])
        if dist < min_distance:
            min_distance = dist
            nearest_node_id = r_node["id"]

    poi_entry = {
        "id": f"{element_type}/{osmid}",
        "name": str(name),
        "type": str(poi_type),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "elevation": ele,
        "nearest_routing_node_id": nearest_node_id,
        "distance_to_trail_m": round(min_distance) # Dodatkowy parametr pomocniczy
    }
    
    poi_list.append(poi_entry)

# Sortujemy listę alfabetycznie dla lepszego efektu
poi_list = sorted(poi_list, key=lambda k: k['name'])

# --- 5. ZAPIS DO PLIKU ---
output_data = {"nodes": poi_list}

with open("tatry_POI.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f"Sukces! Zapisano {len(poi_list)} punktów charakterystycznych do pliku 'tatry_POI.json'.")