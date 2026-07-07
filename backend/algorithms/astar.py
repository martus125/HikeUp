import heapq
from time import perf_counter

from algorithms.common import (
    SearchMetrics,
    build_graph,
    reconstruct_path,
    calculate_route_totals,
)
from algorithms.weights import edge_weight
from algorithms.heuristics import build_node_map, heuristic


def calculate_route(nodes, edges, start, end, criterion="time"):
    """
    Algorytm A* wyznaczający trasę po grafie szlaków.

    A* różni się od Dijkstry tym, że oprócz aktualnego kosztu dojścia
    bierze pod uwagę heurystykę, czyli szacowany koszt dojścia do celu.
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

            new_g_score = g_score[current_node] + edge_weight(edge, criterion)

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
        "algorithm": "astar",
        "path": path,

        # Te pola zostawiamy, żeby backend/frontend działał tak jak przy Dijkstrze.
        "distance": totals["distance_km"],
        "time": totals["time_min"],
        "difficulty": totals["difficulty"],
        "total_elevation_gain": totals["elevation_gain_m"],
        "criterion": criterion,
        "route_weight": round(g_score[end], 3),

        # Te pola są już pod porównywanie algorytmów.
        "totals": totals,
        "metrics": {
            "visited_nodes": metrics.visited_nodes,
            "analyzed_edges": metrics.analyzed_edges,
            "queue_pushes": metrics.queue_pushes,
            "execution_time_ms": metrics.execution_time_ms,
            "route_weight": round(g_score[end], 3),
        },
    }