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
from algorithms.heuristics import build_node_map, heuristic


def calculate_route(
    nodes,
    edges,
    start,
    end,
    criterion="time",
    points=None,
):
    """
    Algorytm A* wyznaczający trasę po grafie szlaków.

    A* różni się od Dijkstry tym, że oprócz aktualnego kosztu dojścia
    bierze pod uwagę heurystykę, czyli szacowany koszt dojścia do celu.
    """
    start_time = perf_counter()
    validate_criterion(criterion)

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
    queue = [(first_priority, 0.0, start)]
    metrics.queue_pushes += 1

    while queue:
        _, queued_g_score, current_node = heapq.heappop(queue)

        if queued_g_score > g_score[current_node]:
            continue

        metrics.visited_nodes += 1

        if current_node == end:
            break

        for neighbor_data in graph[current_node]:
            metrics.analyzed_edges += 1

            neighbor = neighbor_data["node"]
            edge = neighbor_data["edge"]

            new_g_score = queued_g_score + edge_weight(edge, criterion)

            if new_g_score < g_score[neighbor]:
                g_score[neighbor] = new_g_score
                previous[neighbor] = current_node

                h_score = heuristic(neighbor, end, nodes_by_id, criterion)
                priority = new_g_score + h_score

                heapq.heappush(
                    queue,
                    (priority, new_g_score, neighbor),
                )
                metrics.queue_pushes += 1

    if g_score[end] == float("inf"):
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
        algorithm="astar",
        path=path,
        totals=totals,
        metrics=metrics,
        criterion=criterion,
        route_weight=g_score[end],
    )
