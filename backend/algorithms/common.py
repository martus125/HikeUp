from dataclasses import dataclass

from algorithms.weights import as_number, edge_weight


@dataclass
class SearchMetrics:
    """
    Metryki potrzebne do porównania algorytmów
    w pracy inżynierskiej.
    """

    visited_nodes: int = 0
    analyzed_edges: int = 0
    queue_pushes: int = 0
    execution_time_ms: float = 0.0


def make_directional_edge(edge, start, end):
    """
    Tworzy dane krawędzi odpowiednie dla kierunku przejścia.

    Jeżeli przechodzimy zgodnie z kierunkiem zapisanym w JSON,
    dane pozostają bez zmian.

    Jeżeli przechodzimy w przeciwnym kierunku:
    - podejście staje się zejściem,
    - zejście staje się podejściem,
    - zmiana wysokości zmienia znak.
    """

    directional_edge = dict(edge)

    original_start = edge.get("from")
    original_end = edge.get("to")

    directional_edge["from"] = start
    directional_edge["to"] = end

    if start == original_start and end == original_end:
        return directional_edge

    original_gain = as_number(
        edge.get("elevation_gain_m"),
        0,
    )
    original_loss = as_number(
        edge.get("elevation_loss_m"),
        0,
    )
    original_change = as_number(
        edge.get("elevation_change_m"),
        0,
    )

    directional_edge["elevation_gain_m"] = original_loss
    directional_edge["elevation_loss_m"] = original_gain
    directional_edge["elevation_change_m"] = -original_change

    return directional_edge


def build_graph(edges):
    """
    Buduje graf nieskierowany.

    Każda krawędź jest dostępna w obu kierunkach,
    ale dane podejścia i zejścia są odpowiednio odwracane.
    """

    graph = {}

    for edge in edges:
        start = edge.get("from")
        end = edge.get("to")

        if not start or not end:
            continue

        graph.setdefault(start, [])
        graph.setdefault(end, [])

        forward_edge = make_directional_edge(
            edge,
            start,
            end,
        )

        reverse_edge = make_directional_edge(
            edge,
            end,
            start,
        )

        graph[start].append(
            {
                "node": end,
                "edge": forward_edge,
            }
        )

        graph[end].append(
            {
                "node": start,
                "edge": reverse_edge,
            }
        )

    return graph


def reconstruct_path(previous, end):
    """
    Odtwarza ścieżkę od punktu startowego
    do punktu końcowego.
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
    Tworzy mapę krawędzi dla obu kierunków.

    Każdy kierunek ma poprawnie ustawione:
    - elevation_gain_m,
    - elevation_loss_m,
    - elevation_change_m.
    """

    edge_map = {}

    for edge in edges:
        start = edge.get("from")
        end = edge.get("to")

        if not start or not end:
            continue

        edge_map[(start, end)] = make_directional_edge(
            edge,
            start,
            end,
        )

        edge_map[(end, start)] = make_directional_edge(
            edge,
            end,
            start,
        )

    return edge_map


def calculate_route_totals(path, edges):
    """
    Liczy parametry końcowej trasy:
    dystans, czas, trudność i sumę podejść.
    """

    edge_map = build_edge_map(edges)

    total_distance = 0.0
    total_time = 0.0
    total_difficulty = 0.0
    total_elevation_gain = 0.0

    for index in range(len(path) - 1):
        start = path[index]
        end = path[index + 1]

        edge = edge_map.get((start, end))

        if edge is None:
            continue

        total_distance += as_number(
            edge.get("distance_km"),
            0,
        )

        total_time += as_number(
            edge.get("time_min"),
            0,
        )

        total_difficulty += as_number(
            edge.get("difficulty"),
            0,
        )

        total_elevation_gain += as_number(
            edge.get("elevation_gain_m"),
            0,
        )

    return {
        "distance_km": round(total_distance, 2),
        "time_min": round(total_time),
        "difficulty": round(total_difficulty, 2),
        "elevation_gain_m": round(total_elevation_gain),
    }


def calculate_route_weight(path, edges, criterion):
    """
    Liczy wagę końcowej trasy zgodnie z wybranym kryterium.
    """

    edge_map = build_edge_map(edges)
    total_weight = 0.0

    for index in range(len(path) - 1):
        start = path[index]
        end = path[index + 1]

        edge = edge_map.get((start, end))

        if edge is None:
            continue

        total_weight += edge_weight(
            edge,
            criterion,
        )

    return round(total_weight, 3)