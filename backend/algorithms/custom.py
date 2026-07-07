import heapq
from time import perf_counter

from algorithms.common import (
    SearchMetrics,
    build_graph,
    reconstruct_path,
    calculate_route_totals,
)
from algorithms.weights import as_number
from algorithms.heuristics import build_node_map, heuristic


def custom_hikeup_edge_weight(edge, criterion="time"):
    """
    Funkcja kosztu dla autorskiego algorytmu Custom HikeUp.

    Algorytm uwzględnia cechy ważne dla tras górskich:
    dystans, czas przejścia, przewyższenie, trudność,
    nachylenie oraz bezpieczeństwo.
    """
    distance = as_number(edge.get("distance_km"), 0)
    time = as_number(edge.get("time_min"), 0)
    elevation = as_number(edge.get("elevation_gain_m"), 0)
    difficulty = as_number(edge.get("difficulty"), 1)

    # Te pola mogą jeszcze nie istnieć w danych,
    # dlatego mają wartości domyślne.
    slope = as_number(edge.get("slope_percent"), 0)
    safety = as_number(edge.get("safety"), 1)

    # Kara za bardzo strome odcinki.
    # Jeśli nachylenie jest mniejsze niż 15%, kara wynosi 0.
    slope_penalty = max(0, slope - 15) ** 2

    if criterion == "distance":
        return (
            distance * 20
            + time * 0.4
            + elevation * 0.04
            + difficulty * 25
            + slope_penalty * 5
            + safety * 20
        )

    if criterion == "time":
        return (
            time
            + distance * 5
            + elevation * 0.05
            + difficulty * 30
            + slope_penalty * 6
            + safety * 25
        )

    if criterion == "elevation":
        return (
            elevation * 0.12
            + time * 0.8
            + distance * 8
            + difficulty * 35
            + slope_penalty * 8
            + safety * 30
        )

    if criterion == "difficulty":
        return (
            difficulty * 100
            + elevation * 0.08
            + time * 0.6
            + distance * 8
            + slope_penalty * 10
            + safety * 40
        )

    return (
        time
        + distance * 8
        + elevation * 0.06
        + difficulty * 50
        + slope_penalty * 8
        + safety * 30
    )


def calculate_route(nodes, edges, start, end, criterion="time"):
    """
    Custom HikeUp.

    Jest to autorski algorytm do wyznaczania tras górskich.
    Działa podobnie do A*, bo korzysta z heurystyki,
    ale ma własną wielokryterialną funkcję kosztu.

    Różnica polega na tym, że Custom HikeUp nie patrzy tylko
    na jedno kryterium, ale bierze pod uwagę kilka parametrów
    ważnych w terenie górskim.
    """
    start_time = perf_counter()

    graph = build_graph(edges)
    nodes_by_id = build_node_map(nodes)
    metrics = SearchMetrics()

    if start not in graph or end not in graph:
        return None

    g_score = {
        node_id: float("inf")
        for node_id in graph
    }

    previous = {
        node_id: None
        for node_id in graph
    }

    g_score[start] = 0

    first_priority = heuristic(start, end, nodes_by_id, criterion)
    queue = [(first_priority, start)]
    metrics.queue_pushes += 1

    while queue:
        current_priority, current_node = heapq.heappop(queue)
        metrics.visited_nodes += 1

        if current_node == end:
            break

        for neighbor_data in graph[current_node]:
            metrics.analyzed_edges += 1

            neighbor = neighbor_data["node"]
            edge = neighbor_data["edge"]

            new_g_score = g_score[current_node] + custom_hikeup_edge_weight(
                edge,
                criterion,
            )

            if new_g_score < g_score[neighbor]:
                g_score[neighbor] = new_g_score
                previous[neighbor] = current_node

                h_score = heuristic(neighbor, end, nodes_by_id, criterion)
                priority = new_g_score + h_score

                heapq.heappush(queue, (priority, neighbor))
                metrics.queue_pushes += 1

    if g_score[end] == float("inf"):
        return None

    path = reconstruct_path(previous, end)
    totals = calculate_route_totals(path, edges)

    metrics.execution_time_ms = round((perf_counter() - start_time) * 1000, 3)

    return {
        "algorithm": "custom_hikeup",
        "label": "Custom HikeUp",
        "path": path,

        "distance": totals["distance_km"],
        "time": totals["time_min"],
        "difficulty": totals["difficulty"],
        "total_elevation_gain": totals["elevation_gain_m"],
        "criterion": criterion,
        "route_weight": round(g_score[end], 3),

        "totals": totals,
        "metrics": {
            "visited_nodes": metrics.visited_nodes,
            "analyzed_edges": metrics.analyzed_edges,
            "queue_pushes": metrics.queue_pushes,
            "execution_time_ms": metrics.execution_time_ms,
            "route_weight": round(g_score[end], 3),
        },
    }