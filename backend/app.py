from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import math

from algorithms.dijkstra import calculate_route
from database import (
    init_database,
    create_user,
    verify_user,
    add_favorite_route,
    get_favorite_routes,
)

app = Flask(__name__)
CORS(app)
init_database()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAP_DIR = os.path.join(BASE_DIR, "mapa")
POI_FILE = os.path.join(MAP_DIR, "graph_nodes.json")
FULL_MAP_FILE = os.path.join(MAP_DIR, "cala_mapa.json")


def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_points():
    """Punkty charakterystyczne widoczne dla użytkownika w selectach i markerach."""
    return load_json(POI_FILE)


def load_full_map():
    """Pełny graf szlaków używany do obliczania tras."""
    return load_json(FULL_MAP_FILE)


def get_point_by_id(points, point_id):
    if isinstance(points, dict):
        if point_id in points:
            point = points[point_id]

            if isinstance(point, dict):
                return {
                    "id": point.get("id", point_id),
                    **point
                }

        points = points.get("points") or points.get("nodes") or list(points.values())

    for point in points:
        if isinstance(point, dict) and point.get("id") == point_id:
            return point

    return None


def get_node_by_id(nodes, node_id):
    for node in nodes:
        if node.get("id") == node_id:
            return node
    return None


def get_routing_node_id(point):
    if not isinstance(point, dict):
        return point

    return (
        point.get("routing_node_id")
        or point.get("node_id")
        or point.get("nearest_node")
        or point.get("id")
    )


def build_route_points(route_node_ids, routing_nodes, start_point=None, end_point=None):
    """Zamienia ID ścieżki z Dijkstry na współrzędne do Polyline w Leaflet."""
    route_points = []

    # Dodajemy dokładny punkt wybrany przez użytkownika, jeżeli różni się od węzła szlakowego.
    if start_point:
        route_points.append({
            "id": start_point.get("id"),
            "name": start_point.get("name"),
            "type": start_point.get("type"),
            "lat": start_point.get("lat"),
            "lng": start_point.get("lng"),
            "elevation": start_point.get("elevation", 0),
        })

    for node_id in route_node_ids:
        node = get_node_by_id(routing_nodes, node_id)
        if node is not None:
            # Nie dublujemy pierwszego punktu, jeśli ma te same współrzędne.
            route_points.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "type": node.get("type"),
                "lat": node.get("lat"),
                "lng": node.get("lng"),
                "elevation": node.get("elevation", 0),
            })

    if end_point:
        route_points.append({
            "id": end_point.get("id"),
            "name": end_point.get("name"),
            "type": end_point.get("type"),
            "lat": end_point.get("lat"),
            "lng": end_point.get("lng"),
            "elevation": end_point.get("elevation", 0),
        })

    return route_points


@app.route("/")
def home():
    return "Backend HikeUp działa."


@app.route("/api/graph", methods=["GET"])
def get_graph():
    """
    Zostawiamy endpoint dla frontendu, ale zwracamy punkty charakterystyczne.
    Pełnej mapy nie trzeba wysyłać do Reacta, bo trasa ma być liczona w backendzie.
    """
    points = load_points()
    return jsonify({
        "success": True,
        "nodes": points,
        "edges": [],
    })

@app.route("/api/points", methods=["GET"])
def get_points():
    try:
        file_path = os.path.join(BASE_DIR, "mapa", "graph_nodes.json")

        with open(file_path, "r", encoding="utf-8") as file:
            points = json.load(file)

        if isinstance(points, dict):
            if "nodes" in points:
                points = points["nodes"]
            elif "points" in points:
                points = points["points"]
            else:
                points = list(points.values())

        return jsonify({
            "success": True,
            "points": points
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": f"Błąd pobierania punktów: {str(error)}"
        }), 500


@app.route("/api/full-map", methods=["GET"])
def get_full_map_info():
    """Pomocniczy endpoint do sprawdzenia, czy backend widzi nową mapę."""
    full_map = load_full_map()
    return jsonify({
        "success": True,
        "nodes_count": len(full_map.get("nodes", [])),
        "edges_count": len(full_map.get("edges", [])),
    })

def normalize_nodes(nodes):
    if isinstance(nodes, dict):
        return [
            {
                "id": node_id,
                **node
            }
            for node_id, node in nodes.items()
            if isinstance(node, dict)
        ]

    return nodes

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
    r = 6371

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

    return r * c


def find_nearest_routing_node_id(point, routing_nodes):
    point_lat, point_lng = get_lat_lng(point)

    if point_lat is None or point_lng is None:
        return None

    nearest_id = None
    nearest_distance = float("inf")

    for node in routing_nodes:
        if not isinstance(node, dict):
            continue

        node_lat, node_lng = get_lat_lng(node)

        if node_lat is None or node_lng is None:
            continue

        distance = distance_between_points(point_lat, point_lng, node_lat, node_lng)

        if distance < nearest_distance:
            nearest_distance = distance
            nearest_id = node.get("id")

    return nearest_id

