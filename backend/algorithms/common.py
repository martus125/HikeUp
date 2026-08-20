import math
from dataclasses import asdict, dataclass

from algorithms.weights import (
    as_number,
    edge_weight,
    estimate_hiking_time_minutes,
    get_slope_percent,
)


SHELTER_ROUTE_RADIUS_M = 350.0
SHELTER_TYPES = frozenset({"alpine_hut", "shelter"})


@dataclass
class SearchMetrics:
    """
    Metryki potrzebne do porównania algorytmów w pracy inżynierskiej.
    """
    visited_nodes: int = 0
    analyzed_edges: int = 0
    queue_pushes: int = 0
    execution_time_ms: float = 0.0

    def as_dict(self):
        return asdict(self)


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

    # Przed benchmarkiem wielu par warto umożliwić przekazanie grafu zbudowanego
    # jeden raz. Obecne API celowo pozostaje bez zmian, aby zachować zgodność.
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


def _lat_lng(item):
    if not isinstance(item, dict):
        return None

    lat = as_number(item.get("lat", item.get("latitude")), None)
    lng = as_number(
        item.get("lng", item.get("lon", item.get("longitude"))),
        None,
    )

    if lat is None or lng is None:
        return None

    return lat, lng


def _point_to_segment_distance_m(point, segment_start, segment_end):
    """Przybliżona odległość punktu od krótkiego odcinka GPS w metrach."""
    point_lat, point_lng = point
    start_lat, start_lng = segment_start
    end_lat, end_lng = segment_end
    reference_lat = math.radians((point_lat + start_lat + end_lat) / 3.0)
    meters_per_degree_lat = 111_320.0
    meters_per_degree_lng = meters_per_degree_lat * math.cos(reference_lat)

    start_x = (start_lng - point_lng) * meters_per_degree_lng
    start_y = (start_lat - point_lat) * meters_per_degree_lat
    end_x = (end_lng - point_lng) * meters_per_degree_lng
    end_y = (end_lat - point_lat) * meters_per_degree_lat
    vector_x = end_x - start_x
    vector_y = end_y - start_y
    vector_length_squared = vector_x ** 2 + vector_y ** 2

    if vector_length_squared <= 1e-12:
        return math.hypot(start_x, start_y)

    projection = -(
        start_x * vector_x + start_y * vector_y
    ) / vector_length_squared
    projection = max(0.0, min(1.0, projection))
    nearest_x = start_x + projection * vector_x
    nearest_y = start_y + projection * vector_y
    return math.hypot(nearest_x, nearest_y)


def count_shelters_near_route(
    path,
    nodes,
    points,
    radius_m=SHELTER_ROUTE_RADIUS_M,
):
    """Liczy unikalne schroniska w promieniu od polilinii węzłów trasy."""
    if not path or not nodes or not points:
        return 0

    node_items = nodes.values() if isinstance(nodes, dict) else nodes
    point_items = points.values() if isinstance(points, dict) else points
    nodes_by_id = {
        node.get("id"): node
        for node in node_items
        if isinstance(node, dict) and node.get("id") is not None
    }
    route_coordinates = [
        _lat_lng(nodes_by_id.get(node_id))
        for node_id in path
    ]
    route_coordinates = [
        coordinates
        for coordinates in route_coordinates
        if coordinates is not None
    ]

    if not route_coordinates:
        return 0

    route_node_ids = set(path)
    counted_shelters = set()

    for index, point in enumerate(point_items):
        if not isinstance(point, dict) or point.get("type") not in SHELTER_TYPES:
            continue

        shelter_id = point.get("id", f"shelter-{index}")
        nearest_node_id = (
            point.get("nearest_routing_node_id")
            or point.get("routing_node_id")
        )
        distance_to_trail = as_number(point.get("distance_to_trail_m"), None)

        if (
            nearest_node_id in route_node_ids
            and distance_to_trail is not None
            and distance_to_trail <= radius_m
        ):
            counted_shelters.add(shelter_id)
            continue

        shelter_coordinates = _lat_lng(point)

        if shelter_coordinates is None:
            continue

        if len(route_coordinates) == 1:
            distance = _point_to_segment_distance_m(
                shelter_coordinates,
                route_coordinates[0],
                route_coordinates[0],
            )
            if distance <= radius_m:
                counted_shelters.add(shelter_id)
            continue

        if any(
            _point_to_segment_distance_m(
                shelter_coordinates,
                segment_start,
                segment_end,
            )
            <= radius_m
            for segment_start, segment_end in zip(
                route_coordinates,
                route_coordinates[1:],
            )
        ):
            counted_shelters.add(shelter_id)

    return len(counted_shelters)


