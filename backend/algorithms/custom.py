"""Custom HikeUp: wyszukiwanie kandydatów i wybór trasy według profilu.

Algorytm sprawdza znalezionych kandydatów, nie wszystkie możliwe ścieżki.
W tym pliku znajdują się również ocena profilu i propozycje łatwiejszych celów.
"""
import heapq
from time import perf_counter

from algorithms.common import (
    SHELTER_TYPES, SearchMetrics, build_algorithm_result, build_edge_map,
    build_graph, calculate_route_totals, get_shelter_proximity_strength,
    make_directional_edge, reconstruct_path,
)
from algorithms.weights import (
    MAX_REASONABLE_SLOPE_PERCENT, as_number, custom_hikeup_edge_weight,
    edge_weight, get_slope_percent, validate_criterion,
)
from models.experience_config import (
    PROFILE_MATCH_WEIGHTS, SHELTER_PREFERENCE_RADIUS_M, get_limits,
)


def _build_shelter_proximity_lookup(nodes, points, limits):
    """Odległość od schronisk obliczana najwyżej raz dla każdego węzła."""
    if not limits.get("prefer_shelters", False):
        return lambda node_id: 0.0
    node_items = nodes.values() if isinstance(nodes, dict) else nodes
    node_map = {
        node["id"]: node for node in node_items
        if isinstance(node, dict) and node.get("id") is not None
    }
    point_items = points.values() if isinstance(points, dict) else (points or [])
    shelters = [p for p in point_items if isinstance(p, dict) and p.get("type") in SHELTER_TYPES]
    radius = limits.get("shelter_preference_radius_m", SHELTER_PREFERENCE_RADIUS_M)
    strengths = {}

    def strength(node_id):
        if node_id not in strengths:
            strengths[node_id] = get_shelter_proximity_strength(
                node_map.get(node_id), shelters, radius_m=radius,
            )
        return strengths[node_id]

    return strength


def _path_cost(path, edge_lookup, criterion, limits=None, proximity=None):
    """Wspólne sumowanie kosztu klasycznego albo profilowego ścieżki."""
    cost = 0.0
    for start, end in zip(path, path[1:]):
        source = edge_lookup.get((start, end))
        if source is None:
            continue
        edge = make_directional_edge(source, start, end)
        if limits is None:
            cost += edge_weight(edge, criterion)
        else:
            cost += custom_hikeup_edge_weight(
                edge, criterion, limits,
                shelter_proximity_strength=proximity(end) if proximity else 0.0,
            )
    return cost


def _search_graph(graph, start, weight_function, metrics, end=None,
                  target_ids=None, edge_allowed=None):
    """Przeszukiwanie jednokosztowe do jednego lub kilku celów."""
    scores, previous = {start: 0.0}, {start: None}
    queue = [(0.0, start)]
    remaining = set(target_ids or ())
    metrics.queue_pushes += 1
    while queue:
        score, current = heapq.heappop(queue)
        if score > scores.get(current, float("inf")):
            continue
        metrics.visited_nodes += 1
        if end is not None and current == end:
            break
        if current in remaining:
            remaining.remove(current)
            if not remaining:
                break
        for neighbor_data in graph.get(current, []):
            metrics.analyzed_edges += 1
            neighbor, edge = neighbor_data["node"], neighbor_data["edge"]
            if edge_allowed is not None and not edge_allowed(edge):
                continue
            new_score = score + weight_function(edge, neighbor)
            if new_score >= scores.get(neighbor, float("inf")):
                continue
            scores[neighbor], previous[neighbor] = new_score, current
            heapq.heappush(queue, (new_score, neighbor))
            metrics.queue_pushes += 1
    return scores, previous


def _build_profile_edge_filter(limits):
    """Stałe progi są odczytywane raz, a nie przy każdej krawędzi."""
    difficulty_limit = max(1.0, as_number(limits.get("max_difficulty"), 4))
    slope_limit = max(
        as_number(limits.get("max_slope_percent"), 25),
        as_number(limits.get("absolute_max_slope_percent"), MAX_REASONABLE_SLOPE_PERCENT),
    )
    reasonable_slope = as_number(
        limits.get("max_reasonable_slope_percent"), MAX_REASONABLE_SLOPE_PERCENT,
    )

    def allowed(edge):
        difficulty = max(1.0, as_number(edge.get("difficulty"), 1))
        slope = min(get_slope_percent(edge), reasonable_slope)
        return difficulty <= difficulty_limit and slope <= slope_limit

    return allowed


