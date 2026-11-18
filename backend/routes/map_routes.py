from auth import current_user_id
from validation import route_input, ValidationError
# Endpointy API związane z mapą, punktami i wyznaczaniem tras wszystkimi algorytmami
from flask import Blueprint, current_app, jsonify, request
import time

from algorithms.dijkstra import calculate_route as calculate_dijkstra
from algorithms.astar import calculate_route as calculate_astar
from algorithms.greedy import calculate_route as calculate_greedy
from algorithms.custom import calculate_route as calculate_custom_hikeup
from algorithms.weights import validate_criterion
from models.experience_config import (
    apply_shelter_preference,
    criterion_from_route_preference,
    get_limits,
    infer_experience_level,
)

from services.map_service import (
    load_full_map,
    load_points,
    resolve_routing_node,
)
from services.routing_context import (
    load_routing_context,
    routing_context_is_cached,
)

map_bp = Blueprint("map", __name__, url_prefix="/api")


ROUTE_ALGORITHMS = [
    {
        "key": "dijkstra",
        "label": "Dijkstra",
        "function": calculate_dijkstra,
    },
    {
        "key": "astar",
        "label": "A*",
        "function": calculate_astar,
    },
    {
        "key": "greedy",
        "label": "Greedy Best-First Search",
        "function": calculate_greedy,
    },
    {
        "key": "custom_hikeup",
        "label": "Custom HikeUp",
        "function": calculate_custom_hikeup,
    },
]


def get_total_value(route_result, totals, *keys, default=0):
    for key in keys:
        if key in totals and totals.get(key) is not None:
            return totals.get(key)

        if key in route_result and route_result.get(key) is not None:
            return route_result.get(key)

    return default


def build_route_points_fast(
    path_ids,
    node_lookup,
    start_point=None,
    end_point=None,
):
    path_points = []

    for node_id in path_ids:
        node = node_lookup.get(node_id)

        if node is None:
            continue

        path_points.append(
            {
                "id": node_id,
                "name": node.get("name", ""),
                "type": node.get("type", "route_node"),
                "lat": node.get("lat"),
                "lng": node.get("lng", node.get("lon")),
                "elevation": node.get("elevation"),
            }
        )

    if path_points and start_point:
        path_points[0]["name"] = start_point.get(
            "name",
            path_points[0].get("name", ""),
        )

    if path_points and end_point:
        path_points[-1]["name"] = end_point.get(
            "name",
            path_points[-1].get("name", ""),
        )

    return path_points


def build_route_positions_fast(path_ids, node_lookup):
    positions = []

    for node_id in path_ids:
        node = node_lookup.get(node_id)

        if node is None:
            continue

        lat = node.get("lat")
        lng = node.get("lng", node.get("lon"))

        if lat is None or lng is None:
            continue

        positions.append([lat, lng])

    return positions


def build_node_lookup(routing_nodes):
    if isinstance(routing_nodes, dict):
        return routing_nodes

    node_lookup = {}

    for node in routing_nodes:
        node_id = node.get("id")

        if node_id is not None:
            node_lookup[node_id] = node

    return node_lookup


def build_single_route_response(
    algorithm_key,
    algorithm_label,
    route_result,
    routing_nodes,
    routing_edges,
    start_point,
    end_point,
    criterion,
    node_lookup=None,
):
    node_lookup = node_lookup or build_node_lookup(routing_nodes)

    path_ids = route_result["path"]

    path_points = build_route_points_fast(
        path_ids,
        node_lookup,
        start_point=start_point,
        end_point=end_point,
    )

    route_positions = build_route_positions_fast(
        path_ids,
        node_lookup,
    )

    totals = route_result.get("totals", {})
    metrics = route_result.get("metrics", {})

    distance = get_total_value(
        route_result,
        totals,
        "distance_km",
        "distance",
        default=0,
    )
    route_time = get_total_value(
        route_result,
        totals,
        "time_min",
        "time",
        default=0,
    )
    difficulty = get_total_value(
        route_result,
        totals,
        "difficulty",
        default=0,
    )
    elevation_gain = get_total_value(
        route_result,
        totals,
        "elevation_gain_m",
        "total_elevation_gain",
        default=0,
    )
    route_weight = metrics.get(
        "route_weight",
        route_result.get("route_weight", 0),
    )

    return {
        "algorithm": algorithm_key,
        "label": algorithm_label,
        "path": path_points,
        "positions": route_positions,
        "path_ids": path_ids,
        "total_distance_km": distance,
        "total_time_min": route_time,
        "total_difficulty": difficulty,
        "total_elevation_gain_m": elevation_gain,
        "total_elevation_loss_m": totals.get("elevation_loss_m", 0),
        "route_weight": route_weight,
        "max_slope_percent": totals.get("max_slope_percent", 0),
        "average_slope_percent": totals.get("average_slope_percent", 0),
        "shelters_count": totals.get("shelters_count", 0),

        # Zachowane aliasy pozwalają obsłużyć starsze i nowsze komponenty UI.
        "distance": distance,
        "time": route_time,
        "difficulty": difficulty,
        "elevation": elevation_gain,
        "routeWeight": route_weight,
        "criterion": criterion,
        "metrics": metrics,
        "totals": totals,
        "profile_evaluation": route_result.get("profile_evaluation") or {},
        "warnings": route_result.get("warnings", []),
        "recommendation_status": route_result.get(
            "recommendation_status",
            "recommended",
        ),
        "personalization_enabled": route_result.get(
            "personalization_enabled",
            True,
        ),
        "message": route_result.get("message"),
    }


