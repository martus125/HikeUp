"""Spersonalizowany algorytm wyznaczania tras HikeUp."""

import heapq
from time import perf_counter

from algorithms.common import (
    SearchMetrics,
    build_edge_map,
    build_graph,
    calculate_route_totals,
    calculate_route_weight,
    make_directional_edge,
    reconstruct_path,
)
from algorithms.heuristics import build_node_map, haversine_km
from algorithms.weights import (
    MAX_REASONABLE_SLOPE_PERCENT,
    as_number,
    custom_hikeup_edge_weight,
    estimate_hiking_time_minutes,
)


def custom_hikeup_heuristic(
    current_id,
    goal_id,
    nodes_by_id,
    criterion,
    user_limits,
):
    """Zwraca dolne oszacowanie kosztu pozostałej drogi."""
    current = nodes_by_id.get(current_id)
    goal = nodes_by_id.get(goal_id)

    if not current or not goal:
        return 0.0

    distance = haversine_km(current, goal)
    current_elevation = as_number(current.get("elevation"), 0)
    goal_elevation = as_number(goal.get("elevation"), 0)
    minimum_gain = max(0.0, goal_elevation - current_elevation)
    ascent_rate = max(
        1.0,
        as_number(
            user_limits.get("preferred_elevation_per_hour"),
            250,
        ),
    )

    optimistic_edge = {
        "distance_km": distance,
        "elevation_gain_m": minimum_gain,
        "elevation_loss_m": 0,
    }
    estimated_time = estimate_hiking_time_minutes(
        optimistic_edge,
        ascent_rate_m_per_hour=ascent_rate,
    )
    flat_time = distance / 5.0 * 60
    elevation_effort = max(0.0, estimated_time - flat_time)

    if criterion == "distance":
        return flat_time + elevation_effort * 0.25

    if criterion == "time":
        return estimated_time

    if criterion == "elevation":
        return flat_time * 0.35 + elevation_effort * 1.2

    if criterion == "difficulty":
        return estimated_time * 0.5

    return estimated_time


def calculate_custom_path_score(
    path,
    edge_lookup,
    criterion,
    user_limits,
):
    """Oblicza spersonalizowany koszt gotowej ścieżki."""
    score = 0.0

    for start, end in zip(path, path[1:]):
        source_edge = edge_lookup.get((start, end))

        if source_edge is None:
            continue

        edge = make_directional_edge(
            source_edge,
            start,
            end,
        )
        score += custom_hikeup_edge_weight(
            edge,
            criterion,
            user_limits,
        )

    return score