def evaluate_route_profile(path, totals, edge_lookup, user_limits, detour_ratio=None):
    """Sprawdza ograniczenia i oblicza ocenę dopasowania gotowej trasy."""
    max_slope = max(5.0, as_number(user_limits.get("max_slope_percent"), 25))
    absolute_slope = max(max_slope, as_number(
        user_limits.get("absolute_max_slope_percent"), MAX_REASONABLE_SLOPE_PERCENT,
    ))
    max_difficulty = max(1.0, as_number(user_limits.get("max_difficulty"), 4))
    max_gain = max(0.0, as_number(user_limits.get("max_elevation_gain_m"), 700))
    max_steep = max(0.0, as_number(user_limits.get("max_consecutive_steep"), 1000))
    max_detour = max(1.0, as_number(user_limits.get("max_detour_ratio"), 1.35))
    absolute_detour = max(max_detour, as_number(
        user_limits.get("max_acceptable_detour_ratio"), max_detour,
    ))
    reasonable_slope = max(max_slope, as_number(
        user_limits.get("max_reasonable_slope_percent"), MAX_REASONABLE_SLOPE_PERCENT,
    ))
    current_steep = longest_steep = steep_distance = invalid_slopes = 0
    for start, end in zip(path, path[1:]):
        source = edge_lookup.get((start, end))
        if source is None:
            continue
        edge = make_directional_edge(source, start, end)
        distance = max(0.0, as_number(edge.get("distance_km"), 0) * 1000)
        raw_slope = get_slope_percent(edge)
        invalid_slopes += raw_slope > reasonable_slope
        if min(raw_slope, reasonable_slope) > max_slope:
            current_steep += distance
            steep_distance += distance
            longest_steep = max(longest_steep, current_steep)
        else:
            current_steep = 0.0

    effective_slope = min(totals["max_slope_percent"], reasonable_slope)
    elevation_exceeded = max_gain > 0 and totals["elevation_gain_m"] > max_gain
    difficulty_exceeded = totals["max_difficulty"] > max_difficulty
    slope_exceeded = effective_slope > max_slope
    absolute_slope_exceeded = effective_slope > absolute_slope
    steep_exceeded = max_steep > 0 and longest_steep > max_steep
    detour_exceeded = detour_ratio is not None and detour_ratio > max_detour
    detour_unreasonable = detour_ratio is not None and detour_ratio > absolute_detour
    # Kolejność kontroli zachowuje kolejność komunikatów i naruszeń.
    checks = [
        ("max_slope_exceeded", slope_exceeded,
         "Trasa przekracza preferowane nachylenie profilu.", False),
        ("absolute_max_slope_exceeded", absolute_slope_exceeded,
         "Trasa przekracza bezwzględną granicę nachylenia profilu.", True),
        ("max_difficulty_exceeded", difficulty_exceeded,
         f"Trasa zawiera odcinek o trudności {totals['max_difficulty']:g}, "
         f"a limit profilu wynosi {max_difficulty:g}.", True),
        ("elevation_gain_exceeded", elevation_exceeded,
         f"Przewyższenie przekracza limit profilu o {round(totals['elevation_gain_m'] - max_gain)} m.", True),
        ("steep_section_exceeded", steep_exceeded,
         "Najdłuższy stromy fragment przekracza limit profilu.", True),
        ("detour_ratio_exceeded", detour_exceeded,
         "Łagodniejszy wariant przekracza preferowany limit objazdu.", False),
        ("detour_unreasonable", detour_unreasonable,
         "Objazd jest zbyt długi, aby uznać go za rozsądną alternatywę.", False),
    ]
    violations, safety_violations, warnings = [], [], []
    for name, exceeded, message, safety in checks:
        if exceeded:
            violations.append(name)
            warnings.append(message)
            if safety:
                safety_violations.append(name)
    if invalid_slopes:
        warnings.append("Na trasie wykryto niewiarygodne dane nachylenia; "
                        "ich wpływ na wybór trasy został ograniczony.")

    score = 0.0
    components = [
        (effective_slope, max_slope, PROFILE_MATCH_WEIGHTS["slope"]),
        (as_number(totals.get("max_difficulty"), 0), max_difficulty, PROFILE_MATCH_WEIGHTS["difficulty"]),
        (as_number(totals.get("elevation_gain_m"), 0), max_gain, PROFILE_MATCH_WEIGHTS["elevation"]),
        (detour_ratio if detour_ratio is not None else 0, max_detour, PROFILE_MATCH_WEIGHTS["detour"]),
    ]
    for value, limit, weight in components:
        if limit <= 0 or value <= limit:
            score += weight
        else:
            excess = (value - limit) / max(limit, 1.0)
            score += weight * max(0.0, 1.0 - excess)
    if as_number(user_limits.get("shelter_bonus_factor"), 0) <= 0 or totals.get("shelters_count", 0) > 0:
        score += PROFILE_MATCH_WEIGHTS["shelters"]

    limits = {
        "max_slope_percent": max_slope, "absolute_max_slope_percent": absolute_slope,
        "max_difficulty": max_difficulty, "max_elevation_gain_m": max_gain,
        "max_consecutive_steep_m": max_steep,
        "preferred_elevation_per_hour": as_number(user_limits.get("preferred_elevation_per_hour"), 250),
        "max_detour_ratio": max_detour, "max_acceptable_detour_ratio": absolute_detour,
    }
    route = {key: totals[key] for key in (
        "max_slope_percent", "average_slope_percent", "max_difficulty",
        "average_difficulty", "elevation_gain_m", "shelters_count",
    )}
    route.update(steep_distance_m=round(steep_distance), max_consecutive_steep_m=round(longest_steep))
    return {
        "experience_level": user_limits.get("experience_level", "intermediate"),
        "detour_ratio": round(detour_ratio, 3) if detour_ratio is not None else None,
        "limits": limits, "route": route, "violations": violations,
        "safety_violations": safety_violations, "warnings": warnings,
        "profile_match_score": round(max(0.0, min(100.0, score)), 1),
        "within_limits": not violations, "within_safety_limits": not safety_violations,
        "reasonable_detour": not detour_unreasonable,
        "detour_preference_exceeded": detour_exceeded,
    }


