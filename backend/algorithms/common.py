from dataclasses import dataclass

from algorithms.weights import as_number


@dataclass
class SearchMetrics:
    """
    Metryki potrzebne do porównania algorytmów w pracy inżynierskiej.
    """
    visited_nodes: int = 0
    analyzed_edges: int = 0
    queue_pushes: int = 0
    execution_time_ms: float = 0.0


def build_graph(edges):
    """
    Buduje graf nieskierowany na podstawie listy krawędzi.

    Każda krawędź jest dodawana w dwie strony,
    ponieważ szlaki można zwykle przechodzić w obu kierunkach.
    """
    graph = {}

    for edge in edges:
        start = edge.get("from")
        end = edge.get("to")

        if not start or not end:
            continue

        if start not in graph:
            graph[start] = []

        if end not in graph:
            graph[end] = []

        graph[start].append({
            "node": end,
            "edge": edge,
        })

        graph[end].append({
            "node": start,
            "edge": edge,
        })

    return graph


def reconstruct_path(previous, end):
    """
    Odtwarza ścieżkę od punktu startowego do końcowego
    na podstawie słownika previous.
    """
    path = []
    current = end

    while current is not None:
        path.append(current)
        current = previous.get(current)

    path.reverse()
    return path


def build_edge_map(edges):
    """
    Tworzy mapę krawędzi, żeby szybciej znajdować dane odcinków trasy.
    """
    edge_map = {}

    for edge in edges:
        start = edge.get("from")
        end = edge.get("to")

        if not start or not end:
            continue

        edge_map[(start, end)] = edge
        edge_map[(end, start)] = edge

    return edge_map


def calculate_route_totals(path, edges):
    """
    Liczy parametry końcowej trasy:
    dystans, czas, trudność i przewyższenie.
    """
    edge_map = build_edge_map(edges)

    total_distance = 0
    total_time = 0
    total_difficulty = 0
    total_elevation_gain = 0

    for index in range(len(path) - 1):
        start = path[index]
        end = path[index + 1]

        edge = edge_map.get((start, end))

        if edge is None:
            continue

        total_distance += as_number(edge.get("distance_km"), 0)
        total_time += as_number(edge.get("time_min"), 0)
        total_difficulty += as_number(edge.get("difficulty"), 0)
        total_elevation_gain += as_number(edge.get("elevation_gain_m"), 0)

    return {
        "distance_km": round(total_distance, 2),
        "time_min": round(total_time),
        "difficulty": round(total_difficulty, 2),
        "elevation_gain_m": round(total_elevation_gain),
    }
from algorithms.weights import as_number, edge_weight


def calculate_route_weight(path, edges, criterion):
    """
    Liczy porównywalną wagę końcowej trasy,
    identycznie dla wszystkich algorytmów.
    """
    edge_map = build_edge_map(edges)
    total_weight = 0.0

    for index in range(len(path) - 1):
        start = path[index]
        end = path[index + 1]

        edge = edge_map.get((start, end))

        if edge is None:
            continue

        total_weight += edge_weight(edge, criterion)

    return round(total_weight, 3)