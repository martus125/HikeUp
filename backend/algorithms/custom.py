"""Profilowy algorytm wyznaczania tras Custom HikeUp.

Cel Custom HikeUp
-----------------
Algorytm został zaprojektowany w celu dostosowania trasy do profilu
użytkownika. Nie zakłada to, że wynik będzie obiektywnie lepszy od wyników
algorytmów klasycznych; tę hipotezę musi zweryfikować późniejszy benchmark.

Różnica względem Dijkstra/A*/Greedy
-----------------------------------
Dijkstra i A* minimalizują wspólny ``edge_weight``, a Greedy kieruje się
położeniem geograficznym. Custom wykonuje przeszukiwanie jednokosztowe bez
heurystyki nad własną, profilową wagą krawędzi. Dzięki temu nie jest kopią A*,
a przy nieujemnych wagach znajduje minimum zdefiniowanego kosztu profilowego.

Składniki wagi
--------------
``base_cost`` pochodzi ze wspólnego ``edge_weight`` dla kryterium time,
distance, elevation albo difficulty. Nachylenie, trudność i wysiłek związany
z przewyższeniem dodają osobne kary proporcjonalne do kosztu bazowego. Limity
i współczynniki profilu są zdefiniowane centralnie w
``models/experience_config.py``. Beginner i senior otrzymują silniejsze kary,
intermediate umiarkowane, a expert słabsze. Schronisko może dać wyłącznie mały,
ograniczony bonus i nigdy nie tworzy ujemnej krawędzi.

Kandydaci i detour_ratio
-----------------------
Custom tworzy kandydatów profilowych i ograniczonych, a następnie najpierw
odrzuca warianty naruszające twarde granice bezpieczeństwa. Spośród pozostałych
wybiera najtańszy według kryterium użytkownika. ``detour_ratio`` to długość
kandydata podzielona przez długość trasy najkrótszej. Limit preferowany wpływa
na kolejność wyboru, a osobna granica bezwzględna usuwa absurdalne objazdy.
Jeżeli żaden kandydat nie mieści się w limitach profilu, Custom nadal zwraca
najłatwiejszy rozsądny wariant do wybranego celu. Wynik otrzymuje status
``difficult_route`` i konkretne ostrzeżenia. Osobno mogą zostać wskazane
łatwiejsze, podobne cele.

Tryb bez profilu
----------------
Gdy endpoint nie ma zalogowanego użytkownika, Custom nie zakłada domyślnej
sprawności. Zwraca neutralną trasę według wskazanego kryterium i oznacza ją jako
``unpersonalized``. Ocena ograniczeń profilu jest uruchamiana dopiero po
zalogowaniu i pobraniu profilu.
"""

import heapq
from time import perf_counter

from algorithms.common import (
    SearchMetrics,
    build_algorithm_result,
    build_edge_map,
    build_graph,
    calculate_route_totals,
    get_shelter_routing_node_ids,
    make_directional_edge,
    reconstruct_path,
)
from algorithms.weights import (
    MAX_REASONABLE_SLOPE_PERCENT,
    as_number,
    custom_hikeup_edge_weight,
    edge_weight,
    get_slope_percent,
    validate_criterion,
)
from models.experience_config import PROFILE_MATCH_WEIGHTS, get_limits


def calculate_custom_path_score(
    path,
    edge_lookup,
    criterion,
    user_limits,
    shelter_node_ids=None,
):
    """Oblicza profilowy koszt dowolnej gotowej ścieżki."""
    score = 0.0
    shelter_node_ids = shelter_node_ids or set()

    for start, end in zip(path, path[1:]):
        source_edge = edge_lookup.get((start, end))

        if source_edge is None:
            continue

        edge = make_directional_edge(source_edge, start, end)
        score += custom_hikeup_edge_weight(
            edge,
            criterion,
            user_limits,
            shelter_nearby=end in shelter_node_ids,
        )

    return score


def _component_score(value, limit, weight):
    """Pełna punktacja do limitu, potem liniowy spadek do zera."""
    if limit <= 0 or value <= limit:
        return weight

    excess_ratio = (value - limit) / max(limit, 1.0)
    return weight * max(0.0, 1.0 - excess_ratio)


