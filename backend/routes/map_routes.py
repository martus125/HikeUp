# Endpointy API związane z mapą, punktami i wyznaczaniem tras wszystkimi algorytmami
from flask import Blueprint, jsonify, request
import time
import traceback

from algorithms.dijkstra import calculate_route as calculate_dijkstra
from algorithms.astar import calculate_route as calculate_astar
from algorithms.greedy import calculate_route as calculate_greedy
from algorithms.custom import calculate_route as calculate_custom_hikeup

from services.map_service import (
    get_point_by_id,
    load_full_map,
    load_points,
    resolve_routing_node,
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
):
    node_lookup = build_node_lookup(routing_nodes)

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

    return {
        "algorithm": algorithm_key,
        "label": algorithm_label,
        "path": path_points,
        "positions": route_positions,
        "path_ids": path_ids,
        "total_distance_km": get_total_value(
            route_result,
            totals,
            "distance_km",
            "distance",
            default=0,
        ),
        "total_time_min": get_total_value(
            route_result,
            totals,
            "time_min",
            "time",
            default=0,
        ),
        "total_difficulty": get_total_value(
            route_result,
            totals,
            "difficulty",
            default=0,
        ),
        "total_elevation_gain_m": get_total_value(
            route_result,
            totals,
            "elevation_gain_m",
            "total_elevation_gain",
            default=0,
        ),
        "route_weight": metrics.get(
            "route_weight",
            route_result.get("route_weight", 0),
        ),
        "criterion": criterion,
        "metrics": metrics,
        "totals": totals,
        "profile_evaluation": route_result.get(
            "profile_evaluation"
        ),
        "warnings": route_result.get("warnings", []),
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


@map_bp.route("/route", methods=["POST"])
def route():
    """
    Główny endpoint do wyznaczania tras wszystkimi algorytmami.

    Request body powinien zawierać:
    {
        "start": "Zakopane" lub ID,
        "end": "Morskie Oko" lub ID,
        "criterion": "time" | "distance" | "elevation" | "difficulty",
        "user_id": 123
    }
    """
    print(
        "Rozpoczęcie wyznaczania tras wszystkimi algorytmami",
        flush=True,
    )

    try:
        data = request.get_json() or {}

        start = data.get("start")
        end = data.get("end")
        criterion = data.get("criterion", "time")
        user_id = data.get("user_id")

        user_limits = None

        if user_id:
            try:
                from database import get_user_profile
                from models.experience_config import (
                    get_limits,
                    infer_experience_level,
                )

                profile = get_user_profile(user_id)

                experience = infer_experience_level(
                    profile.get("age_years"),
                    profile.get("experience_level"),
                )

                user_limits = get_limits(experience)

                print(
                    f"[LOG] User {user_id}: "
                    f"doświadczenie={experience}, "
                    f"limity={user_limits}",
                    flush=True,
                )
            except Exception as error:
                print(
                    f"[LOG] Błąd pobierania profilu: {error}",
                    flush=True,
                )
                user_limits = None

        if not user_limits:
            from models.experience_config import get_limits

            user_limits = get_limits("intermediate")

            print(
                "[LOG] Brak profilu - używam domyślnych "
                "limitów (intermediate)",
                flush=True,
            )

        if not start or not end:
            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Brakuje punktu początkowego lub końcowego."
                    ),
                }
            ), 400

        if start == end:
            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Punkt początkowy i końcowy "
                        "nie mogą być takie same."
                    ),
                }
            ), 400

        print(
            "Rozpoczęcie ładowania mapy i punktów",
            flush=True,
        )

        points = load_points()
        full_map = load_full_map()

        routing_nodes = full_map["nodes"]
        routing_edges = full_map["edges"]

        print(
            "Rozpoczęcie pobrania punktów startowego i końcowego",
            flush=True,
        )

        start_point = get_point_by_id(points, start)
        end_point = get_point_by_id(points, end)

        if start_point is None or end_point is None:
            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Nie znaleziono wybranego punktu "
                        "w graph_nodes.json."
                    ),
                    "debug": {
                        "start": start,
                        "end": end,
                    },
                }
            ), 404

        print(
            "Rozpoczęcie dopasowania punktów do grafu szlaków",
            flush=True,
        )

        routing_start = resolve_routing_node(
            start_point,
            routing_nodes,
        )
        routing_end = resolve_routing_node(
            end_point,
            routing_nodes,
        )

        if routing_start is None or routing_end is None:
            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Nie udało się dopasować punktów "
                        "do grafu szlaków."
                    ),
                    "debug": {
                        "start": start,
                        "end": end,
                        "routing_start": routing_start,
                        "routing_end": routing_end,
                    },
                }
            ), 404

        routing_start_id = (
            routing_start["id"]
            if isinstance(routing_start, dict)
            else routing_start
        )
        routing_end_id = (
            routing_end["id"]
            if isinstance(routing_end, dict)
            else routing_end
        )

        def count_neighbors(node_id):
            neighbors = []

            for edge in routing_edges:
                edge_from = edge.get("from")
                edge_to = edge.get("to")

                if edge_from == node_id:
                    neighbors.append(edge_to)

                if edge_to == node_id:
                    neighbors.append(edge_from)

            return neighbors

        start_neighbors = count_neighbors(routing_start_id)
        end_neighbors = count_neighbors(routing_end_id)

        print("Routing start:", routing_start, flush=True)
        print("Routing end:", routing_end, flush=True)
        print("Routing start ID:", routing_start_id, flush=True)
        print("Routing end ID:", routing_end_id, flush=True)
        print(
            "Czy start jest w grafie:",
            len(start_neighbors) > 0,
            flush=True,
        )
        print(
            "Czy koniec jest w grafie:",
            len(end_neighbors) > 0,
            flush=True,
        )
        print(
            "Liczba sąsiadów startu:",
            len(start_neighbors),
            flush=True,
        )
        print(
            "Liczba sąsiadów końca:",
            len(end_neighbors),
            flush=True,
        )
        print(
            "Przykładowi sąsiedzi startu:",
            start_neighbors[:5],
            flush=True,
        )
        print(
            "Przykładowi sąsiedzi końca:",
            end_neighbors[:5],
            flush=True,
        )

        print(
            "Rozpoczęcie obliczania tras",
            flush=True,
        )

        routes = []
        algorithm_errors = {}
        algorithm_results = {}

        for algorithm_config in ROUTE_ALGORITHMS:
            algorithm_key = algorithm_config["key"]
            algorithm_label = algorithm_config["label"]
            algorithm_function = algorithm_config["function"]

            algorithm_start_time = time.perf_counter()

            try:
                print("=" * 60, flush=True)
                print(
                    f"START ALGORYTMU: {algorithm_label}",
                    flush=True,
                )

                if algorithm_key == "custom_hikeup":
                    route_result = algorithm_function(
                        routing_nodes,
                        routing_edges,
                        routing_start_id,
                        routing_end_id,
                        criterion,
                        user_limits,
                        algorithm_results.get("dijkstra"),
                    )

                    print(
                        "[LOG] Custom HikeUp otrzymał limity: "
                        f"{user_limits}",
                        flush=True,
                    )
                else:
                    route_result = algorithm_function(
                        routing_nodes,
                        routing_edges,
                        routing_start_id,
                        routing_end_id,
                        criterion,
                    )

                algorithm_elapsed = (
                    time.perf_counter() - algorithm_start_time
                )

                print(
                    f"ALGORYTM ZWRÓCIŁ WYNIK: "
                    f"{algorithm_label}, "
                    f"czas: {algorithm_elapsed:.2f}s",
                    flush=True,
                )

                print(
                    f"[DEBUG] {algorithm_label}: "
                    f"type={type(route_result).__name__}, "
                    f"value_preview={str(route_result)[:300]}",
                    flush=True,
                )

                # Obsługa starszego formatu wyniku:
                # ({...wynik...}, metryki)
                if isinstance(route_result, tuple):
                    print(
                        f"[WARNING] {algorithm_label} "
                        "zwrócił tuple zamiast dict.",
                        flush=True,
                    )

                    if (
                        len(route_result) > 0
                        and isinstance(route_result[0], dict)
                    ):
                        route_result = route_result[0]
                    else:
                        raise TypeError(
                            f"{algorithm_label} zwrócił "
                            "nieprawidłowy format wyniku. "
                            "Oczekiwano słownika."
                        )

                if route_result is None:
                    print(
                        f"{algorithm_label}: "
                        "route_result is None",
                        flush=True,
                    )
                    algorithm_errors[algorithm_key] = (
                        "Nie znaleziono trasy."
                    )
                    continue

                if not isinstance(route_result, dict):
                    raise TypeError(
                        f"{algorithm_label} zwrócił "
                        f"nieprawidłowy typ: "
                        f"{type(route_result).__name__}. "
                        "Oczekiwano dict."
                    )

                if "path" not in route_result:
                    raise ValueError(
                        f"{algorithm_label} zwrócił "
                        "wynik bez pola 'path'."
                    )

                algorithm_results[algorithm_key] = route_result

                print(
                    f"{algorithm_label}: "
                    "rozpoczynam budowanie odpowiedzi",
                    flush=True,
                )

                response_start_time = time.perf_counter()

                route_response = build_single_route_response(
                    algorithm_key=algorithm_key,
                    algorithm_label=algorithm_label,
                    route_result=route_result,
                    routing_nodes=routing_nodes,
                    routing_edges=routing_edges,
                    start_point=start_point,
                    end_point=end_point,
                    criterion=criterion,
                )

                response_elapsed = (
                    time.perf_counter() - response_start_time
                )

                print(
                    f"{algorithm_label}: odpowiedź zbudowana, "
                    f"czas: {response_elapsed:.2f}s",
                    flush=True,
                )

                routes.append(route_response)

                total_elapsed = (
                    time.perf_counter() - algorithm_start_time
                )

                print(
                    f"KONIEC ALGORYTMU: {algorithm_label}, "
                    f"całkowity czas: {total_elapsed:.2f}s",
                    flush=True,
                )

            except Exception as algorithm_error:
                algorithm_elapsed = (
                    time.perf_counter() - algorithm_start_time
                )

                algorithm_errors[algorithm_key] = str(
                    algorithm_error
                )

                print(
                    f"BŁĄD ALGORYTMU {algorithm_label}, "
                    f"po czasie: {algorithm_elapsed:.2f}s",
                    flush=True,
                )
                print(algorithm_error, flush=True)
                traceback.print_exc()

        if not routes:
            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Nie znaleziono połączenia między "
                        "wybranymi punktami żadnym algorytmem."
                    ),
                    "debug": {
                        "start": start,
                        "end": end,
                        "routing_start": routing_start,
                        "routing_end": routing_end,
                        "algorithm_errors": algorithm_errors,
                    },
                }
            ), 404

        primary_route = next(
            (
                route_item
                for route_item in routes
                if route_item["algorithm"] == "dijkstra"
            ),
            routes[0],
        )

        return jsonify(
            {
                "success": True,
                "routes": routes,
                "algorithm_errors": algorithm_errors,
                "start_point": start_point,
                "end_point": end_point,
                "routing_start": routing_start,
                "routing_end": routing_end,
                "criterion": criterion,
                "algorithm": primary_route["algorithm"],
                "label": primary_route["label"],
                "path": primary_route["path"],
                "positions": primary_route["positions"],
                "path_ids": primary_route["path_ids"],
                "total_distance_km": (
                    primary_route["total_distance_km"]
                ),
                "total_time_min": primary_route["total_time_min"],
                "total_difficulty": (
                    primary_route["total_difficulty"]
                ),
                "total_elevation_gain_m": (
                    primary_route["total_elevation_gain_m"]
                ),
                "route_weight": primary_route["route_weight"],
                "metrics": primary_route["metrics"],
                "totals": primary_route["totals"],
            }
        )

    except Exception as error:
        print(
            "BŁĄD /api/route:",
            error,
            flush=True,
        )
        traceback.print_exc()

        return jsonify(
            {
                "success": False,
                "message": (
                    f"Błąd backendu w /api/route: {error}"
                ),
            }
        ), 500
