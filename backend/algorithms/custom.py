"""
Algorytm Custom HikeUp - dostosowany do profilu użytkownika.
Uwzględnia limity doświadczenia (stromość, trudność) i preferencje użytkownika.
"""

import heapq
from time import perf_counter

from algorithms.common import (
    SearchMetrics,
    build_graph,
    reconstruct_path,
    calculate_route_totals,
)
from algorithms.weights import as_number
from algorithms.heuristics import build_node_map, heuristic


def custom_hikeup_edge_weight(edge, criterion="time", user_limits=None):
    """
    Oblicza koszt przejścia jednej krawędzi dla algorytmu Custom HikeUp.
    
    Uwzględnia:
    - Dystans (km)
    - Czas przejścia (min)
    - Przewyższenie w górę (m) - trudne
    - Przewyższenie w dół (m) - łatwe (waga 0.3)
    - Trudność (1-7)
    - Nachylenie (%)
    - Limity użytkownika (max_slope, max_difficulty)
    
    Args:
        edge: dict - krawędź z parametrami
        criterion: str - kryterium optymalizacji (time/distance/elevation/difficulty)
        user_limits: dict - limity użytkownika z doświadczenia
    
    Returns:
        float - koszt przejścia krawędzią
    """
    # Pobierz dane z krawędzi
    distance = as_number(edge.get("distance_km"), 0)
    time = as_number(edge.get("time_min"), 0)
    elevation_gain = as_number(edge.get("elevation_gain_m"), 0)
    elevation_loss = as_number(edge.get("elevation_loss_m"), 0)
    difficulty = as_number(edge.get("difficulty"), 1)
    slope = as_number(edge.get("slope_percent"), 0)
    
    # Pobierz limity użytkownika (lub użyj domyślnych)
    user_limits = user_limits or {}
    max_slope = user_limits.get("max_slope_percent", 35)
    max_difficulty = user_limits.get("max_difficulty", 6)
    
    # Jeśli nachylenie > limit użytkownika → znaczna kara
    # Jeśli poniżej limitu → bez kary
    if slope > max_slope:
        # Karanie wzrasta kwadratowo (im bardziej powyżej limitu, tym większa kara)
        slope_penalty = ((slope - max_slope) ** 2) * 50
    else:
        slope_penalty = 0
    
    # Jeśli trudność > limit użytkownika → kara
    if difficulty > max_difficulty:
        difficulty_penalty = ((difficulty - max_difficulty) ** 2) * 100
    else:
        difficulty_penalty = 0
    
    # Podejście (elevation_gain) jest trudne - waga 1.0
    # Zejście (elevation_loss) jest łatwe - waga 0.3
    # Ta różnica jest kluczowa dla wygody użytkownika!
    total_elevation = elevation_gain * 1.0 + elevation_loss * 0.3
    
    
    if criterion == "distance":
        # Optymalizacja: NAJKRÓTSZA trasa
        return (
            distance * 20              # dystans jest głównym celem
            + time * 0.4               # czas drugorzędny
            + total_elevation * 0.04   # przewyższenie mało ważne
            + difficulty * 25
            + slope_penalty
        )
    
    elif criterion == "time":
        # Optymalizacja: NAJSZYBSZA trasa
        return (
            time                       # czas jest głównym celem
            + distance * 5             # dystans wpływa na czas
            + total_elevation * 0.05   # przewyższenie wpływa na tempo
            + difficulty * 30
            + slope_penalty * 1.5
        )
    
    elif criterion == "elevation":
        # Optymalizacja: Trasa z NAJMNIEJSZYM przewyższeniem
        return (
            total_elevation * 0.15     # przewyższenie jest głównym celem
            + time * 0.8
            + distance * 8
            + difficulty * 35
            + slope_penalty * 2
        )
    
    elif criterion == "difficulty":
        # Optymalizacja: NAJŁATWNIEJSZA trasa
        return (
            difficulty * 100           # trudność jest głównym celem
            + total_elevation * 0.08
            + time * 0.6
            + distance * 8
            + slope_penalty * 2.5
            + difficulty_penalty
        )
    
    # Domyślnie: balans wszystkich kryteriów
    return (
        time
        + distance * 8
        + total_elevation * 0.07
        + difficulty * 50
        + slope_penalty * 1.5
        + difficulty_penalty
    )