def calculate_route(nodes, edges, start, end, criterion="time", user_limits=None,
                    baseline_route=None, points=None, routing_context=None,
                    personalization_enabled=True):
    """Tworzy warianty, ocenia ograniczenia i wybiera najlepszy z kandydatów."""
    start_time = perf_counter()
    validate_criterion(criterion)
    limits = {**get_limits("intermediate"), **(user_limits or {})}
    graph = routing_context.graph if routing_context is not None else build_graph(edges)
    edge_lookup = routing_context.edges_by_nodes if routing_context is not None else build_edge_map(edges)
    node_lookup = routing_context.nodes_by_id if routing_context is not None else None
    metrics = SearchMetrics()
    if start not in graph or end not in graph:
        return None

    def search(selected_criterion, constrained=False, profile_weight=False,
               route_start=start, route_end=end, allowed_edges=None):
        if profile_weight:
            weight = lambda edge, neighbor: custom_hikeup_edge_weight(
                edge, selected_criterion, limits, shelter_proximity_strength=proximity(neighbor),
            )
        else:
            weight = lambda edge, neighbor: edge_weight(edge, selected_criterion)
        scores, previous = _search_graph(
            graph, route_start, weight, metrics, end=route_end,
            edge_allowed=allowed_edges if allowed_edges is not None else edge_filter if constrained else None,
        )
        path = reconstruct_path(previous, route_end) if route_end in scores else None
        return path, scores.get(route_end)

    def totals_for(path):
        key = tuple(path)
        if key not in totals_cache:
            totals_cache[key] = calculate_route_totals(
                path, edges, nodes=nodes, points=points,
                edge_map=edge_lookup, node_lookup=node_lookup,
            )
        return totals_cache[key]

    totals_cache = {}
    reuse_baseline = bool(baseline_route and baseline_route.get("path")
                          and baseline_route.get("criterion", criterion) == criterion)
    if reuse_baseline:
        baseline_path = baseline_route["path"]
        baseline_weight = baseline_route.get("route_weight")
    else:
        baseline_path, baseline_weight = search(criterion)
    if not personalization_enabled:
        if not baseline_path:
            return None
        totals = baseline_route.get("totals") if baseline_route else None
        totals = totals or totals_for(baseline_path)
        if baseline_weight is None:
            baseline_weight = _path_cost(baseline_path, edge_lookup, criterion)
        message = ("Trasa ogólna według wybranego kryterium. Zaloguj się, aby "
                   "Custom HikeUp uwzględnił doświadczenie i preferencje profilu.")
        evaluation = {
            "personalization_enabled": False, "experience_level": None,
            "recommendation_status": "unpersonalized", "message": message, "warnings": [],
        }
        metrics.execution_time_ms = round((perf_counter() - start_time) * 1000, 3)
        return build_algorithm_result(
            algorithm="custom_hikeup", path=baseline_path, totals=totals,
            criterion=criterion, route_weight=baseline_weight, profile_evaluation=evaluation,
            metrics={**metrics.as_dict(), "custom_score": None,
                     "baseline_reused": bool(baseline_route), "personalization_enabled": False},
            warnings=[], extra={"custom_score": None, "personalization_enabled": False,
                                "recommendation_status": "unpersonalized", "message": message},
        )

    prefer_shelters = bool(limits.get("prefer_shelters", False))
    # Najpierw zwykły wariant profilowy; bliskość schroniska nie obniża kosztów.
    limits = {**limits, "prefer_shelters": False, "shelter_bonus_factor": 0.0}
    proximity = lambda node_id: 0.0
    edge_filter = _build_profile_edge_filter(limits)
    candidate_paths = [("dijkstra_baseline", baseline_path)] if baseline_path else []
    distance_path = baseline_path
    if criterion != "distance" or not baseline_path:
        distance_path, _ = search("distance")
        if distance_path:
            candidate_paths.append(("shortest_distance_reference", distance_path))
    profile_path, profile_cost = search(criterion, profile_weight=True)
    if profile_path:
        candidate_paths.append(("profile_weighted", profile_path))
    for selected_criterion in dict.fromkeys((criterion, "difficulty", "distance", "time", "elevation")):
        path, _ = search(selected_criterion, constrained=True)
        if path:
            candidate_paths.append((f"profile_constrained_{selected_criterion}", path))
    if not candidate_paths:
        return None

    baseline_distance = max(0.0, as_number(totals_for(distance_path).get("distance_km"), 0)) if distance_path else 0.0
    candidates, seen = [], {}
    for source, path in candidate_paths:
        key = tuple(path)
        if key in seen:
            seen[key]["sources"].append(source)
            continue
        totals = totals_for(path)
        detour = totals["distance_km"] / baseline_distance if baseline_distance > 0 else None
        candidate = {
            "sources": [source], "path": path, "totals": totals,
            "evaluation": evaluate_route_profile(path, totals, edge_lookup, limits, detour),
            "route_weight": _path_cost(path, edge_lookup, criterion),
            "custom_score": _path_cost(path, edge_lookup, criterion, limits, proximity),
        }
        seen[key] = candidate
        candidates.append(candidate)

    acceptable = [c for c in candidates if c["evaluation"]["within_safety_limits"]
                  and c["evaluation"]["reasonable_detour"]]
    preferred = [c for c in acceptable if not c["evaluation"]["detour_preference_exceeded"]]
    pool = preferred or acceptable
    rerouted = False
    shelter_reason = "preference_disabled"
    point_items = routing_context.points if routing_context is not None else (points or [])
    if isinstance(point_items, dict):
        point_items = point_items.values()
    shelter_ids = {p.get("nearest_routing_node_id") for p in point_items
                   if p.get("type") in SHELTER_TYPES} & graph.keys()
    if pool:
        selected = min(pool, key=lambda c: (c["route_weight"], c["totals"]["distance_km"]))
        status = "recommended"
        message = ("Znaleziono trasę przez schronisko, zgodną z limitami profilu."
                   if prefer_shelters and shelter_ids.intersection(selected["path"])
                   else "Znaleziono trasę odpowiednią dla profilu.")
        reason = ("safe_with_shelter_within_extra_limit" if rerouted else
                  "safe_within_preferred_detour" if preferred else "safe_within_acceptable_detour")
    else:
        reasonable = [c for c in candidates if c["evaluation"]["reasonable_detour"]]
        selected = min(reasonable or candidates, key=lambda c: (
            len(c["evaluation"]["safety_violations"]), -c["evaluation"]["profile_match_score"],
            c["totals"]["max_difficulty"], c["totals"]["max_slope_percent"],
            c["totals"]["elevation_gain_m"], c["route_weight"],
        ))
        status = "difficult_route"
        message = ("To najłatwiejszy rozsądny wariant do wybranego celu, ale trasa "
                   "nadal jest wymagająca dla Twojego profilu.")
        reason = "easiest_reasonable_route_to_requested_goal"

    if prefer_shelters:
        standard = selected
        reference = standard["totals"]
        # Przy trudnej trasie zachowujemy trudność i nachylenie wariantu podstawowego.
        shelter_edge_filter = edge_filter if pool else _build_profile_edge_filter({
            **limits, "max_difficulty": reference["max_difficulty"],
            "max_slope_percent": reference["max_slope_percent"] + 0.01,
            "absolute_max_slope_percent": reference["max_slope_percent"] + 0.01,
        })
        shelter_options = []
        shelter_reason = "no_shelter_variant_within_limits"
        for shelter_id in sorted(shelter_ids):
            if shelter_id in standard["path"]:
                shelter_options.append(standard)
                continue
            first, _ = search(criterion, allowed_edges=shelter_edge_filter,
                              route_start=start, route_end=shelter_id)
            second, _ = search(criterion, allowed_edges=shelter_edge_filter,
                               route_start=shelter_id, route_end=end)
            if not first or not second:
                continue
            path = first + second[1:]
            totals = totals_for(path)
            detour = totals["distance_km"] / baseline_distance if baseline_distance else None
            assessment = evaluate_route_profile(path, totals, edge_lookup, limits, detour)
            checks = {
                "profile_limits": (assessment["within_safety_limits"] if pool else
                    set(assessment["safety_violations"]).issubset(standard["evaluation"]["safety_violations"])),
                "detour_limit": assessment["reasonable_detour"],
                "slope_limit": totals["max_slope_percent"] <= reference["max_slope_percent"] + 1e-9,
                "consecutive_steep_limit": (limits.get("max_consecutive_steep_m", 0) <= 0
                    or assessment["route"]["max_consecutive_steep_m"] <= max(
                    standard["evaluation"]["route"]["max_consecutive_steep_m"],
                    standard["evaluation"]["limits"]["max_consecutive_steep_m"])),
                "distance_limit": totals["distance_km"] <= reference["distance_km"] * limits["shelter_preference_max_extra_ratio"] + 1e-9,
                "time_ratio_limit": totals["time_min"] <= reference["time_min"] * limits["shelter_preference_max_time_ratio"] + 1e-9,
                "extra_time_limit": totals["time_min"] <= reference["time_min"] + limits["shelter_preference_max_extra_time_min"] + 1e-9,
                "extra_ascent_limit": totals["elevation_gain_m"] <= reference["elevation_gain_m"] + limits["shelter_preference_max_extra_gain_m"] + 1e-9,
                "difficulty_limit": totals["max_difficulty"] <= reference["max_difficulty"],
            }
            candidate = {
                "shelter_node_id": shelter_id,
                "sources": ["via_shelter"], "path": path, "totals": totals,
                "evaluation": assessment,
                "route_weight": _path_cost(path, edge_lookup, criterion),
                "custom_score": _path_cost(path, edge_lookup, criterion, limits, proximity),
            }
            candidates.append(candidate)
            if all(checks.values()):
                shelter_options.append(candidate)
            # Zapis powodów odrzucenia umożliwia sprawdzenie decyzji w odpowiedzi API.
            candidate["shelter_rejection_reasons"] = [k for k, passed in checks.items() if not passed]
        if shelter_options:
            selected = min(shelter_options, key=lambda c: (c["route_weight"], c["totals"]["distance_km"]))
            rerouted = selected["path"] != standard["path"]
            shelter_reason = "shelter_node_visited_within_limits"
            if status == "difficult_route":
                message = ("Wybrano wariant przez schronisko w granicach dodatkowego wysiłku, "
                           "ale trasa nadal przekracza limity Twojego profilu.")
                reason = "difficult_route_with_shelter_within_extra_limit"
            else:
                message = "Znaleziono trasę przez schronisko, zgodną z limitami profilu."
                reason = "safe_with_shelter_within_extra_limit"

    evaluation = {
        **selected["evaluation"], "recommendation_status": status, "message": message,
        "selection_reason": reason, "shelter_preference_enabled": prefer_shelters,
        "shelter_preference_matched": prefer_shelters and bool(shelter_ids.intersection(selected["path"])),
        "shelter_preference_reason": shelter_reason,
        "shelter_rejected_variants": [
            {"shelter_node_id": c["shelter_node_id"], "reasons": c["shelter_rejection_reasons"]}
            for c in candidates if c.get("shelter_rejection_reasons")
        ],
        "shelter_preference_rerouted": rerouted, "candidate_count": len(candidates),
        "acceptable_candidate_count": sum(c["evaluation"]["within_safety_limits"]
                                          and c["evaluation"]["reasonable_detour"] for c in candidates),
        "selected_candidate_sources": selected["sources"],
        "warnings": list(selected["evaluation"]["warnings"]),
    }
    if status == "recommended" and not preferred:
        evaluation["warnings"].insert(0, "Wybrano dłuższą trasę, ponieważ pozostaje zgodna z "
                                     "profilem i mieści się w rozsądnej granicy objazdu.")
    if rerouted:
        evaluation["warnings"].insert(0, "Wybrano przejście przez schronisko w granicach "
                                     "dodatkowego dystansu, czasu i podejścia.")
    score = round(selected["custom_score"], 3)
    metrics.execution_time_ms = round((perf_counter() - start_time) * 1000, 3)
    extra = {"custom_score": score, "recommendation_status": status, "message": message}
    if status == "difficult_route":
        extra["alternative_destinations"] = []
    return build_algorithm_result(
        algorithm="custom_hikeup", path=selected["path"], totals=selected["totals"],
        criterion=criterion, route_weight=selected["route_weight"],
        profile_evaluation=evaluation, warnings=evaluation["warnings"], extra=extra,
        metrics={**metrics.as_dict(), "custom_score": score,
                 "candidate_custom_score": round(profile_cost if profile_cost is not None else
                                                   selected["custom_score"] if pool else 0.0, 3),
                 "fallback_applied": False, "detour_ratio": evaluation["detour_ratio"],
                 "candidate_count": len(candidates)},
    )