def evaluate_route_profile(
    path,
    totals,
    edge_lookup,
    user_limits,
):
    """Sprawdza wynik trasy względem limitów profilu użytkownika."""
    max_slope = max(
        5.0,
        as_number(
            user_limits.get("max_slope_percent"),
            25,
        ),
    )
    max_difficulty = max(
        1.0,
        as_number(
            user_limits.get("max_difficulty"),
            4,
        ),
    )
    max_elevation_gain = max(
        0.0,
        as_number(
            user_limits.get("max_elevation_gain_m"),
            700,
        ),
    )
    max_consecutive_steep = max(
        0.0,
        as_number(
            user_limits.get("max_consecutive_steep"),
            1000,
        ),
    )
    reasonable_slope = max(
        max_slope,
        as_number(
            user_limits.get("max_reasonable_slope_percent"),
            MAX_REASONABLE_SLOPE_PERCENT,
        ),
    )

    maximum_observed_slope = 0.0
    maximum_effective_slope = 0.0
    maximum_observed_difficulty = 0.0
    current_steep_distance_m = 0.0
    maximum_consecutive_steep_m = 0.0
    steep_distance_m = 0.0
    invalid_slope_edges = 0

    for start, end in zip(path, path[1:]):
        source_edge = edge_lookup.get((start, end))

        if source_edge is None:
            continue

        edge = make_directional_edge(
            source_edge,
            start,
            end,
        )
        distance_m = max(
            0.0,
            as_number(edge.get("distance_km"), 0) * 1000,
        )
        raw_slope = abs(
            as_number(edge.get("slope_percent"), 0)
        )
        effective_slope = min(raw_slope, reasonable_slope)
        difficulty = as_number(edge.get("difficulty"), 1)

        maximum_observed_slope = max(
            maximum_observed_slope,
            raw_slope,
        )
        maximum_effective_slope = max(
            maximum_effective_slope,
            effective_slope,
        )
        maximum_observed_difficulty = max(
            maximum_observed_difficulty,
            difficulty,
        )

        if raw_slope > reasonable_slope:
            invalid_slope_edges += 1

        if effective_slope > max_slope:
            current_steep_distance_m += distance_m
            steep_distance_m += distance_m
            maximum_consecutive_steep_m = max(
                maximum_consecutive_steep_m,
                current_steep_distance_m,
            )
        else:
            current_steep_distance_m = 0.0

    elevation_exceeded = (
        max_elevation_gain > 0
        and totals["elevation_gain_m"] > max_elevation_gain
    )
    difficulty_exceeded = (
        maximum_observed_difficulty > max_difficulty
    )
    steep_section_exceeded = (
        max_consecutive_steep > 0
        and maximum_consecutive_steep_m
        > max_consecutive_steep
    )

    warnings = []

    if elevation_exceeded:
        difference = round(
            totals["elevation_gain_m"] - max_elevation_gain
        )
        warnings.append(
            "Przewyższenie przekracza limit profilu "
            f"o {difference} m."
        )

    if difficulty_exceeded:
        warnings.append(
            "Trasa zawiera odcinek o trudności "
            f"{maximum_observed_difficulty:g}, a limit profilu "
            f"wynosi {max_difficulty:g}."
        )

    if steep_section_exceeded:
        warnings.append(
            "Najdłuższy stromy fragment przekracza limit profilu."
        )

    if invalid_slope_edges:
        warnings.append(
            "Na trasie wykryto niewiarygodne dane nachylenia; "
            "ich wpływ na wybór trasy został ograniczony."
        )

    return {
        "within_limits": not (
            elevation_exceeded
            or difficulty_exceeded
            or steep_section_exceeded
        ),
        "elevation_limit_m": max_elevation_gain,
        "elevation_exceeded": elevation_exceeded,
        "max_difficulty_limit": max_difficulty,
        "difficulty_exceeded": difficulty_exceeded,
        "max_observed_difficulty": round(
            maximum_observed_difficulty,
            2,
        ),
        "max_slope_limit_percent": max_slope,
        "max_observed_slope_percent": round(
            maximum_observed_slope,
            2,
        ),
        "max_effective_slope_percent": round(
            maximum_effective_slope,
            2,
        ),
        "steep_distance_m": round(steep_distance_m),
        "max_consecutive_steep_m": round(
            maximum_consecutive_steep_m
        ),
        "steep_section_exceeded": steep_section_exceeded,
        "invalid_slope_edges": invalid_slope_edges,
        "warnings": warnings,
    }


