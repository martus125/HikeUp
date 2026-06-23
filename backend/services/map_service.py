"""Logika związana z mapą, punktami i geometrią trasy."""
import json
import math

from config import FULL_MAP_FILE, POI_FILE


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_collection(data, key_names=("points", "nodes")):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in key_names:
            if isinstance(data.get(key), list):
                return data[key]

            if isinstance(data.get(key), dict):
                return [
                    {"id": item_id, **item}
                    for item_id, item in data[key].items()
                    if isinstance(item, dict)
                ]

        return [
            {"id": item_id, **item}
            for item_id, item in data.items()
            if isinstance(item, dict)
        ]

    return []


def load_points():
    return normalize_collection(load_json(POI_FILE))


def load_full_map():
    data = load_json(FULL_MAP_FILE)

    return {
        "nodes": normalize_collection(data.get("nodes", [])),
        "edges": normalize_collection(data.get("edges", []), key_names=("edges",)),
    }


def get_point_by_id(points, point_id):
    for point in normalize_collection(points):
        if point.get("id") == point_id:
            return point

    return None


def get_node_by_id(nodes, node_id):
    for node in nodes:
        if node.get("id") == node_id:
            return node

    return None


def get_node_map(nodes):
    return {node.get("id"): node for node in nodes if node.get("id")}


def get_routing_node_id(point):
    if not isinstance(point, dict):
        return point

    return (
        point.get("nearest_routing_node_id")
        or point.get("routing_node_id")
        or point.get("node_id")
        or point.get("nearest_node")
        or point.get("id")
    )


def get_lat_lng(point):
    if not isinstance(point, dict):
        return None, None

    lat = point.get("lat") or point.get("latitude")
    lng = point.get("lng") or point.get("lon") or point.get("longitude")

    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None


def distance_between_points(lat1, lng1, lat2, lng2):
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


def find_nearest_routing_node_id(point, routing_nodes):
    point_lat, point_lng = get_lat_lng(point)

    if point_lat is None or point_lng is None:
        return None

    nearest_id = None
    nearest_distance = float("inf")

    for node in routing_nodes:
        node_lat, node_lng = get_lat_lng(node)

        if node_lat is None or node_lng is None:
            continue

        distance = distance_between_points(point_lat, point_lng, node_lat, node_lng)

        if distance < nearest_distance:
            nearest_distance = distance
            nearest_id = node.get("id")

    return nearest_id


def resolve_routing_node(point, routing_nodes):
    routing_node_id = get_routing_node_id(point)
    routing_node_ids = {node.get("id") for node in routing_nodes if node.get("id")}

    if routing_node_id not in routing_node_ids:
        routing_node_id = find_nearest_routing_node_id(point, routing_nodes)

    return routing_node_id


def format_route_point(point):
    lat, lng = get_lat_lng(point)

    return {
        "id": point.get("id"),
        "name": point.get("name"),
        "type": point.get("type"),
        "lat": lat,
        "lng": lng,
        "elevation": point.get("elevation", 0),
    }


def build_route_points(route_node_ids, routing_nodes, start_point=None, end_point=None):
    """Lista punktów do opisu trasy w panelu bocznym.

    Zostawiamy tu wybrany punkt startu i końca, żeby użytkownik widział,
    że trasa dotyczy dokładnie tych miejsc, które wybrał.
    """
    route_points = []

    if start_point:
        route_points.append(format_route_point(start_point))

    node_map = get_node_map(routing_nodes)

    for node_id in route_node_ids:
        node = node_map.get(node_id)
        if node is not None:
            route_points.append(format_route_point(node))

    if end_point:
        route_points.append(format_route_point(end_point))

    return remove_duplicate_points(route_points)


def remove_duplicate_points(points):
    result = []

    for point in points:
        if not point:
            continue

        previous = result[-1] if result else None
        if previous and previous.get("id") == point.get("id"):
            continue

        result.append(point)

    return result


def find_edge_between_nodes(edges, start_id, end_id):
    for edge in edges:
        edge_start = edge.get("from")
        edge_end = edge.get("to")

        if edge_start == start_id and edge_end == end_id:
            return edge, False

        if edge_start == end_id and edge_end == start_id:
            return edge, True

    return None, False


def normalize_position(position):
    if isinstance(position, dict):
        lat = position.get("lat") or position.get("latitude")
        lng = position.get("lng") or position.get("lon") or position.get("longitude")
    elif isinstance(position, (list, tuple)) and len(position) >= 2:
        lat = position[0]
        lng = position[1]
    else:
        return None

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(lat) or not math.isfinite(lng):
        return None

    return [lat, lng]


def extract_edge_geometry(edge, reversed_direction=False):
    """Zwraca geometrię krawędzi, jeżeli w danych mapy jest dostępna.

    Obecny plik cala_mapa.json ma tylko pola "from" i "to".
    Ta funkcja obsługuje jednak też przyszły wariant z dokładną geometrią,
    np. geometry/path/coordinates.
    """
    if not isinstance(edge, dict):
        return []

    geometry = (
        edge.get("geometry")
        or edge.get("path")
        or edge.get("points")
        or edge.get("coordinates")
    )

    if not isinstance(geometry, list):
        return []

    positions = [normalize_position(position) for position in geometry]
    positions = [position for position in positions if position is not None]

    if reversed_direction:
        positions.reverse()

    return positions


def append_position(positions, position):
    if position is None:
        return

    if positions and positions[-1] == position:
        return

    positions.append(position)


def build_route_positions(route_node_ids, routing_nodes, routing_edges):
    """Współrzędne używane do rysowania linii trasy na mapie.

    Ważne: nie dodajemy tutaj surowych współrzędnych punktów wybranych przez
    użytkownika, jeżeli są poza szlakiem albo są środkiem jeziora.
    Linia jest rysowana po węzłach grafu szlaków.
    """
    positions = []
    node_map = get_node_map(routing_nodes)

    for index, node_id in enumerate(route_node_ids):
        current_node = node_map.get(node_id)
        current_position = normalize_position(current_node)

        if index == 0:
            append_position(positions, current_position)
            continue

        previous_id = route_node_ids[index - 1]
        edge, reversed_direction = find_edge_between_nodes(routing_edges, previous_id, node_id)
        edge_positions = extract_edge_geometry(edge, reversed_direction)

        if edge_positions:
            for edge_position in edge_positions:
                append_position(positions, edge_position)
        else:
            append_position(positions, current_position)

    return positions
