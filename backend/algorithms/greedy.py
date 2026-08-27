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
from algorithms.heuristics import build_node_map, greedy_heuristic


def calculate_route(
    nodes,
    edges,
    start,
    end,
    criterion="time",
    points=None,
    routing_context=None,
):
    """
    Greedy Best-First Search wyznaczający trasę po grafie szlaków.

    Algorytm wybiera w pierwszej kolejności ten wierzchołek,
    który według heurystyki znajduje się najbliżej celu.

    W przeciwieństwie do A* nie bierze pod uwagę pełnego kosztu dojścia
    od startu, dlatego może działać szybciej, ale nie gwarantuje
    najkrótszej albo najtańszej trasy.

    Kolejność przeszukiwania jest zawsze geograficzna. ``criterion`` służy do
    porównywalnego policzenia kosztu gotowej trasy, ale Greedy nie udaje przez
    to bezpośredniej optymalizacji elevation ani difficulty.
    """
    start_time = perf_counter()
    validate_criterion(criterion)

    graph = (
        routing_context.graph
        if routing_context is not None
        else build_graph(edges)
    )
    nodes_by_id = (
        routing_context.nodes_by_id
        if routing_context is not None
        else build_node_map(nodes)
    )
    edge_map = (
        routing_context.edges_by_nodes
        if routing_context is not None
        else None
    )
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
            greedy_heuristic(start, end, nodes_by_id),
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

                priority = greedy_heuristic(neighbor, end, nodes_by_id)

                heapq.heappush(queue, (priority, neighbor))
                metrics.queue_pushes += 1

    if end not in visited:
        return None

    path = reconstruct_path(previous, end)
    totals = calculate_route_totals(
        path,
        edges,
        nodes=nodes,
        points=points,
        edge_map=edge_map,
        node_lookup=nodes_by_id,
    )

    metrics.execution_time_ms = round((perf_counter() - start_time) * 1000, 3)

    return build_algorithm_result(
        algorithm="greedy",
        path=path,
        totals=totals,
        metrics=metrics,
        criterion=criterion,
        route_weight=cost_so_far.get(end, 0),
    )
