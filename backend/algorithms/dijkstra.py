import heapq


def build_graph(edges):
    graph = {}

    for edge in edges:
        start = edge["from"]
        end = edge["to"]

        if start not in graph:
            graph[start] = []

        if end not in graph:
            graph[end] = []

        # Połączenie w jedną stronę
        graph[start].append({
            "node": end,
            "edge": edge
        })

        # Połączenie w drugą stronę
        # Dzięki temu graf jest nieskierowany, czyli szlaki działają w obie strony
        graph[end].append({
            "node": start,
            "edge": edge
        })

    return graph


def get_edge_weight(edge, criterion):
    """
    Funkcja zwraca wagę krawędzi w zależności od wybranego kryterium.

    time       - najszybsza trasa
    distance   - najkrótsza trasa
    difficulty - najłatwiejsza trasa
    """

    if criterion == "time":
        return edge["time_min"]

    if criterion == "distance":
        return edge["distance_km"]

    if criterion == "difficulty":
        return (
            edge["difficulty"] * 100
            + edge["elevation_gain_m"]
            + edge["time_min"]
        )

    # Domyślnie liczymy trasę najszybszą
    return edge["time_min"]


def calculate_route(nodes, edges, start, end, criterion):
    graph = build_graph(edges)

    distances = {}
    previous = {}

    for node in graph:
        distances[node] = float("inf")
        previous[node] = None

    if start not in graph or end not in graph:
        return None

    distances[start] = 0

    queue = []
    heapq.heappush(queue, (0, start))

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
            total_distance += edge["distance_km"]
            total_time += edge["time_min"]
            total_difficulty += edge["difficulty"]
            total_elevation_gain += edge["elevation_gain_m"]

    return {
        "path": path,
        "total_distance_km": round(total_distance, 2),
        "total_time_min": total_time,
        "total_difficulty": total_difficulty,
        "total_elevation_gain_m": total_elevation_gain,
        "criterion": criterion,
        "route_weight": round(distances[end], 2)
    }


def find_edge(edges, start, end):
    for edge in edges:
        if edge["from"] == start and edge["to"] == end:
            return edge

        if edge["from"] == end and edge["to"] == start:
            return edge

    return None