def calculate_route(nodes, edges, start, end, criterion="time", user_limits=None):
    """
    Algorytm Custom HikeUp - dostosowany do profilu użytkownika.
    
    Zwraca trasę optymalizowaną pod względem wybranego kryterium,
    z uwzględnieniem limitów wynikających z poziomu doświadczenia.
    
    Args:
        nodes: list - lista wszystkich węzłów grafu
        edges: list - lista wszystkich krawędzi grafu
        start: int - ID węzła startowego
        end: int - ID węzła końcowego
        criterion: str - kryterium optymalizacji (time/distance/elevation/difficulty)
        user_limits: dict - limity użytkownika na podstawie doświadczenia
    
    Returns:
        dict - wynik zawierający ścieżkę i metryki, lub None jeśli nie znaleziono
    """
    start_time = perf_counter()

    # Zbuduj graf wewnętrzny algorytmu
    graph = build_graph(edges)
    nodes_by_id = build_node_map(nodes)
    metrics = SearchMetrics()

    # Sprawdź czy węzły startowy i końcowy są w grafie
    if start not in graph or end not in graph:
        return None

    
    # Odległości od startu
    g_score = {node_id: float("inf") for node_id in graph}
    
    # Poprzedni węzeł w optymalnej ścieżce
    previous = {node_id: None for node_id in graph}

    # Start ma odległość 0
    g_score[start] = 0

    # Kolejka priorytetowa: (priorytet, węzeł)
    first_priority = heuristic(start, end, nodes_by_id, criterion)
    queue = [(first_priority, start)]
    metrics.queue_pushes += 1

    
    while queue:
        current_priority, current_node = heapq.heappop(queue)
        metrics.visited_nodes += 1

        # Jeśli dotarliśmy do celu, możemy zakończyć
        if current_node == end:
            break

        # Przeanalizuj wszystkich sąsiadów
        for neighbor_data in graph[current_node]:
            metrics.analyzed_edges += 1

            neighbor = neighbor_data["node"]
            edge = neighbor_data["edge"]

            # Oblicz koszt przejścia do sąsiada za pomocą custom_hikeup_edge_weight
            # ← KLUCZOWE: tutaj przekazujemy user_limits!
            new_g_score = g_score[current_node] + custom_hikeup_edge_weight(
                edge,
                criterion,
                user_limits  # ← Tutaj profil użytkownika wpływa na trasę!
            )

            # Jeśli znaleźliśmy lepszą ścieżkę do sąsiada
            if new_g_score < g_score[neighbor]:
                g_score[neighbor] = new_g_score
                previous[neighbor] = current_node

                # Dodaj do kolejki z priorytetem (g_score + heurystyka)
                h_score = heuristic(neighbor, end, nodes_by_id, criterion)
                priority = new_g_score + h_score

                heapq.heappush(queue, (priority, neighbor))
                metrics.queue_pushes += 1

    
    if g_score[end] == float("inf"):
        return None  # Nie znaleziono drogi

    
    path = reconstruct_path(previous, end)
    totals = calculate_route_totals(path, edges)

    
    metrics.execution_time_ms = round((perf_counter() - start_time) * 1000, 3)

    
    return {
        "algorithm": "custom_hikeup",
        "label": "Custom HikeUp",
        "path": path,
        "distance": totals["distance_km"],
        "time": totals["time_min"],
        "difficulty": totals["difficulty"],
        "total_elevation_gain": totals["elevation_gain_m"],
        "total_elevation_loss": totals.get("elevation_loss_m", 0),
        "criterion": criterion,
        "route_weight": round(g_score[end], 3),
        "totals": totals,
        "metrics": {
            "visited_nodes": metrics.visited_nodes,
            "analyzed_edges": metrics.analyzed_edges,
            "queue_pushes": metrics.queue_pushes,
            "execution_time_ms": metrics.execution_time_ms,
            "route_weight": round(g_score[end], 3),
        },
    }