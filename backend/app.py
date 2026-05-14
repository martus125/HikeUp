from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

from algorithms.dijkstra import calculate_route
from database import init_database, create_user, verify_user

app = Flask(__name__)
CORS(app)

init_database()

def load_graph():
    file_path = os.path.join(os.path.dirname(__file__), "graph.json")

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_point_by_id(nodes, point_id):
    for node in nodes:
        if node["id"] == point_id:
            return node

    return None


@app.route("/")
def home():
    return "Backend HikeUp działa."


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "Uzupełnij wszystkie pola formularza."
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Hasło powinno mieć co najmniej 6 znaków."
        }), 400

    result = create_user(name, email, password)

    if not result["success"]:
        return jsonify(result), 400

    return jsonify({
        "success": True,
        "message": "Konto zostało utworzone. Możesz się zalogować."
    })


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Podaj email i hasło."
        }), 400

    result = verify_user(email, password)

    if not result["success"]:
        return jsonify(result), 401

    return jsonify({
        "success": True,
        "message": "Zalogowano pomyślnie.",
        "user": result["user"]
    })


@app.route("/api/points", methods=["GET"])
def get_points():
    graph = load_graph()

    return jsonify({
        "success": True,
        "points": graph["nodes"]
    })


@app.route("/api/route", methods=["POST"])
def route():
    data = request.get_json()

    start = data.get("start")
    end = data.get("end")
    criterion = data.get("criterion")

    if not start or not end or not criterion:
        return jsonify({
            "success": False,
            "message": "Brakuje wymaganych danych."
        }), 400

    if start == end:
        return jsonify({
            "success": False,
            "message": "Punkt początkowy i końcowy nie mogą być takie same."
        }), 400

    graph = load_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    route_result = calculate_route(nodes, edges, start, end, criterion)

    if route_result is None:
        return jsonify({
            "success": False,
            "message": "Nie znaleziono połączenia między wybranymi punktami."
        }), 404

    path_points = []

    for point_id in route_result["path"]:
        point = get_point_by_id(nodes, point_id)

        if point is not None:
            path_points.append({
                "id": point["id"],
                "name": point["name"],
                "lat": point["lat"],
                "lng": point["lng"]
            })

    return jsonify({
    "success": True,
    "path": path_points,
    "total_distance_km": route_result["total_distance_km"],
    "total_time_min": route_result["total_time_min"],
    "total_difficulty": route_result["total_difficulty"],
    "total_elevation_gain_m": route_result["total_elevation_gain_m"],
    "route_weight": route_result["route_weight"],
    "criterion": criterion
})


if __name__ == "__main__":
    app.run(debug=True)