def find_profile_suitable_destination_alternatives(
    nodes, edges, start, destinations, criterion, user_limits, points=None,
    reference_distance_km=None, reference_route_totals=None,
    reference_profile_match_score=None, max_results=3, routing_context=None,
):
    """Proponuje inne cele, które spełniają limity lub są wyraźnie łatwiejsze."""
    validate_criterion(criterion)
    limits = {**get_limits("intermediate"), **(user_limits or {})}
    graph = routing_context.graph if routing_context is not None else build_graph(edges)
    if start not in graph:
        return []
    by_node = {}
    for destination in destinations:
        node_id = destination.get("routing_node_id")
        if node_id in graph:
            by_node.setdefault(node_id, []).append(destination)
    if not by_node:
        return []
    edge_lookup = routing_context.edges_by_nodes if routing_context is not None else build_edge_map(edges)
    node_lookup = routing_context.nodes_by_id if routing_context is not None else None
    proximity = _build_shelter_proximity_lookup(
        node_lookup if node_lookup is not None else nodes,
        routing_context.points if routing_context is not None else points, limits,
    )
    weight = lambda edge, neighbor: custom_hikeup_edge_weight(
        edge, "difficulty", limits, shelter_proximity_strength=proximity(neighbor),
    )
    metrics = SearchMetrics()
    searches = [
        _search_graph(graph, start, weight, metrics, target_ids=by_node,
                      edge_allowed=_build_profile_edge_filter(limits)),
        _search_graph(graph, start, weight, metrics, target_ids=by_node),
    ]
    ratio = max(1.0, as_number(limits.get("alternative_destination_max_route_ratio"), 1.35))
    reference_distance = max(0.0, as_number(reference_distance_km, 0))
    max_distance = max(reference_distance * ratio, reference_distance + 2.0) if reference_distance > 0 else None
    reference_totals = reference_route_totals or {}
    reference_score = as_number(reference_profile_match_score, 0)
    comparison_metrics = ("max_difficulty", "max_slope_percent", "elevation_gain_m")
    alternatives = []
    for node_id, destination_group in by_node.items():
        options, seen = [], set()
        for scores, previous in searches:
            path = reconstruct_path(previous, node_id) if node_id in scores else None
            key = tuple(path or ())
            if len(key) < 2 or key in seen:
                continue
            seen.add(key)
            totals = calculate_route_totals(
                path, edges, nodes=nodes, points=points,
                edge_map=edge_lookup, node_lookup=node_lookup,
            )
            if max_distance is not None and totals["distance_km"] > max_distance:
                continue
            evaluation = evaluate_route_profile(path, totals, edge_lookup, limits)
            suitable = evaluation["within_safety_limits"]
            no_harder = bool(reference_totals) and all(
                as_number(totals.get(k), 0) <= as_number(reference_totals.get(k), 0) + 1e-9
                for k in comparison_metrics
            )
            easier = (no_harder and any(
                as_number(totals.get(k), 0) < as_number(reference_totals.get(k), 0) - 1e-9
                for k in comparison_metrics)
                      and evaluation["profile_match_score"] > reference_score + 1e-9)
            if suitable or easier:
                options.append({
                    "totals": totals, "evaluation": evaluation, "suitable": suitable,
                    "easier": easier, "weight": _path_cost(path, edge_lookup, criterion),
                })
        if not options:
            continue
        selected = min(options, key=lambda o: (
            not o["suitable"], not o["evaluation"]["within_limits"],
            -o["evaluation"]["profile_match_score"], o["weight"],
        ))
        totals, evaluation = selected["totals"], selected["evaluation"]
        for destination in destination_group:
            point = destination["point"]
            alternatives.append({
                "id": point.get("id"), "name": point.get("name", "Alternatywny cel"),
                "type": point.get("type"), "lat": point.get("lat"),
                "lng": point.get("lng", point.get("lon")), "elevation": point.get("elevation"),
                "routing_node_id": node_id,
                "distance_from_requested_km": round(as_number(destination.get("distance_from_requested_km"), 0), 2),
                "similarity_score": round(as_number(destination.get("similarity_score"), 0), 3),
                "same_destination_type": bool(destination.get("same_destination_type", True)),
                "route": {
                    **{k: totals[k] for k in ("distance_km", "time_min", "elevation_gain_m",
                                             "max_slope_percent", "max_difficulty")},
                    "profile_match_score": evaluation["profile_match_score"],
                    "within_preferred_limits": evaluation["within_limits"],
                    "within_safety_limits": selected["suitable"],
                    "easier_than_requested": selected["easier"],
                    "recommendation_kind": "profile_suitable" if selected["suitable"] else "easier_than_requested",
                    "route_weight": round(selected["weight"], 3),
                },
            })
    suitable = [a for a in alternatives if a["route"]["within_safety_limits"]]
    pool = suitable or alternatives
    pool.sort(key=lambda a: (
        not a["route"]["within_preferred_limits"], not a["same_destination_type"],
        -a["route"]["profile_match_score"], a["similarity_score"], a["route"]["route_weight"],
    ))
    return pool[:max_results]
