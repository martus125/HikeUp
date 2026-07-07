import math


def haversine_km(first_node, second_node):
    """
    Liczy odległość w linii prostej między dwoma punktami GPS.

    To nie jest gotowa trasa.
    Ta odległość służy tylko jako heurystyka dla A* i Greedy.
    """
    lat1 = math.radians(float(first_node["lat"]))
    lng1 = math.radians(float(first_node["lng"]))
    lat2 = math.radians(float(second_node["lat"]))
    lng2 = math.radians(float(second_node["lng"]))

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlng / 2) ** 2
    )

    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_node_map(nodes):
    """
    Tworzy słownik:
    id wierzchołka -> dane wierzchołka.

    Dzięki temu można szybko znaleźć współrzędne konkretnego węzła.
    """
    return {
        node.get("id"): node
        for node in nodes
        if node.get("id")
    }


def heuristic(current_id, goal_id, nodes_by_id, criterion="time"):
    """
    Heurystyka, czyli oszacowanie kosztu od aktualnego wierzchołka do celu.

    Dla A*:
    f(n) = g(n) + h(n)

    h(n) to właśnie ta funkcja.
    """
    current = nodes_by_id.get(current_id)
    goal = nodes_by_id.get(goal_id)

    if not current or not goal:
        return 0

    distance = haversine_km(current, goal)

    if criterion == "distance":
        return distance

    if criterion == "time":
        # Zakładam orientacyjnie 5 km/h jako maksymalnie optymistyczne tempo.
        return distance / 5 * 60

    if criterion == "elevation":
        current_elevation = float(current.get("elevation") or 0)
        goal_elevation = float(goal.get("elevation") or 0)

        estimated_gain = max(0, goal_elevation - current_elevation)

        return estimated_gain + distance * 10

    if criterion == "difficulty":
        return distance * 10

    return distance