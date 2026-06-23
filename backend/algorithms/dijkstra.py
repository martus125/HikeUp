import heapq


def as_number(value, default=0):
    try:
        if value is None:
            return default
        if isinstance(value, str) and value.strip().lower() in {"", "unknown", "none", "null"}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_graph(edges):
    graph = {}

    for edge in edges:
        start = edge.get("from")
        end = edge.get("to")

        if not start or not end:
            continue

        graph.setdefault(start, []).append({"node": end, "edge": edge})
        graph.setdefault(end, []).append({"node": start, "edge": edge})

    return graph


def get_edge_weight(edge, criterion):
    distance = as_number(edge.get("distance_km"), 0)
    time = as_number(edge.get("time_min"), 0)
    elevation = as_number(edge.get("elevation_gain_m"), 0)
    difficulty = as_number(edge.get("difficulty"), 1)

    if criterion == "distance":
        return distance
    if criterion == "elevation":
        return elevation + distance * 10
    if criterion == "difficulty":
        return difficulty * 100 + elevation + time + distance * 10

    return time


def find_edge(edges, start, end):
    for edge in edges:
        if edge.get("from") == start and edge.get("to") == end:
            return edge
        if edge.get("from") == end and edge.get("to") == start:
            return edge
    return None


def calculate_route(nodes, edges, start, end, criterion="time"):
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
            new_distance = current_distance + get_edge_weight(edge, criterion)

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

    totals = calculate_route_totals(path, edges)

    return {
        "path": path,
        "total_distance_km": round(totals["distance"], 2),
        "total_time_min": round(totals["time"]),
        "total_difficulty": round(totals["difficulty"], 2),
        "total_elevation_gain_m": round(totals["elevation"]),
        "criterion": criterion,
        "route_weight": round(distances[end], 2),
    }


def calculate_route_totals(path, edges):
    totals = {
        "distance": 0,
        "time": 0,
        "difficulty": 0,
        "elevation": 0,
    }

    for index in range(len(path) - 1):
        edge = find_edge(edges, path[index], path[index + 1])
        if edge is None:
            continue

        totals["distance"] += as_number(edge.get("distance_km"), 0)
        totals["time"] += as_number(edge.get("time_min"), 0)
        totals["difficulty"] += as_number(edge.get("difficulty"), 0)
        totals["elevation"] += as_number(edge.get("elevation_gain_m"), 0)

    return totals