@app.route("/api/route", methods=["POST"])
def route():
    try:
        data = request.get_json() or {}

        start = data.get("start")
        end = data.get("end")
        criterion = data.get("criterion", "time")

        if not start or not end:
            return jsonify({
                "success": False,
                "message": "Brakuje punktu początkowego lub końcowego.",
            }), 400

        if start == end:
            return jsonify({
                "success": False,
                "message": "Punkt początkowy i końcowy nie mogą być takie same.",
            }), 400

        points = load_points()
        full_map = load_full_map()

        routing_nodes = normalize_nodes(full_map.get("nodes", []))
        routing_edges = full_map.get("edges", [])

        if isinstance(routing_edges, dict):
            routing_edges = list(routing_edges.values())

        start_point = get_point_by_id(points, start)
        end_point = get_point_by_id(points, end)

        if start_point is None or end_point is None:
            return jsonify({
                "success": False,
                "message": "Nie znaleziono wybranego punktu w graph_nodes.json.",
                "debug": {
                    "start": start,
                    "end": end,
                },
            }), 404

        routing_start = get_routing_node_id(start_point)
        routing_end = get_routing_node_id(end_point)

        routing_node_ids = {
            node.get("id")
            for node in routing_nodes
            if isinstance(node, dict) and node.get("id")
        }

        if routing_start not in routing_node_ids:
            routing_start = find_nearest_routing_node_id(start_point, routing_nodes)

        if routing_end not in routing_node_ids:
            routing_end = find_nearest_routing_node_id(end_point, routing_nodes)

        if routing_start is None or routing_end is None:
            return jsonify({
                "success": False,
                "message": "Nie udało się dopasować punktów do grafu szlaków.",
                "debug": {
                    "start": start,
                    "end": end,
                    "routing_start": routing_start,
                    "routing_end": routing_end,
                },
            }), 404

        route_result = calculate_route(
            routing_nodes,
            routing_edges,
            routing_start,
            routing_end,
            criterion,
        )

        if route_result is None:
            return jsonify({
                "success": False,
                "message": "Nie znaleziono połączenia między wybranymi punktami.",
                "debug": {
                    "start": start,
                    "end": end,
                    "routing_start": routing_start,
                    "routing_end": routing_end,
                },
            }), 404

        path_points = build_route_points(
            route_result["path"],
            routing_nodes,
            start_point=start_point,
            end_point=end_point,
        )

        return jsonify({
            "success": True,
            "path": path_points,
            "path_ids": route_result["path"],
            "start_point": start_point,
            "end_point": end_point,
            "routing_start": routing_start,
            "routing_end": routing_end,
            "total_distance_km": route_result.get("total_distance_km", 0),
            "total_time_min": route_result.get("total_time_min", 0),
            "total_difficulty": route_result.get("total_difficulty", 0),
            "total_elevation_gain_m": route_result.get("total_elevation_gain_m", 0),
            "route_weight": route_result.get("route_weight", 0),
            "criterion": criterion,
        })

    except Exception as error:
        print("BŁĄD /api/route:", error)

        return jsonify({
            "success": False,
            "message": f"Błąd backendu w /api/route: {str(error)}"
        }), 500

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "Uzupełnij wszystkie pola formularza.",
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Hasło powinno mieć co najmniej 6 znaków.",
        }), 400

    result = create_user(name, email, password)
    if not result["success"]:
        return jsonify(result), 400

    return jsonify({
        "success": True,
        "message": "Konto zostało utworzone. Możesz się zalogować.",
    })


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Podaj email i hasło.",
        }), 400

    result = verify_user(email, password)
    if not result["success"]:
        return jsonify(result), 401

    return jsonify({
        "success": True,
        "message": "Zalogowano pomyślnie.",
        "user": result["user"],
    })


@app.route("/api/favorites", methods=["POST"])
def add_favorite():
    data = request.get_json() or {}

    user_id = data.get("user_id")
    route_name = data.get("route_name")
    start_point_name = data.get("start_point_name")
    end_point_name = data.get("end_point_name")
    distance_km = data.get("distance_km")
    time_min = data.get("time_min")
    elevation_gain_m = data.get("elevation_gain_m")
    criterion = data.get("criterion")
    path = data.get("path")

    if not user_id or not route_name:
        return jsonify({
            "success": False,
            "message": "Brakuje danych użytkownika lub nazwy trasy.",
        }), 400

    result = add_favorite_route(
        user_id,
        route_name,
        start_point_name,
        end_point_name,
        distance_km,
        time_min,
        elevation_gain_m,
        criterion,
        path,
    )

    if not result["success"]:
        return jsonify(result), 400

    return jsonify(result), 201


@app.route("/api/favorites/<int:user_id>", methods=["GET"])
def get_favorites(user_id):
    result = get_favorite_routes(user_id)
    if not result["success"]:
        return jsonify(result), 400
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