def calculate_profile_match_score(
    totals,
    user_limits,
    detour_ratio,
):
    """Zwraca analityczną, niesterującą wyszukiwaniem ocenę 0–100."""
    max_slope = max(
        5.0,
        as_number(user_limits.get("max_slope_percent"), 25),
    )
    max_difficulty = max(
        1.0,
        as_number(user_limits.get("max_difficulty"), 4),
    )
    max_elevation_gain = max(
        0.0,
        as_number(user_limits.get("max_elevation_gain_m"), 700),
    )
    max_detour_ratio = max(
        1.0,
        as_number(user_limits.get("max_detour_ratio"), 1.35),
    )
    reasonable_slope = max(
        max_slope,
        as_number(
            user_limits.get("max_reasonable_slope_percent"),
            MAX_REASONABLE_SLOPE_PERCENT,
        ),
    )
    effective_slope = min(
        as_number(totals.get("max_slope_percent"), 0),
        reasonable_slope,
    )

    score = _component_score(
        effective_slope,
        max_slope,
        PROFILE_MATCH_WEIGHTS["slope"],
    )
    score += _component_score(
        as_number(totals.get("max_difficulty"), 0),
        max_difficulty,
        PROFILE_MATCH_WEIGHTS["difficulty"],
    )
    score += _component_score(
        as_number(totals.get("elevation_gain_m"), 0),
        max_elevation_gain,
        PROFILE_MATCH_WEIGHTS["elevation"],
    )

    if detour_ratio is None:
        score += PROFILE_MATCH_WEIGHTS["detour"]
    else:
        score += _component_score(
            detour_ratio,
            max_detour_ratio,
            PROFILE_MATCH_WEIGHTS["detour"],
        )

    shelter_preference = as_number(
        user_limits.get("shelter_bonus_factor"),
        0,
    )
    if shelter_preference <= 0 or totals.get("shelters_count", 0) > 0:
        score += PROFILE_MATCH_WEIGHTS["shelters"]

    return round(max(0.0, min(100.0, score)), 1)


