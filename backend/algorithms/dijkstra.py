import heapq
from time import perf_counter

from algorithms.common import (
    SearchMetrics,
    build_algorithm_result,
    build_graph,
    reconstruct_path,
    calculate_route_totals,
)
from algorithms.weights import edge_weight, validate_criterion


def calculate_route(
    nodes,
    edges,
    start,
    end,
    criterion="time",
    points=None,
):
    """
    Algorytm Dijkstry wyznaczający trasę po grafie szlaków.

    Algorytm wybiera zawsze wierzchołek o najmniejszym aktualnym koszcie dojścia
    od punktu startowego.
    """
    start_time = perf_counter()
    validate_criterion(criterion)

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

        if current_distance > distances[current_node]:
            continue

        metrics.visited_nodes += 1

        if current_node == end:
            break

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
    totals = calculate_route_totals(
        path,
        edges,
        nodes=nodes,
        points=points,
    )

    metrics.execution_time_ms = round((perf_counter() - start_time) * 1000, 3)

    return build_algorithm_result(
        algorithm="dijkstra",
        path=path,
        totals=totals,
        metrics=metrics,
        criterion=criterion,
        route_weight=distances[end],
    )