def calculate_route(
    nodes,
    edges,
    start,
    end,
    criterion="time",
    user_limits=None,
    baseline_route=None,
):
    """Wyznacza spersonalizowaną trasę algorytmem A*."""
    start_time = perf_counter()
    user_limits = user_limits or {}

    graph = build_graph(edges)
    nodes_by_id = build_node_map(nodes)
    metrics = SearchMetrics()

    if start not in graph or end not in graph:
        return None

    g_score = {
        node_id: float("inf")
        for node_id in graph
    }
    previous = {
        node_id: None
        for node_id in graph
    }

    g_score[start] = 0.0
    first_priority = custom_hikeup_heuristic(
        start,
        end,
        nodes_by_id,
        criterion,
        user_limits,
    )
    queue = [(first_priority, 0.0, start)]
    metrics.queue_pushes += 1

    while queue:
        _, current_score, current_node = heapq.heappop(queue)

        if current_score > g_score[current_node]:
            continue

        metrics.visited_nodes += 1

        if current_node == end:
            break

        for neighbor_data in graph[current_node]:
            metrics.analyzed_edges += 1

            neighbor = neighbor_data["node"]
            edge = neighbor_data["edge"]
            new_score = (
                current_score
                + custom_hikeup_edge_weight(
                    edge,
                    criterion,
                    user_limits,
                )
            )

            if new_score >= g_score[neighbor]:
                continue

            g_score[neighbor] = new_score
            previous[neighbor] = current_node

            heuristic_score = custom_hikeup_heuristic(
                neighbor,
                end,
                nodes_by_id,
                criterion,
                user_limits,
            )
            heapq.heappush(
                queue,
                (
                    new_score + heuristic_score,
                    new_score,
                    neighbor,
                ),
            )
            metrics.queue_pushes += 1

    if g_score[end] == float("inf"):
        return None

    candidate_path = reconstruct_path(previous, end)
    candidate_totals = calculate_route_totals(
        candidate_path,
        edges,
    )
    candidate_score = g_score[end]

    path = candidate_path
    totals = candidate_totals
    custom_score = candidate_score
    fallback_applied = False
    detour_ratio = 1.0
    max_detour_ratio = max(
        1.0,
        as_number(
            user_limits.get("max_detour_ratio"),
            1.35,
        ),
    )
    edge_lookup = build_edge_map(edges)

    if baseline_route and baseline_route.get("path"):
        baseline_path = baseline_route["path"]
        baseline_totals = baseline_route.get("totals") or (
            calculate_route_totals(baseline_path, edges)
        )
        baseline_distance = max(
            0.0,
            as_number(
                baseline_totals.get("distance_km"),
                0,
            ),
        )

        if baseline_distance > 0:
            detour_ratio = (
                candidate_totals["distance_km"]
                / baseline_distance
            )

        if detour_ratio > max_detour_ratio:
            fallback_applied = True
            path = baseline_path
            totals = baseline_totals
            custom_score = calculate_custom_path_score(
                path,
                edge_lookup,
                criterion,
                user_limits,
            )

    comparable_route_weight = calculate_route_weight(
        path,
        edges,
        criterion,
    )
    profile_evaluation = evaluate_route_profile(
        path,
        totals,
        edge_lookup,
        user_limits,
    )

    if fallback_applied:
        profile_evaluation["warnings"].insert(
            0,
            "Wariant spersonalizowany był zbyt długi "
            f"({detour_ratio:.2f}× trasy bazowej), dlatego "
            "zastosowano bezpieczne ograniczenie objazdu.",
        )

    profile_evaluation.update(
        {
            "detour_ratio": round(detour_ratio, 3),
            "max_detour_ratio": max_detour_ratio,
            "fallback_applied": fallback_applied,
        }
    )

    metrics.execution_time_ms = round(
        (perf_counter() - start_time) * 1000,
        3,
    )

    return {
        "algorithm": "custom_hikeup",
        "path": path,
        "totals": totals,
        "route_weight": comparable_route_weight,
        "custom_score": round(custom_score, 3),
        "profile_evaluation": profile_evaluation,
        "warnings": profile_evaluation["warnings"],
        "metrics": {
            "visited_nodes": metrics.visited_nodes,
            "analyzed_edges": metrics.analyzed_edges,
            "queue_pushes": metrics.queue_pushes,
            "execution_time_ms": metrics.execution_time_ms,
            "route_weight": comparable_route_weight,
            "custom_score": round(custom_score, 3),
            "candidate_custom_score": round(
                candidate_score,
                3,
            ),
            "fallback_applied": fallback_applied,
            "detour_ratio": round(detour_ratio, 3),
        },
    }
