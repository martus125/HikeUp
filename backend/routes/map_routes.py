"""Endpointy API związane z mapą, punktami i wyznaczaniem trasy."""
from flask import Blueprint, jsonify, request

from algorithms.dijkstra import calculate_route
from services.map_service import (
    build_route_points,
    build_route_positions,
    get_point_by_id,
    load_full_map,
    load_points,
    resolve_routing_node,
)

map_bp = Blueprint("map", __name__, url_prefix="/api")


@map_bp.route("/graph", methods=["GET"])
def get_graph():
    points = load_points()
    return jsonify({"success": True, "nodes": points, "edges": []})


@map_bp.route("/points", methods=["GET"])
def get_points():
    try:
        return jsonify({"success": True, "points": load_points()})
    except Exception as error:
        return jsonify({"success": False, "message": f"Błąd pobierania punktów: {error}"}), 500


@map_bp.route("/full-map", methods=["GET"])
def get_full_map_info():
    full_map = load_full_map()

    return jsonify(
        {
            "success": True,
            "nodes_count": len(full_map["nodes"]),
            "edges_count": len(full_map["edges"]),
        }
    )


@map_bp.route("/route", methods=["POST"])
def route():
    console.log("Rozpoczecie wyznaczania trasy")
    try:
        data = request.get_json() or {}
        start = data.get("start")
        end = data.get("end")
        criterion = data.get("criterion", "time")

        if not start or not end:
            return jsonify(
                {
                    "success": False,
                    "message": "Brakuje punktu początkowego lub końcowego.",
                }
            ), 400

        if start == end:
            return jsonify(
                {
                    "success": False,
                    "message": "Punkt początkowy i końcowy nie mogą być takie same.",
                }
            ), 400

        points = load_points()
        full_map = load_full_map()
        routing_nodes = full_map["nodes"]
        routing_edges = full_map["edges"]

        start_point = get_point_by_id(points, start)
        end_point = get_point_by_id(points, end)

        if start_point is None or end_point is None:
            return jsonify(
                {
                    "success": False,
                    "message": "Nie znaleziono wybranego punktu w graph_nodes.json.",
                    "debug": {"start": start, "end": end},
                }
            ), 404

        routing_start = resolve_routing_node(start_point, routing_nodes)
        routing_end = resolve_routing_node(end_point, routing_nodes)

        if routing_start is None or routing_end is None:
            return jsonify(
                {
                    "success": False,
                    "message": "Nie udało się dopasować punktów do grafu szlaków.",
                    "debug": {
                        "start": start,
                        "end": end,
                        "routing_start": routing_start,
                        "routing_end": routing_end,
                    },
                }
            ), 404

        route_result = calculate_route(
            routing_nodes,
            routing_edges,
            routing_start,
            routing_end,
            criterion,
        )

        if route_result is None:
            return jsonify(
                {
                    "success": False,
                    "message": "Nie znaleziono połączenia między wybranymi punktami.",
                    "debug": {
                        "start": start,
                        "end": end,
                        "routing_start": routing_start,
                        "routing_end": routing_end,
                    },
                }
            ), 404

        path_points = build_route_points(
            route_result["path"],
            routing_nodes,
            start_point=start_point,
            end_point=end_point,
        )
        route_positions = build_route_positions(
            route_result["path"],
            routing_nodes,
            routing_edges,
        )

        return jsonify(
            {
                "success": True,
                "path": path_points,
                "positions": route_positions,
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
            }
        )
    except Exception as error:
        print("BŁĄD /api/route:", error)
        return jsonify(
            {
                "success": False,
                "message": f"Błąd backendu w /api/route: {error}",
            }
        ), 500