def get_shelter_routing_node_ids(
    points,
    radius_m=SHELTER_ROUTE_RADIUS_M,
):
    """Węzły najbliższe schroniskom, używane tylko do lekkiego bonusu Custom."""
    if not points:
        return set()

    point_items = points.values() if isinstance(points, dict) else points
    result = set()

    for point in point_items:
        if not isinstance(point, dict) or point.get("type") not in SHELTER_TYPES:
            continue

        distance_to_trail = as_number(point.get("distance_to_trail_m"), None)
        node_id = (
            point.get("nearest_routing_node_id")
            or point.get("routing_node_id")
        )

        if (
            node_id is not None
            and distance_to_trail is not None
            and distance_to_trail <= radius_m
        ):
            result.add(node_id)

    return result


def calculate_route_totals(
    path,
    edges,
    nodes=None,
    points=None,
    edge_map=None,
):
    """
    Liczy parametry końcowej trasy:
    dystans, czas, trudność i przewyższenie.

    Przewyższenie jest liczone zgodnie z rzeczywistym
    kierunkiem przechodzenia krawędzi.
    """
    edge_map = edge_map or build_edge_map(edges)

    total_distance = 0.0
    total_time = 0.0
    weighted_difficulty = 0.0
    maximum_difficulty = 0.0
    total_elevation_gain = 0.0
    total_elevation_loss = 0.0
    maximum_slope = 0.0
    slope_distance_sum = 0.0
    slope_distance = 0.0

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

        distance = max(
            0.0,
            as_number(edge.get("distance_km"), 0),
        )
        difficulty = max(
            0.0,
            as_number(edge.get("difficulty"), 0),
        )

        total_distance += distance
        total_time += estimate_hiking_time_minutes(edge)
        weighted_difficulty += difficulty * distance
        maximum_difficulty = max(
            maximum_difficulty,
            difficulty,
        )
        slope = get_slope_percent(edge)
        maximum_slope = max(maximum_slope, slope)

        if distance > 0:
            slope_distance_sum += slope * distance
            slope_distance += distance

        total_elevation_gain += as_number(
            edge.get("elevation_gain_m"),
            0,
        )
        total_elevation_loss += as_number(
            edge.get("elevation_loss_m"),
            0,
        )

    average_difficulty = (
        weighted_difficulty / total_distance
        if total_distance > 0
        else 0.0
    )
    average_slope = (
        slope_distance_sum / slope_distance
        if slope_distance > 0
        else 0.0
    )
    shelters_count = count_shelters_near_route(
        path,
        nodes,
        points,
    )

    return {
        "distance_km": round(total_distance, 2),
        "time_min": round(total_time, 2),
        "difficulty": round(average_difficulty, 2),
        "average_difficulty": round(average_difficulty, 2),
        "max_difficulty": round(maximum_difficulty, 2),
        "elevation": round(total_elevation_gain, 2),
        "elevation_gain": round(total_elevation_gain, 2),
        "elevation_gain_m": round(total_elevation_gain, 2),
        "elevation_loss_m": round(total_elevation_loss, 2),
        "max_slope_percent": round(maximum_slope, 2),
        "average_slope_percent": round(average_slope, 2),
        "shelters_count": shelters_count,
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


def build_algorithm_result(
    algorithm,
    path,
    totals,
    metrics,
    criterion,
    route_weight,
    profile_evaluation=None,
    warnings=None,
    extra=None,
):
    """Buduje wspólny, kompatybilny kontrakt wyniku algorytmu."""
    metrics_data = (
        metrics.as_dict()
        if isinstance(metrics, SearchMetrics)
        else dict(metrics)
    )
    metrics_data["route_weight"] = round(route_weight, 3)

    result = {
        "algorithm": algorithm,
        "path": path,
        "totals": totals,
        "metrics": metrics_data,
        "profile_evaluation": profile_evaluation or {},
        "warnings": list(warnings or []),
        "criterion": criterion,
        "route_weight": round(route_weight, 3),

        # Pola kompatybilności pozostają dostępne dla endpointu i frontendu.
        "distance": totals["distance_km"],
        "time": totals["time_min"],
        "difficulty": totals["difficulty"],
        "elevation": totals["elevation_gain_m"],
        "total_distance_km": totals["distance_km"],
        "total_time_min": totals["time_min"],
        "total_elevation_gain": totals["elevation_gain_m"],
        "total_elevation_gain_m": totals["elevation_gain_m"],
    }

    if extra:
        result.update(extra)

    return result