def evaluate_route_profile(
    path,
    totals,
    edge_lookup,
    user_limits,
    detour_ratio=None,
    fallback_applied=False,
    fallback_reason=None,
):
    """Wyjaśnia dopasowanie trasy i oddziela preferencje od bezpieczeństwa."""
    max_slope = max(
        5.0,
        as_number(user_limits.get("max_slope_percent"), 25),
    )
    absolute_max_slope = max(
        max_slope,
        as_number(
            user_limits.get("absolute_max_slope_percent"),
            MAX_REASONABLE_SLOPE_PERCENT,
        ),
    )
    max_difficulty = max(
        1.0,
        as_number(user_limits.get("max_difficulty"), 4),
    )
    max_elevation_gain = max(
        0.0,
        as_number(user_limits.get("max_elevation_gain_m"), 700),
    )
    max_consecutive_steep = max(
        0.0,
        as_number(user_limits.get("max_consecutive_steep"), 1000),
    )
    max_detour_ratio = max(
        1.0,
        as_number(user_limits.get("max_detour_ratio"), 1.35),
    )
    max_acceptable_detour_ratio = max(
        max_detour_ratio,
        as_number(
            user_limits.get("max_acceptable_detour_ratio"),
            max_detour_ratio,
        ),
    )
    reasonable_slope = max(
        max_slope,
        as_number(
            user_limits.get("max_reasonable_slope_percent"),
            MAX_REASONABLE_SLOPE_PERCENT,
        ),
    )

    current_steep_distance_m = 0.0
    maximum_consecutive_steep_m = 0.0
    steep_distance_m = 0.0
    invalid_slope_edges = 0

    for start, end in zip(path, path[1:]):
        source_edge = edge_lookup.get((start, end))

        if source_edge is None:
            continue

        edge = make_directional_edge(source_edge, start, end)
        distance_m = max(
            0.0,
            as_number(edge.get("distance_km"), 0) * 1000,
        )
        raw_slope = get_slope_percent(edge)
        effective_slope = min(raw_slope, reasonable_slope)

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
    difficulty_exceeded = totals["max_difficulty"] > max_difficulty
    slope_exceeded = min(
        totals["max_slope_percent"],
        reasonable_slope,
    ) > max_slope
    absolute_slope_exceeded = min(
        totals["max_slope_percent"],
        reasonable_slope,
    ) > absolute_max_slope
    steep_section_exceeded = (
        max_consecutive_steep > 0
        and maximum_consecutive_steep_m > max_consecutive_steep
    )
    detour_exceeded = (
        detour_ratio is not None
        and detour_ratio > max_detour_ratio
    )
    detour_unreasonable = (
        detour_ratio is not None
        and detour_ratio > max_acceptable_detour_ratio
    )

    violations = []
    warnings = []

    if slope_exceeded:
        violations.append("max_slope_exceeded")
        warnings.append("Trasa przekracza preferowane nachylenie profilu.")

    if absolute_slope_exceeded:
        violations.append("absolute_max_slope_exceeded")
        warnings.append(
            "Trasa przekracza bezwzględną granicę nachylenia profilu."
        )

    if difficulty_exceeded:
        violations.append("max_difficulty_exceeded")
        warnings.append(
            "Trasa zawiera odcinek o trudności "
            f"{totals['max_difficulty']:g}, a limit profilu "
            f"wynosi {max_difficulty:g}."
        )

    if elevation_exceeded:
        violations.append("elevation_gain_exceeded")
        difference = round(totals["elevation_gain_m"] - max_elevation_gain)
        warnings.append(
            "Przewyższenie przekracza limit profilu "
            f"o {difference} m."
        )

    if steep_section_exceeded:
        violations.append("steep_section_exceeded")
        warnings.append("Najdłuższy stromy fragment przekracza limit profilu.")

    if detour_exceeded:
        violations.append("detour_ratio_exceeded")
        warnings.append(
            "Łagodniejszy wariant przekracza preferowany limit objazdu."
        )

    if detour_unreasonable:
        violations.append("detour_unreasonable")
        warnings.append(
            "Objazd jest zbyt długi, aby uznać go za rozsądną alternatywę."
        )

    if invalid_slope_edges:
        warnings.append(
            "Na trasie wykryto niewiarygodne dane nachylenia; "
            "ich wpływ na wybór trasy został ograniczony."
        )

    if fallback_applied:
        warnings.insert(
            0,
            "Zastosowano jawną trasę bazową Dijkstry: "
            f"{fallback_reason}."
        )

    limits = {
        "max_slope_percent": max_slope,
        "absolute_max_slope_percent": absolute_max_slope,
        "max_difficulty": max_difficulty,
        "max_elevation_gain_m": max_elevation_gain,
        "max_consecutive_steep_m": max_consecutive_steep,
        "preferred_elevation_per_hour": as_number(
            user_limits.get("preferred_elevation_per_hour"),
            250,
        ),
        "max_detour_ratio": max_detour_ratio,
        "max_acceptable_detour_ratio": max_acceptable_detour_ratio,
    }
    route = {
        "max_slope_percent": totals["max_slope_percent"],
        "average_slope_percent": totals["average_slope_percent"],
        "max_difficulty": totals["max_difficulty"],
        "average_difficulty": totals["average_difficulty"],
        "elevation_gain_m": totals["elevation_gain_m"],
        "shelters_count": totals["shelters_count"],
        "steep_distance_m": round(steep_distance_m),
        "max_consecutive_steep_m": round(maximum_consecutive_steep_m),
    }
    safety_violations = [
        violation
        for violation in violations
        if violation
        in {
            "absolute_max_slope_exceeded",
            "max_difficulty_exceeded",
            "elevation_gain_exceeded",
            "steep_section_exceeded",
        }
    ]

    return {
        "experience_level": user_limits.get(
            "experience_level",
            "intermediate",
        ),
        "fallback_applied": fallback_applied,
        "fallback_reason": fallback_reason,
        "detour_ratio": (
            round(detour_ratio, 3)
            if detour_ratio is not None
            else None
        ),
        "limits": limits,
        "route": route,
        "violations": violations,
        "safety_violations": safety_violations,
        "profile_match_score": calculate_profile_match_score(
            totals,
            user_limits,
            detour_ratio,
        ),
        "warnings": warnings,

        # Pola kompatybilności ze starszym widokiem i testami.
        "within_limits": not violations,
        "within_safety_limits": not safety_violations,
        "reasonable_detour": not detour_unreasonable,
        "elevation_limit_m": max_elevation_gain,
        "elevation_exceeded": elevation_exceeded,
        "max_difficulty_limit": max_difficulty,
        "difficulty_exceeded": difficulty_exceeded,
        "max_observed_difficulty": totals["max_difficulty"],
        "max_slope_limit_percent": max_slope,
        "absolute_max_slope_limit_percent": absolute_max_slope,
        "absolute_slope_exceeded": absolute_slope_exceeded,
        "max_observed_slope_percent": totals["max_slope_percent"],
        "max_effective_slope_percent": min(
            totals["max_slope_percent"],
            reasonable_slope,
        ),
        "steep_distance_m": round(steep_distance_m),
        "max_consecutive_steep_m": round(maximum_consecutive_steep_m),
        "steep_section_exceeded": steep_section_exceeded,
        "invalid_slope_edges": invalid_slope_edges,
        "max_detour_ratio": max_detour_ratio,
        "max_acceptable_detour_ratio": max_acceptable_detour_ratio,
        "detour_preference_exceeded": detour_exceeded,
        "detour_unreasonable": detour_unreasonable,
    }


