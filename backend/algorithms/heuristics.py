import math

from algorithms.weights import DEFAULT_FLAT_SPEED_KMH, validate_criterion


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
    validate_criterion(criterion)

    current = nodes_by_id.get(current_id)
    goal = nodes_by_id.get(goal_id)

    if not current or not goal:
        return 0

    distance = haversine_km(current, goal)

    if criterion == "distance":
        return distance

    if criterion == "time":
        # 5 km/h jest optymistyczną prędkością użytą również przez edge_weight.
        # Podejścia tylko zwiększają koszt, więc oszacowanie pozostaje dolne.
        return distance / DEFAULT_FLAT_SPEED_KMH * 60

    if criterion in {"elevation", "difficulty"}:
        # Dla tych złożonych kosztów nie używamy odległości w kilometrach jako
        # heurystyki o innej jednostce. h=0 zachowuje optymalność i sprawia, że
        # A* działa metodologicznie jak Dijkstra dla danego edge_weight.
        return 0.0

    raise AssertionError("Kryterium zostało zweryfikowane powyżej.")


def greedy_heuristic(current_id, goal_id, nodes_by_id):
    """Geograficzna heurystyka Greedy, niezależna od kryterium kosztu."""
    current = nodes_by_id.get(current_id)
    goal = nodes_by_id.get(goal_id)

    if not current or not goal:
        return 0.0

    return haversine_km(current, goal)
