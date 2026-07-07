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
    Greedy Best-First Search wyznaczający trasę po grafie szlaków.

    Algorytm wybiera w pierwszej kolejności ten wierzchołek,
    który według heurystyki znajduje się najbliżej celu.

    W przeciwieństwie do A* nie bierze pod uwagę pełnego kosztu dojścia
    od startu, dlatego może działać szybciej, ale nie gwarantuje
    najkrótszej albo najtańszej trasy.
    """
    start_time = perf_counter()

    graph = build_graph(edges)
    nodes_by_id = build_node_map(nodes)
    metrics = SearchMetrics()

    if start not in graph or end not in graph:
        return None

    visited = set()

    previous = {
        start: None
    }

    cost_so_far = {
        start: 0
    }

    queue = [
        (
            heuristic(start, end, nodes_by_id, criterion),
            start,
        )
    ]

    metrics.queue_pushes += 1

    while queue:
        current_priority, current_node = heapq.heappop(queue)

        if current_node in visited:
            continue

        visited.add(current_node)
        metrics.visited_nodes += 1

        if current_node == end:
            break

        for neighbor_data in graph[current_node]:
            metrics.analyzed_edges += 1

            neighbor = neighbor_data["node"]
            edge = neighbor_data["edge"]

            if neighbor in visited:
                continue

            if neighbor not in previous:
                previous[neighbor] = current_node
                cost_so_far[neighbor] = cost_so_far[current_node] + edge_weight(
                    edge,
                    criterion,
                )

                priority = heuristic(neighbor, end, nodes_by_id, criterion)

                heapq.heappush(queue, (priority, neighbor))
                metrics.queue_pushes += 1

    if end not in visited:
        return None

    path = reconstruct_path(previous, end)
    totals = calculate_route_totals(path, edges)

    metrics.execution_time_ms = round((perf_counter() - start_time) * 1000, 3)

    return {
        "algorithm": "greedy",
        "path": path,

        "distance": totals["distance_km"],
        "time": totals["time_min"],
        "difficulty": totals["difficulty"],
        "total_elevation_gain": totals["elevation_gain_m"],
        "criterion": criterion,
        "route_weight": round(cost_so_far.get(end, 0), 3),

        "totals": totals,
        "metrics": {
            "visited_nodes": metrics.visited_nodes,
            "analyzed_edges": metrics.analyzed_edges,
            "queue_pushes": metrics.queue_pushes,
            "execution_time_ms": metrics.execution_time_ms,
            "route_weight": round(cost_so_far.get(end, 0), 3),
        },
    }