def _search_graph(
    graph,
    start,
    weight_function,
    metrics,
    end=None,
    target_ids=None,
    edge_allowed=None,
):
    """Wspólne przeszukiwanie używane do tworzenia kilku kandydatów."""
    scores = {start: 0.0}
    previous = {start: None}
    queue = [(0.0, start)]
    remaining_targets = set(target_ids or ())
    metrics.queue_pushes += 1

    while queue:
        current_score, current_node = heapq.heappop(queue)

        if current_score > scores.get(current_node, float("inf")):
            continue

        metrics.visited_nodes += 1

        if end is not None and current_node == end:
            break

        if current_node in remaining_targets:
            remaining_targets.remove(current_node)
            if not remaining_targets:
                break

        for neighbor_data in graph.get(current_node, []):
            metrics.analyzed_edges += 1
            neighbor = neighbor_data["node"]
            edge = neighbor_data["edge"]

            if edge_allowed is not None and not edge_allowed(edge):
                continue

            new_score = current_score + weight_function(edge, neighbor)

            if new_score >= scores.get(neighbor, float("inf")):
                continue

            scores[neighbor] = new_score
            previous[neighbor] = current_node
            heapq.heappush(queue, (new_score, neighbor))
            metrics.queue_pushes += 1

    return scores, previous


def _path_from_search(scores, previous, end):
    if end not in scores:
        return None
    return reconstruct_path(previous, end)


def _profile_edge_allowed(edge, user_limits):
    """Twarde ograniczenia lokalne dla kandydatów bezpieczeństwa."""
    max_difficulty = max(
        1.0,
        as_number(user_limits.get("max_difficulty"), 4),
    )
    absolute_max_slope = max(
        as_number(user_limits.get("max_slope_percent"), 25),
        as_number(
            user_limits.get("absolute_max_slope_percent"),
            MAX_REASONABLE_SLOPE_PERCENT,
        ),
    )
    difficulty = max(1.0, as_number(edge.get("difficulty"), 1))
    slope = min(
        get_slope_percent(edge),
        as_number(
            user_limits.get("max_reasonable_slope_percent"),
            MAX_REASONABLE_SLOPE_PERCENT,
        ),
    )
    return difficulty <= max_difficulty and slope <= absolute_max_slope


def _path_criterion_weight(path, edge_lookup, criterion):
    total = 0.0

    for start, end in zip(path, path[1:]):
        source_edge = edge_lookup.get((start, end))
        if source_edge is None:
            continue
        total += edge_weight(
            make_directional_edge(source_edge, start, end),
            criterion,
        )

    return total


