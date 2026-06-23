'''dodawanie trasy do ulubionych i pobieranie ulubionych tras'''
from flask import Blueprint, jsonify, request

from database import add_favorite_route, get_favorite_routes

favorites_bp = Blueprint("favorites", __name__, url_prefix="/api/favorites")


@favorites_bp.route("", methods=["POST"])
def add_favorite():
    data = request.get_json() or {}

    user_id = data.get("user_id")
    route_name = data.get("route_name")

    if not user_id or not route_name:
        return jsonify({"success": False, "message": "Brakuje danych użytkownika lub nazwy trasy."}), 400

    result = add_favorite_route(
        user_id=user_id,
        route_name=route_name,
        start_point_name=data.get("start_point_name"),
        end_point_name=data.get("end_point_name"),
        distance_km=data.get("distance_km"),
        time_min=data.get("time_min"),
        elevation_gain_m=data.get("elevation_gain_m"),
        criterion=data.get("criterion"),
        path=data.get("path"),
    )

    if not result["success"]:
        return jsonify(result), 400

    return jsonify(result), 201


@favorites_bp.route("/<int:user_id>", methods=["GET"])
def get_favorites(user_id):
    result = get_favorite_routes(user_id)
    if not result["success"]:
        return jsonify(result), 400
    return jsonify(result)
