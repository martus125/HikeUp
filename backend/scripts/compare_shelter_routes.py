"""Porównanie Custom na rzeczywistej mapie, bez API i bazy danych.

Uruchom z backendu: python scripts/compare_shelter_routes.py
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms.common import SHELTER_TYPES, calculate_route_totals
from algorithms.custom import (
    _build_shelter_proximity_lookup,
    calculate_custom_path_score,
    calculate_route,
)
from models.experience_config import EXPERIENCE_LIMITS, apply_shelter_preference, get_limits
from services.map_service import get_point_by_id
from services.routing_context import load_routing_context


START_POI_ID = "node/3633357479"
END_POI_ID = "relation/8626083"
START_NODE_ID = "node/5100098610"
END_NODE_ID = "node/3047874937"
HUT_POI_ID = "way/358407058"


def compare_routes(profile="intermediate", criterion="distance"):
    context = load_routing_context()
    start = get_point_by_id(context.points, START_POI_ID)
    end = get_point_by_id(context.points, END_POI_ID)
    if start is None or end is None:
        raise ValueError("Nie znaleziono wskazanych punktów POI na mapie.")
    for point, expected in ((start, START_NODE_ID), (end, END_NODE_ID)):
        if point.get("nearest_routing_node_id") != expected:
            raise ValueError(f"Zmieniło się przypisanie węzła dla {point['id']}.")
        if expected not in context.nodes_by_id:
            raise ValueError(f"Brak węzła {expected} w grafie.")

    results = {}
    for label, enabled in (("without_preference", False), ("with_preference", True)):
        route = calculate_route(
            context.nodes, context.edges, START_NODE_ID, END_NODE_ID,
            criterion=criterion,
            user_limits=apply_shelter_preference(get_limits(profile), enabled),
            points=context.points,
            routing_context=context,
        )
        if route is None:
            raise ValueError(f"Nie znaleziono trasy: {label}.")
        path_ids = set(route["path"])
        shelters = [
            {"name": point.get("name", point["id"]),
             "routing_node_id": point.get("nearest_routing_node_id") or point.get("routing_node_id")}
            for point in context.points
            if point.get("type") in SHELTER_TYPES
            and (point.get("nearest_routing_node_id") or point.get("routing_node_id")) in path_ids
        ]
        results[label] = {"route": route, "shelter_nodes_on_path": shelters}

    baseline = results["without_preference"]["route"]
    preferred = results["with_preference"]["route"]
    hut = get_point_by_id(context.points, HUT_POI_ID)
    if hut is None:
        raise ValueError("Nie znaleziono Murowańca na mapie.")
    hut_node_id = hut.get("nearest_routing_node_id") or hut.get("routing_node_id")
    if hut_node_id not in context.nodes_by_id:
        raise ValueError("Brak przypisanego węzła Murowańca w grafie.")

    limits = apply_shelter_preference(get_limits(profile), True)
    proximity = _build_shelter_proximity_lookup(context.nodes_by_id, context.points, limits)

    def score(path):
        # Porównujemy koszty przed zaokrągleniem w odpowiedzi algorytmu.
        return calculate_custom_path_score(
            path, context.edges_by_nodes, criterion, limits, proximity
        )

    segments = []
    for source, target in ((START_NODE_ID, hut_node_id), (hut_node_id, END_NODE_ID)):
        segment = calculate_route(
            context.nodes, context.edges, source, target,
            criterion=criterion, user_limits=limits,
            points=context.points, routing_context=context,
        )
        if segment is None:
            raise ValueError(f"Nie znaleziono odcinka {source} -> {target}.")
        segments.append({"route": segment, "custom_cost": score(segment["path"])})

    combined_path = segments[0]["route"]["path"] + segments[1]["route"]["path"][1:]
    combined_score = score(combined_path)
    segment_sum = sum(segment["custom_cost"] for segment in segments)
    if abs(combined_score - segment_sum) > 1e-9:
        raise ValueError("Koszt połączonej trasy nie zgadza się z sumą odcinków.")
    direct_score = score(preferred["path"])
    combined_totals = calculate_route_totals(
        combined_path, context.edges, nodes=context.nodes, points=context.points,
        edge_map=context.edges_by_nodes, node_lookup=context.nodes_by_id,
    )
    return {
        "start": {"name": start.get("name"), "routing_node_id": START_NODE_ID},
        "end": {"name": end.get("name"), "routing_node_id": END_NODE_ID},
        "profile": profile,
        "criterion": criterion,
        "path_changed": baseline["path"] != preferred["path"],
        "via_murowaniec": {
            "hut": {"name": hut.get("name"), "routing_node_id": hut_node_id},
            "segments": segments,
            "path": combined_path,
            "totals": combined_totals,
            "custom_cost": combined_score,
            "segments_custom_cost_sum": segment_sum,
            "direct_custom_cost": direct_score,
            "cost_difference_via_minus_direct": combined_score - direct_score,
            "via_is_cheaper": combined_score < direct_score,
            "hut_node_on_path": hut_node_id in combined_path,
            "repeated_node_count": len(combined_path) - len(set(combined_path)),
        },
        **results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(EXPERIENCE_LIMITS), default="intermediate")
    parser.add_argument("--criterion", choices=("distance", "time", "difficulty", "elevation"), default="distance")
    parser.add_argument("--output", type=Path, help="Zapis pełnych wyników i list ID do JSON.")
    args = parser.parse_args()
    report = compare_routes(args.profile, args.criterion)
    print(f"{report['start']['name']} -> {report['end']['name']}")
    print(f"Start: {START_NODE_ID}; cel: {END_NODE_ID}")
    print(f"Profil: {args.profile}; kryterium: {args.criterion}")
    limits = apply_shelter_preference(get_limits(args.profile), True)
    print(f"Bonus: {limits['shelter_bonus_factor']}; promień: {limits['shelter_preference_radius_m']} m")
    for label, title in (("without_preference", "prefer_shelters=False"), ("with_preference", "prefer_shelters=True")):
        result = report[label]
        route = result["route"]
        totals = route["totals"]
        print(f"\n{title}")
        print(f"  Dystans: {totals['distance_km']} km; czas: {totals['time_min']} min; węzły: {len(route['path'])}")
        print(f"  Status: {route.get('recommendation_status')}; koszt Custom: {route.get('custom_score')}")
        names = [hut['name'] for hut in result['shelter_nodes_on_path']]
        print(f"  Schroniska z przypisanym węzłem na trasie: {', '.join(names) or 'brak'}")
        print(f"  Schroniska w pobliżu trasy (osobna metryka): {totals['shelters_count']}")
        print(f"  Powód wyboru: {route.get('profile_evaluation', {}).get('selection_reason')}")
    print(f"\nCzy lista węzłów trasy się zmieniła: {'TAK' if report['path_changed'] else 'NIE'}")
    via = report["via_murowaniec"]
    print(f"\nWymuszony punkt pośredni: {via['hut']['name']} ({via['hut']['routing_node_id']})")
    for title, segment in zip(("Start -> Murowaniec", "Murowaniec -> cel"), via["segments"]):
        route = segment["route"]
        print(f"  {title}: {route['totals']['distance_km']} km; {route['totals']['time_min']} min; koszt Custom: {segment['custom_cost']:.6f}; status: {route.get('recommendation_status')}")
    print(f"  Łącznie: {via['totals']['distance_km']} km; {via['totals']['time_min']} min")
    print(f"  Koszt obecnej trasy z bonusem: {via['direct_custom_cost']:.6f}")
    print(f"  Suma kosztów odcinków przez schronisko: {via['segments_custom_cost_sum']:.6f}")
    print(f"  Różnica (przez schronisko minus obecna): {via['cost_difference_via_minus_direct']:+.6f}")
    print(f"  Czy przez schronisko jest taniej według Custom: {'TAK' if via['via_is_cheaper'] else 'NIE'}")
    print(f"  Węzeł Murowańca na trasie: {via['hut_node_on_path']}; powtórzone węzły: {via['repeated_node_count']}")
    print("  Odcinki wybrano osobno; połączona trasa nie przeszła ponownie filtrów całej trasy.")
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Pełne wyniki: {args.output.resolve()}")


if __name__ == "__main__":
    main()