def calculate_route(
    nodes,
    edges,
    start,
    end,
    criterion="time",
    user_limits=None,
    baseline_route=None,
    points=None,
    routing_context=None,
    personalization_enabled=True,
):
    """Wybiera trasę ogólną albo najtańszą spośród kandydatów profilu."""
    start_time = perf_counter()
    validate_criterion(criterion)

    profile_limits = {
        **get_limits("intermediate"),
        **(user_limits or {}),
    }
    graph = (
        routing_context.graph
        if routing_context is not None
        else build_graph(edges)
    )
    metrics = SearchMetrics()

    if start not in graph or end not in graph:
        return None

    shelter_node_ids = (
        routing_context.shelter_node_ids
        if routing_context is not None
        else get_shelter_routing_node_ids(points)
    )
    edge_lookup = (
        routing_context.edges_by_nodes
        if routing_context is not None
        else build_edge_map(edges)
    )
    node_lookup = (
        routing_context.nodes_by_id
        if routing_context is not None
        else None
    )
    candidate_paths = []

    baseline_path = None
    baseline_weight = None
    if (
        baseline_route
        and baseline_route.get("path")
        and baseline_route.get("criterion", criterion) == criterion
    ):
        baseline_path = baseline_route["path"]
        baseline_weight = baseline_route.get("route_weight")
    else:
        scores, previous = _search_graph(
            graph,
            start,
            lambda edge, _neighbor: edge_weight(edge, criterion),
            metrics,
            end=end,
        )
        baseline_path = _path_from_search(scores, previous, end)
        baseline_weight = scores.get(end)

    if not personalization_enabled:
        if not baseline_path:
            return None

        baseline_totals = (
            baseline_route.get("totals")
            if baseline_route and baseline_route.get("totals")
            else calculate_route_totals(
                baseline_path,
                edges,
                nodes=nodes,
                points=points,
                edge_map=edge_lookup,
                node_lookup=node_lookup,
            )
        )
        if baseline_weight is None:
            baseline_weight = _path_criterion_weight(
                baseline_path,
                edge_lookup,
                criterion,
            )

        message = (
            "Trasa ogólna według wybranego kryterium. Zaloguj się, aby "
            "Custom HikeUp uwzględnił doświadczenie i preferencje profilu."
        )
        profile_evaluation = {
            "personalization_enabled": False,
            "experience_level": None,
            "recommendation_status": "unpersonalized",
            "message": message,
            "warnings": [],
        }
        metrics.execution_time_ms = round(
            (perf_counter() - start_time) * 1000,
            3,
        )
        metrics_data = metrics.as_dict()
        metrics_data.update(
            {
                "custom_score": None,
                "baseline_reused": bool(baseline_route),
                "personalization_enabled": False,
            }
        )
        return build_algorithm_result(
            algorithm="custom_hikeup",
            path=baseline_path,
            totals=baseline_totals,
            metrics=metrics_data,
            criterion=criterion,
            route_weight=baseline_weight,
            profile_evaluation=profile_evaluation,
            warnings=[],
            extra={
                "custom_score": None,
                "personalization_enabled": False,
                "recommendation_status": "unpersonalized",
                "message": message,
            },
        )

    if baseline_path:
        candidate_paths.append(("dijkstra_baseline", baseline_path))

    if criterion == "distance" and baseline_path:
        distance_reference_path = baseline_path
    else:
        scores, previous = _search_graph(
            graph,
            start,
            lambda edge, _neighbor: edge_weight(edge, "distance"),
            metrics,
            end=end,
        )
        distance_reference_path = _path_from_search(scores, previous, end)
        if distance_reference_path:
            candidate_paths.append(
                ("shortest_distance_reference", distance_reference_path)
            )

    custom_scores, custom_previous = _search_graph(
        graph,
        start,
        lambda edge, neighbor: custom_hikeup_edge_weight(
            edge,
            criterion,
            profile_limits,
            shelter_nearby=neighbor in shelter_node_ids,
        ),
        metrics,
        end=end,
    )
    profile_candidate_path = _path_from_search(
        custom_scores,
        custom_previous,
        end,
    )
    if profile_candidate_path:
        candidate_paths.append(("profile_weighted", profile_candidate_path))

    strict_criteria = dict.fromkeys(
        (criterion, "difficulty", "distance", "time", "elevation")
    )
    for candidate_criterion in strict_criteria:
        scores, previous = _search_graph(
            graph,
            start,
            lambda edge, _neighbor, selected=candidate_criterion: edge_weight(
                edge,
                selected,
            ),
            metrics,
            end=end,
            edge_allowed=lambda edge: _profile_edge_allowed(
                edge,
                profile_limits,
            ),
        )
        strict_path = _path_from_search(scores, previous, end)
        if strict_path:
            candidate_paths.append(
                (f"profile_constrained_{candidate_criterion}", strict_path)
            )

    if not candidate_paths:
        return None

    baseline_distance = 0.0
    if distance_reference_path:
        distance_totals = calculate_route_totals(
            distance_reference_path,
            edges,
            nodes=nodes,
            points=points,
            edge_map=edge_lookup,
            node_lookup=node_lookup,
        )
        baseline_distance = max(
            0.0,
            as_number(distance_totals.get("distance_km"), 0),
        )

    candidates = []
    seen_paths = {}
    for source, candidate_path in candidate_paths:
        path_key = tuple(candidate_path)
        if path_key in seen_paths:
            seen_paths[path_key]["sources"].append(source)
            continue

        totals = calculate_route_totals(
            candidate_path,
            edges,
            nodes=nodes,
            points=points,
            edge_map=edge_lookup,
            node_lookup=node_lookup,
        )
        detour_ratio = None
        if baseline_distance > 0:
            detour_ratio = totals["distance_km"] / baseline_distance

        evaluation = evaluate_route_profile(
            candidate_path,
            totals,
            edge_lookup,
            profile_limits,
            detour_ratio=detour_ratio,
        )
        candidate = {
            "source": source,
            "sources": [source],
            "path": candidate_path,
            "totals": totals,
            "evaluation": evaluation,
            "route_weight": _path_criterion_weight(
                candidate_path,
                edge_lookup,
                criterion,
            ),
            "custom_score": calculate_custom_path_score(
                candidate_path,
                edge_lookup,
                criterion,
                profile_limits,
                shelter_node_ids,
            ),
        }
        seen_paths[path_key] = candidate
        candidates.append(candidate)

    recommendable = [
        candidate
        for candidate in candidates
        if candidate["evaluation"]["within_safety_limits"]
        and candidate["evaluation"]["reasonable_detour"]
    ]
    preferred_detour = [
        candidate
        for candidate in recommendable
        if not candidate["evaluation"]["detour_preference_exceeded"]
    ]
    selection_pool = preferred_detour or recommendable
    standard_selection_pool = selection_pool
    shelter_preference_enabled = bool(
        profile_limits.get("prefer_shelters", False)
    )
    shelter_preference_rerouted = False

    if shelter_preference_enabled and selection_pool:
        shortest_acceptable_distance = min(
            candidate["totals"]["distance_km"]
            for candidate in selection_pool
        )
        shelter_extra_ratio = max(
            1.0,
            as_number(
                profile_limits.get(
                    "shelter_preference_max_extra_ratio",
                    1.10,
                ),
                1.10,
            ),
        )
        nearby_shelter_candidates = [
            candidate
            for candidate in selection_pool
            if candidate["totals"]["distance_km"]
            <= shortest_acceptable_distance * shelter_extra_ratio + 1e-9
        ]
        maximum_shelters = max(
            (
                candidate["totals"].get("shelters_count", 0)
                for candidate in nearby_shelter_candidates
            ),
            default=0,
        )
        if maximum_shelters > 0:
            selection_pool = [
                candidate
                for candidate in nearby_shelter_candidates
                if candidate["totals"].get("shelters_count", 0)
                == maximum_shelters
            ]

    metrics.execution_time_ms = round(
        (perf_counter() - start_time) * 1000,
        3,
    )

    if selection_pool:
        standard_selected = min(
            standard_selection_pool,
            key=lambda candidate: (
                candidate["route_weight"],
                candidate["totals"]["distance_km"],
            ),
        )
        selected = min(
            selection_pool,
            key=lambda candidate: (
                candidate["route_weight"],
                candidate["totals"]["distance_km"],
            ),
        )
        shelter_preference_rerouted = (
            shelter_preference_enabled
            and selected["path"] != standard_selected["path"]
        )
        path = selected["path"]
        totals = selected["totals"]
        custom_score = selected["custom_score"]
        comparable_route_weight = selected["route_weight"]
        profile_evaluation = selected["evaluation"]
        profile_evaluation.update(
            {
                "recommendation_status": "recommended",
                "message": (
                    "Znaleziono bezpieczną trasę przy schronisku, zgodną "
                    "z preferencjami profilu."
                    if shelter_preference_enabled
                    and totals.get("shelters_count", 0) > 0
                    else "Znaleziono trasę odpowiednią dla profilu."
                ),
                "selection_reason": (
                    "safe_with_shelter_within_extra_limit"
                    if shelter_preference_rerouted
                    else (
                        "safe_within_preferred_detour"
                        if preferred_detour
                        else "safe_within_acceptable_detour"
                    )
                ),
                "shelter_preference_enabled": shelter_preference_enabled,
                "shelter_preference_matched": (
                    shelter_preference_enabled
                    and totals.get("shelters_count", 0) > 0
                ),
                "shelter_preference_rerouted": shelter_preference_rerouted,
                "candidate_count": len(candidates),
                "acceptable_candidate_count": len(recommendable),
                "selected_candidate_sources": selected["sources"],
            }
        )
        if not preferred_detour:
            profile_evaluation["warnings"].insert(
                0,
                "Wybrano dłuższą trasę, ponieważ pozostaje zgodna z "
                "profilem i mieści się w rozsądnej granicy objazdu.",
            )
        if shelter_preference_rerouted:
            profile_evaluation["warnings"].insert(
                0,
                "Wybrano nieznacznie dłuższy wariant przy schronisku. "
                "Pozostaje bezpieczny i nie przekracza 10% dodatkowego "
                "dystansu względem najkrótszej akceptowalnej trasy.",
            )

        metrics_data = metrics.as_dict()
        metrics_data.update(
            {
                "custom_score": round(custom_score, 3),
                "candidate_custom_score": round(
                    custom_scores.get(end, custom_score),
                    3,
                ),
                "fallback_applied": False,
                "detour_ratio": profile_evaluation["detour_ratio"],
                "candidate_count": len(candidates),
            }
        )
        return build_algorithm_result(
            algorithm="custom_hikeup",
            path=path,
            totals=totals,
            metrics=metrics_data,
            criterion=criterion,
            route_weight=comparable_route_weight,
            profile_evaluation=profile_evaluation,
            warnings=profile_evaluation["warnings"],
            extra={
                "custom_score": round(custom_score, 3),
                "recommendation_status": "recommended",
                "message": profile_evaluation["message"],
            },
        )

    reasonable_candidates = [
        candidate
        for candidate in candidates
        if candidate["evaluation"]["reasonable_detour"]
    ]
    difficult_selection_pool = reasonable_candidates or candidates
    easiest_available = min(
        difficult_selection_pool,
        key=lambda candidate: (
            len(candidate["evaluation"]["safety_violations"]),
            -candidate["evaluation"]["profile_match_score"],
            candidate["totals"]["max_difficulty"],
            candidate["totals"]["max_slope_percent"],
            candidate["totals"]["elevation_gain_m"],
            candidate["route_weight"],
        ),
    )
    difficult_evaluation = easiest_available["evaluation"]
    message = (
        "To najłatwiejszy rozsądny wariant do wybranego celu, ale trasa "
        "nadal jest wymagająca dla Twojego profilu."
    )
    profile_evaluation = {
        **difficult_evaluation,
        "recommendation_status": "difficult_route",
        "message": message,
        "fallback_applied": False,
        "fallback_reason": None,
        "selection_reason": "easiest_reasonable_route_to_requested_goal",
        "shelter_preference_enabled": shelter_preference_enabled,
        "shelter_preference_matched": (
            shelter_preference_enabled
            and easiest_available["totals"].get("shelters_count", 0) > 0
        ),
        "shelter_preference_rerouted": False,
        "candidate_count": len(candidates),
        "acceptable_candidate_count": 0,
        "selected_candidate_sources": easiest_available["sources"],
        "warnings": list(difficult_evaluation["warnings"]),
    }
    metrics.execution_time_ms = round(
        (perf_counter() - start_time) * 1000,
        3,
    )
    metrics_data = metrics.as_dict()
    metrics_data.update(
        {
            "custom_score": round(easiest_available["custom_score"], 3),
            "candidate_custom_score": round(
                custom_scores.get(end, 0.0),
                3,
            ),
            "fallback_applied": False,
            "detour_ratio": difficult_evaluation["detour_ratio"],
            "candidate_count": len(candidates),
        }
    )

    return build_algorithm_result(
        algorithm="custom_hikeup",
        path=easiest_available["path"],
        totals=easiest_available["totals"],
        metrics=metrics_data,
        criterion=criterion,
        route_weight=easiest_available["route_weight"],
        profile_evaluation=profile_evaluation,
        warnings=profile_evaluation["warnings"],
        extra={
            "custom_score": round(easiest_available["custom_score"], 3),
            "recommendation_status": "difficult_route",
            "message": message,
            "alternative_destinations": [],
        },
    )


