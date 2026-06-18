import heapq


def _as_number(value, default=0):
    """Bezpiecznie zamienia wartość z JSON-a na liczbę."""
    try:
        if value is None:
            return default
        if isinstance(value, str) and value.strip().lower() in {"", "unknown", "none", "null"}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_graph(edges):
    """
    Buduje graf nieskierowany z listy krawędzi z pliku cala_mapa.json.

    Każda krawędź powinna mieć pola:
    - from
    - to
    - distance_km
    - time_min
    - elevation_gain_m
    - difficulty
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

        graph[start].append({"node": end, "edge": edge})
        graph[end].append({"node": start, "edge": edge})

    return graph


def get_edge_weight(edge, criterion):
    """
    Zwraca wagę krawędzi w zależności od wybranego kryterium.

    time       - najszybsza trasa
    distance   - najkrótsza trasa
    elevation  - najmniejsze przewyższenie
    difficulty - najłatwiejsza trasa

    W nowych danych difficulty może być tekstem "unknown", dlatego nie można
    bezpośrednio mnożyć edge["difficulty"] jak wcześniej.
    """
    distance = _as_number(edge.get("distance_km"), 0)
    time = _as_number(edge.get("time_min"), 0)
    elevation = _as_number(edge.get("elevation_gain_m"), 0)
    difficulty = _as_number(edge.get("difficulty"), 1)

    if criterion == "distance":
        return distance

    if criterion == "elevation":
        # Mały dodatek dystansu zapobiega wybieraniu absurdalnych obejść tylko dlatego,
        # że mają minimalnie mniejsze przewyższenie.
        return elevation + distance * 10

    if criterion == "difficulty":
        # Przy braku realnej trudności używamy połączenia przewyższenia, czasu i dystansu.
        return difficulty * 100 + elevation + time + distance * 10

    # Domyślnie: time
    return time


def find_edge(edges, start, end):
    for edge in edges:
        if edge.get("from") == start and edge.get("to") == end:
            return edge
        if edge.get("from") == end and edge.get("to") == start:
            return edge
    return None


def calculate_route(nodes, edges, start, end, criterion="time"):
    """
    Liczy trasę Dijkstrą po pełnej mapie szlaków.

    Ważne:
    - start i end powinny być ID węzłów routingowych, czyli np. node/123,
      a niekoniecznie ID punktów charakterystycznych z graph_nodes.json.
    - Zamiana punktu charakterystycznego na nearest_routing_node_id odbywa się w app.py.
    """
    graph = build_graph(edges)

    if start not in graph or end not in graph:
        return None

    distances = {node_id: float("inf") for node_id in graph}
    previous = {node_id: None for node_id in graph}
    distances[start] = 0

    queue = [(0, start)]

    while queue:
        current_distance, current_node = heapq.heappop(queue)

        if current_node == end:
            break

        if current_distance > distances[current_node]:
            continue

        for neighbor_data in graph[current_node]:
            neighbor = neighbor_data["node"]
            edge = neighbor_data["edge"]
            weight = get_edge_weight(edge, criterion)
            new_distance = current_distance + weight

            if new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                previous[neighbor] = current_node
                heapq.heappush(queue, (new_distance, neighbor))

    if distances[end] == float("inf"):
        return None

    path = []
    current = end
    while current is not None:
        path.append(current)
        current = previous[current]
    path.reverse()

    total_distance = 0
    total_time = 0
    total_difficulty = 0
    total_elevation_gain = 0

    for i in range(len(path) - 1):
        edge = find_edge(edges, path[i], path[i + 1])
        if edge is not None:
            total_distance += _as_number(edge.get("distance_km"), 0)
            total_time += _as_number(edge.get("time_min"), 0)
            total_difficulty += _as_number(edge.get("difficulty"), 0)
            total_elevation_gain += _as_number(edge.get("elevation_gain_m"), 0)

    return {
        "path": path,
        "total_distance_km": round(total_distance, 2),
        "total_time_min": round(total_time),
        "total_difficulty": round(total_difficulty, 2),
        "total_elevation_gain_m": round(total_elevation_gain),
        "criterion": criterion,
        "route_weight": round(distances[end], 2),
    }
