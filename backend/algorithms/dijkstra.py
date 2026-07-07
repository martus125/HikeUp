import heapq
from time import perf_counter

from algorithms.common import (
    SearchMetrics,
    build_graph,
    reconstruct_path,
    calculate_route_totals,
)
from algorithms.weights import edge_weight


def calculate_route(nodes, edges, start, end, criterion="time"):
    """
    Algorytm Dijkstry wyznaczający trasę po grafie szlaków.

    Algorytm wybiera zawsze wierzchołek o najmniejszym aktualnym koszcie dojścia
    od punktu startowego.
    """
    start_time = perf_counter()

    graph = build_graph(edges)
    metrics = SearchMetrics()

    if start not in graph or end not in graph:
        return None

    distances = {
        node_id: float("inf")
        for node_id in graph
    }

    previous = {
        node_id: None
        for node_id in graph
    }

    distances[start] = 0
    queue = [(0, start)]
    metrics.queue_pushes += 1

    while queue:
        current_distance, current_node = heapq.heappop(queue)
        metrics.visited_nodes += 1

        if current_node == end:
            break

        if current_distance > distances[current_node]:
            continue

        for neighbor_data in graph[current_node]:
            metrics.analyzed_edges += 1

            neighbor = neighbor_data["node"]
            edge = neighbor_data["edge"]

            new_distance = current_distance + edge_weight(edge, criterion)

            if new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                previous[neighbor] = current_node

                heapq.heappush(queue, (new_distance, neighbor))
                metrics.queue_pushes += 1

    if distances[end] == float("inf"):
        return None

    path = reconstruct_path(previous, end)
    totals = calculate_route_totals(path, edges)

    metrics.execution_time_ms = round((perf_counter() - start_time) * 1000, 3)

    return {
        "algorithm": "dijkstra",
        "path": path,

        # Te pola zostawiamy, żeby obecny backend/frontend dalej działał.
        "distance": totals["distance_km"],
        "time": totals["time_min"],
        "difficulty": totals["difficulty"],
        "total_elevation_gain": totals["elevation_gain_m"],
        "criterion": criterion,
        "route_weight": round(distances[end], 3),

        # Te pola dodajemy już pod porównanie algorytmów.
        "totals": totals,
        "metrics": {
            "visited_nodes": metrics.visited_nodes,
            "analyzed_edges": metrics.analyzed_edges,
            "queue_pushes": metrics.queue_pushes,
            "execution_time_ms": metrics.execution_time_ms,
            "route_weight": round(distances[end], 3),
        },
    }