def find_profile_suitable_destination_alternatives(
    nodes,
    edges,
    start,
    destinations,
    criterion,
    user_limits,
    points=None,
    reference_distance_km=None,
    reference_route_totals=None,
    reference_profile_match_score=None,
    max_results=3,
    routing_context=None,
):
    """Znajduje podobne cele osiągalne trasą zgodną z profilem.

    ``destinations`` zawiera punkty POI z przypisanym ``routing_node_id`` i
    wynikiem podobieństwa do pierwotnego celu. Cele są oceniane na ścieżkach
    profilowo ograniczonych oraz na łagodnym przebiegu zapasowym, dzięki czemu
    można wskazać wariant wyraźnie łatwiejszy nawet wtedy, gdy żaden cel górski
    nie mieści się w stu procentach w limitach profilu.
    """
    validate_criterion(criterion)
    profile_limits = {
        **get_limits("intermediate"),
        **(user_limits or {}),
    }
    graph = (
        routing_context.graph
        if routing_context is not None
        else build_graph(edges)
    )
    if start not in graph:
        return []

    destinations_by_node = {}
    for destination in destinations:
        routing_node_id = destination.get("routing_node_id")
        if routing_node_id in graph:
            destinations_by_node.setdefault(routing_node_id, []).append(
                destination
            )

    if not destinations_by_node:
        return []

    shelter_node_ids = (
        routing_context.shelter_node_ids
        if routing_context is not None
        else get_shelter_routing_node_ids(points)
    )
    metrics = SearchMetrics()
    scores, previous = _search_graph(
        graph,
        start,
        lambda edge, neighbor: custom_hikeup_edge_weight(
            edge,
            "difficulty",
            profile_limits,
            shelter_nearby=neighbor in shelter_node_ids,
        ),
        metrics,
        target_ids=destinations_by_node,
        edge_allowed=lambda edge: _profile_edge_allowed(
            edge,
            profile_limits,
        ),
    )
    relaxed_scores, relaxed_previous = _search_graph(
        graph,
        start,
        lambda edge, neighbor: custom_hikeup_edge_weight(
            edge,
            "difficulty",
            profile_limits,
            shelter_nearby=neighbor in shelter_node_ids,
        ),
        metrics,
        target_ids=destinations_by_node,
    )
    edge_lookup = (
        routing_context.edges_by_nodes
        if routing_context is not None
        else build_edge_map(edges)
    )
    node_lookup = (
        routing_context.nodes_by_id
        if routing_context is not None
        else None
    )
    max_route_ratio = max(
        1.0,
        as_number(
            profile_limits.get("alternative_destination_max_route_ratio"),
            1.35,
        ),
    )
    reference_distance = max(
        0.0,
        as_number(reference_distance_km, 0),
    )
    max_route_distance = None
    if reference_distance > 0:
        max_route_distance = max(
            reference_distance * max_route_ratio,
            reference_distance + 2.0,
        )

    reference_totals = reference_route_totals or {}
    reference_match_score = as_number(reference_profile_match_score, 0)
    alternatives = []
    for routing_node_id, destination_group in destinations_by_node.items():
        path_options = []
        seen_paths = set()
        for search_scores, search_previous in (
            (scores, previous),
            (relaxed_scores, relaxed_previous),
        ):
            path = _path_from_search(
                search_scores,
                search_previous,
                routing_node_id,
            )
            path_key = tuple(path or ())
            if len(path_key) < 2 or path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            totals = calculate_route_totals(
                path,
                edges,
                nodes=nodes,
                points=points,
                edge_map=edge_lookup,
                node_lookup=node_lookup,
            )
            if (
                max_route_distance is not None
                and totals["distance_km"] > max_route_distance
            ):
                continue

            evaluation = evaluate_route_profile(
                path,
                totals,
                edge_lookup,
                profile_limits,
            )
            fully_profile_suitable = evaluation["within_safety_limits"]
            comparison_metrics = (
                "max_difficulty",
                "max_slope_percent",
                "elevation_gain_m",
            )
            no_harder_than_requested = bool(reference_totals) and all(
                as_number(totals.get(metric), 0)
                <= as_number(reference_totals.get(metric), 0) + 1e-9
                for metric in comparison_metrics
            )
            meaningfully_easier = no_harder_than_requested and any(
                as_number(totals.get(metric), 0)
                < as_number(reference_totals.get(metric), 0) - 1e-9
                for metric in comparison_metrics
            )
            easier_than_requested = (
                meaningfully_easier
                and evaluation["profile_match_score"]
                > reference_match_score + 1e-9
            )
            if not fully_profile_suitable and not easier_than_requested:
                continue

            path_options.append(
                {
                    "path": path,
                    "totals": totals,
                    "evaluation": evaluation,
                    "fully_profile_suitable": fully_profile_suitable,
                    "easier_than_requested": easier_than_requested,
                    "route_weight": _path_criterion_weight(
                        path,
                        edge_lookup,
                        criterion,
                    ),
                }
            )

        if not path_options:
            continue

        selected_path = min(
            path_options,
            key=lambda option: (
                not option["fully_profile_suitable"],
                not option["evaluation"]["within_limits"],
                -option["evaluation"]["profile_match_score"],
                option["route_weight"],
            ),
        )
        totals = selected_path["totals"]
        evaluation = selected_path["evaluation"]
        fully_profile_suitable = selected_path["fully_profile_suitable"]
        easier_than_requested = selected_path["easier_than_requested"]
        route_weight = selected_path["route_weight"]
        for destination in destination_group:
            point = destination["point"]
            alternatives.append(
                {
                    "id": point.get("id"),
                    "name": point.get("name", "Alternatywny cel"),
                    "type": point.get("type"),
                    "lat": point.get("lat"),
                    "lng": point.get("lng", point.get("lon")),
                    "elevation": point.get("elevation"),
                    "routing_node_id": routing_node_id,
                    "distance_from_requested_km": round(
                        as_number(
                            destination.get("distance_from_requested_km"),
                            0,
                        ),
                        2,
                    ),
                    "similarity_score": round(
                        as_number(destination.get("similarity_score"), 0),
                        3,
                    ),
                    "same_destination_type": bool(
                        destination.get("same_destination_type", True)
                    ),
                    "route": {
                        "distance_km": totals["distance_km"],
                        "time_min": totals["time_min"],
                        "elevation_gain_m": totals["elevation_gain_m"],
                        "max_slope_percent": totals["max_slope_percent"],
                        "max_difficulty": totals["max_difficulty"],
                        "profile_match_score": evaluation[
                            "profile_match_score"
                        ],
                        "within_preferred_limits": evaluation[
                            "within_limits"
                        ],
                        "within_safety_limits": fully_profile_suitable,
                        "easier_than_requested": easier_than_requested,
                        "recommendation_kind": (
                            "profile_suitable"
                            if fully_profile_suitable
                            else "easier_than_requested"
                        ),
                        "route_weight": round(route_weight, 3),
                    },
                }
            )

    fully_suitable_alternatives = [
        alternative
        for alternative in alternatives
        if alternative["route"]["within_safety_limits"]
    ]
    selection_pool = fully_suitable_alternatives or alternatives
    selection_pool.sort(
        key=lambda alternative: (
            not alternative["route"]["within_preferred_limits"],
            not alternative["same_destination_type"],
            -alternative["route"]["profile_match_score"],
            alternative["similarity_score"],
            alternative["route"]["route_weight"],
        )
    )
    return selection_pool[:max_results]
