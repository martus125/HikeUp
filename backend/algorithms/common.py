from dataclasses import dataclass

from algorithms.weights import as_number, edge_weight


@dataclass
class SearchMetrics:
    """
    Metryki potrzebne do porównania algorytmów w pracy inżynierskiej.
    """
    visited_nodes: int = 0
    analyzed_edges: int = 0
    queue_pushes: int = 0
    execution_time_ms: float = 0.0


def get_elevation_values(edge):
    """
    Zwraca podejście, zejście i zmianę wysokości dla kierunku krawędzi.

    Obsługuje również starsze dane, w których zapisano tylko część pól
    wysokościowych.
    """
    elevation_change = as_number(
        edge.get("elevation_change_m"),
        None,
    )
    elevation_gain = as_number(
        edge.get("elevation_gain_m"),
        None,
    )
    elevation_loss = as_number(
        edge.get("elevation_loss_m"),
        None,
    )

    if elevation_change is None:
        elevation_change = (
            (elevation_gain or 0.0)
            - (elevation_loss or 0.0)
        )

    if elevation_gain is None:
        elevation_gain = max(0.0, elevation_change)

    if elevation_loss is None:
        elevation_loss = max(0.0, -elevation_change)

    return elevation_gain, elevation_loss, elevation_change


def make_directional_edge(edge, start, end):
    """
    Zwraca dane krawędzi zgodne z rzeczywistym kierunkiem przejścia.

    Krawędzie w pliku mapy mają jeden zapisany kierunek, ale graf jest
    nieskierowany. Przy przejściu odwrotnym podejście staje się zejściem,
    a podpisana zmiana wysokości zmienia znak.
    """
    directional_edge = dict(edge)

    original_start = edge.get("from")
    original_end = edge.get("to")
    elevation_gain, elevation_loss, elevation_change = (
        get_elevation_values(edge)
    )

    directional_edge["from"] = start
    directional_edge["to"] = end

    if start == original_start and end == original_end:
        directional_edge["elevation_gain_m"] = elevation_gain
        directional_edge["elevation_loss_m"] = elevation_loss
        directional_edge["elevation_change_m"] = elevation_change
        return directional_edge

    directional_edge["elevation_gain_m"] = elevation_loss
    directional_edge["elevation_loss_m"] = elevation_gain
    directional_edge["elevation_change_m"] = -elevation_change

    return directional_edge


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

        graph[start].append(
            {
                "node": end,
                "edge": edge,
            }
        )

        graph[end].append(
            {
                "node": start,
                "edge": make_directional_edge(
                    edge,
                    end,
                    start,
                ),
            }
        )

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

    Przewyższenie jest liczone zgodnie z rzeczywistym
    kierunkiem przechodzenia krawędzi.
    """
    edge_map = build_edge_map(edges)

    total_distance = 0.0
    total_time = 0.0
    total_difficulty = 0.0
    total_elevation_gain = 0.0
    total_elevation_loss = 0.0

    for index in range(len(path) - 1):
        start = path[index]
        end = path[index + 1]

        source_edge = edge_map.get((start, end))

        if source_edge is None:
            continue

        edge = make_directional_edge(
            source_edge,
            start,
            end,
        )

        total_distance += as_number(edge.get("distance_km"), 0)
        total_time += as_number(edge.get("time_min"), 0)
        total_difficulty += as_number(edge.get("difficulty"), 0)
        total_elevation_gain += as_number(
            edge.get("elevation_gain_m"),
            0,
        )
        total_elevation_loss += as_number(
            edge.get("elevation_loss_m"),
            0,
        )

    return {
        "distance_km": round(total_distance, 2),
        "time_min": round(total_time),
        "difficulty": round(total_difficulty, 2),
        "elevation": round(total_elevation_gain),
        "elevation_gain": round(total_elevation_gain),
        "elevation_gain_m": round(total_elevation_gain),
        "elevation_loss_m": round(total_elevation_loss),
    }


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

        source_edge = edge_map.get((start, end))

        if source_edge is None:
            continue

        edge = make_directional_edge(
            source_edge,
            start,
            end,
        )

        total_weight += edge_weight(edge, criterion)

    return round(total_weight, 3)