@map_bp.route("/graph", methods=["GET"])
def get_graph():
    points = load_points()
    return jsonify({"success": True, "nodes": points, "edges": []})


@map_bp.route("/points", methods=["GET"])
def get_points():
    try:
        return jsonify({"success": True, "points": load_points()})
    except Exception as error:
        return jsonify(
            {
                "success": False,
                "message": f"Błąd pobierania punktów: {error}",
            }
        ), 500


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


def load_route_profile():
    """Gość korzysta z trybu ogólnego; profil pobieramy wyłącznie z sesji."""
    user_id = current_user_id()
    if user_id is None:
        return {}, False
    try:
        from database import get_user_profile

        return get_user_profile(user_id), True
    except Exception:
        current_app.logger.exception("Nie udało się pobrać profilu do planowania trasy")
        return {}, False


@map_bp.route("/route", methods=["POST"])
def route():
    """Wyznacza cztery warianty dla ID startu, celu i opcjonalnego kryterium."""
    try:
        data = request.get_json() or {}
        try:
            route_input(data)
        except (ValidationError, ValueError) as error:
            return jsonify(success=False, message=str(error)), 400

        start, end = data["start"], data["end"]
        profile, personalization_enabled = load_route_profile()
        criterion = data.get("criterion") or criterion_from_route_preference(
            profile.get("route_preference"), default="time",
        )
        validate_criterion(criterion)
        experience = infer_experience_level(profile.get("age_years"), profile.get("experience_level"))
        user_limits = apply_shelter_preference(
            get_limits(experience), profile.get("prefer_shelters", False),
        )

        context_was_cached = routing_context_is_cached()
        context_start_time = time.perf_counter()
        context = load_routing_context()
        context_load_time_ms = round((time.perf_counter() - context_start_time) * 1000, 3)
        start_point = context.points_by_id.get(start)
        end_point = context.points_by_id.get(end)
        if start_point is None or end_point is None:
            return jsonify(success=False, message=(
                "Wybrany punkt nie istnieje lub nie jest dostępny do planowania. "
                "Wybierz punkt z aktualnej listy przy sieci szlaków."
            )), 404

        routing_start = resolve_routing_node(start_point, context.nodes, context.node_ids)
        routing_end = resolve_routing_node(end_point, context.nodes, context.node_ids)
        if routing_start is None or routing_end is None:
            return jsonify(success=False, message=(
                "Nie znaleziono pobliskiego węzła szlaku dla wybranych punktów. "
                "Nie można wyznaczyć trasy do odległego miejsca poza siecią."
            )), 404

        routes, algorithm_results, algorithm_errors = [], {}, {}
        for config in ROUTE_ALGORITHMS:
            key = config["key"]
            try:
                arguments = (context.nodes, context.edges, routing_start, routing_end, criterion)
                if key == "custom_hikeup":
                    result = config["function"](
                        *arguments, user_limits=user_limits,
                        baseline_route=algorithm_results.get("dijkstra"),
                        points=context.points, routing_context=context,
                        personalization_enabled=personalization_enabled,
                    )
                else:
                    result = config["function"](
                        *arguments, points=context.points, routing_context=context,
                    )
                if result is None:
                    algorithm_errors[key] = "Nie znaleziono trasy."
                    continue
                if not isinstance(result, dict) or "path" not in result:
                    raise TypeError("Algorytm musi zwrócić słownik z polem 'path'.")
                algorithm_results[key] = result
                routes.append(build_single_route_response(
                    algorithm_key=key, algorithm_label=config["label"], route_result=result,
                    routing_nodes=context.nodes, routing_edges=context.edges,
                    start_point=start_point, end_point=end_point, criterion=criterion,
                    node_lookup=context.nodes_by_id,
                ))
            except Exception as error:
                algorithm_errors[key] = str(error)
                current_app.logger.exception("Błąd algorytmu %s", key)

        if not routes:
            return jsonify(success=False, message=(
                "Nie znaleziono połączenia między wybranymi punktami przy uwzględnieniu "
                "ograniczeń dostępu. Odcinki sezonowe i warunkowe są wyłączone z planowania."
            ), debug={"algorithm_errors": algorithm_errors}), 404

        primary = next((item for item in routes if item["algorithm"] == "dijkstra"), routes[0])
        # Pola głównej trasy pozostają dostępne dla obecnego interfejsu i klientów API.
        primary_fields = {key: primary[key] for key in (
            "algorithm", "label", "path", "positions", "path_ids", "total_distance_km",
            "total_time_min", "total_difficulty", "total_elevation_gain_m", "route_weight", "metrics",
        )}
        return jsonify(
            success=True, routes=routes, algorithm_errors=algorithm_errors,
            start_point=start_point, end_point=end_point,
            routing_start=routing_start, routing_end=routing_end, criterion=criterion,
            personalization_enabled=personalization_enabled,
            preprocessing_metrics={
                "routing_context_load_ms": context_load_time_ms,
                "routing_context_cache_hit": context_was_cached,
                "nodes_count": len(context.nodes_by_id), "edges_count": len(context.edges),
            }, totals=primary["totals"], **primary_fields,
        )
    except Exception as error:
        current_app.logger.exception("Błąd endpointu /api/route")
        return jsonify(success=False, message=f"Błąd backendu w /api/route: {error}"), 500
