"""Testy preferencji schronisk bez API i bazy danych."""
import math
import pytest
from unittest.mock import patch
from algorithms.common import build_edge_map, get_shelter_proximity_strength
from algorithms.custom import _build_shelter_proximity_lookup, calculate_custom_path_score, calculate_route
from algorithms.weights import custom_hikeup_edge_weight, edge_weight
from models.experience_config import apply_shelter_preference, get_limits
from services.routing_context import build_routing_context

def node_at_distance(node_id, distance_m):
    return {'id': node_id, 'lat': 49.0 + math.degrees(distance_m / 6371000.0), 'lng': 20.0, 'elevation': 100}

def flat_edge(start, end, distance_km):
    return {'from': start, 'to': end, 'distance_km': distance_km, 'time_min': distance_km * 12, 'difficulty': 1, 'slope_percent': 0, 'elevation_gain_m': 0, 'elevation_loss_m': 0, 'elevation_change_m': 0}
HUT = {**node_at_distance('hut/H', 0), 'type': 'alpine_hut', 'nearest_routing_node_id': 'H', 'distance_to_trail_m': 0}

@pytest.mark.parametrize(
    "distance, expected",
    [(0, 1), (25, 0.99), (50, 0.98), (75, 0.965), (100, 0.95),
     (175, 0.625), (250, 0.3), (375, 0.175),
     (500, 0.05), (750, 0.025), (1000, 0), (1500, 0)],
)
def test_strength_at_boundaries_and_between_them(distance, expected):
    strength = get_shelter_proximity_strength(node_at_distance('N', distance), [HUT])
    assert strength == pytest.approx(expected)

def test_only_shelter_types_with_coordinates_affect_strength():
    node = node_at_distance('N', 0)
    for points in ([], [{**HUT, 'type': 'peak'}], [{'type': 'alpine_hut'}]):
        assert get_shelter_proximity_strength(node, points) == 0
    assert get_shelter_proximity_strength(node, [{**HUT, 'type': 'shelter'}]) == 1

def test_bonus_is_applied_once_and_only_when_enabled():
    edge = flat_edge('A', 'B', 1)
    disabled = get_limits('intermediate')
    enabled = apply_shelter_preference(disabled, True)
    original = custom_hikeup_edge_weight(edge, 'distance', disabled)
    for strength in (0, 0.5, 0.85, 1):
        actual = custom_hikeup_edge_weight(edge, 'distance', enabled, strength)
        expected_bonus = edge_weight(edge, 'distance') * enabled['shelter_bonus_factor'] * strength
        assert original - actual == pytest.approx(expected_bonus)
        assert actual > 0
    assert custom_hikeup_edge_weight(edge, 'distance', {**enabled, 'prefer_shelters': False}, 1) == original

def test_lookup_caches_per_call_and_skips_disabled_preference():
    nodes = [node_at_distance('N', 500)]
    enabled = apply_shelter_preference(get_limits('intermediate'), True)
    lookup = _build_shelter_proximity_lookup(nodes, [HUT], enabled)
    other_lookup = _build_shelter_proximity_lookup(nodes, [HUT], enabled)
    disabled_lookup = _build_shelter_proximity_lookup(nodes, [HUT], {})
    with patch('algorithms.custom.get_shelter_proximity_strength', wraps=get_shelter_proximity_strength) as calculate:
        assert disabled_lookup('N') == 0
        calculate.assert_not_called()
        assert lookup('N') == pytest.approx(0.05)
        assert lookup('N') == pytest.approx(0.05)
        assert calculate.call_count == 1
        assert other_lookup('N') == pytest.approx(0.05)
        assert calculate.call_count == 2

def test_custom_start_to_end_chooses_shelter_detour():
    nodes = [node_at_distance('S', 2000), {**node_at_distance('A', 1500), 'lng': 20.04}, node_at_distance('B', 500), node_at_distance('H', 0), node_at_distance('T', -2000)]
    edges = [flat_edge('S', 'A', 2.0), flat_edge('A', 'T', 2.0), flat_edge('S', 'B', 1.6), flat_edge('B', 'H', 0.5), flat_edge('H', 'T', 2.1)]
    disabled = get_limits('intermediate')
    enabled = apply_shelter_preference(disabled, True)
    baseline = calculate_route(nodes, edges, 'S', 'T', 'distance', disabled, points=[HUT])
    preferred = calculate_route(nodes, edges, 'S', 'T', 'distance', enabled, points=[HUT])
    assert baseline['path'] == ['S', 'A', 'T']
    assert baseline['totals']['shelters_count'] == 0
    assert preferred['path'] == ['S', 'B', 'H', 'T']
    assert preferred['totals']['shelters_count'] == 1
    assert preferred['totals']['distance_km'] == pytest.approx(4.2)
    lookup = _build_shelter_proximity_lookup(nodes, [HUT], enabled)
    expected_score = calculate_custom_path_score(preferred['path'], build_edge_map(edges), 'distance', enabled, lookup)
    assert preferred['custom_score'] == pytest.approx(expected_score, abs=0.0005)
    approach = edges[2]
    assert custom_hikeup_edge_weight(approach, 'distance', enabled, lookup('B')) < custom_hikeup_edge_weight(approach, 'distance', disabled)
    context_result = calculate_route(nodes, edges, 'S', 'T', 'distance', enabled, points=[HUT], routing_context=build_routing_context(nodes, edges, [HUT]))
    assert context_result['path'] == preferred['path']
    assert context_result['custom_score'] == preferred['custom_score']


@pytest.mark.parametrize("prefer_shelters, middle", [(False, "B"), (True, "H")])
def test_final_selection_uses_custom_cost_only_with_shelter_preference(prefer_shelters, middle):
    # Obie trasy są w pobliżu tego samego schroniska. Liczba schronisk nie
    # rozstrzyga wyboru: dłuższy wariant musi wygrać dzięki kosztowi Custom.
    nodes = [node_at_distance("S", 2000), node_at_distance("B", 500),
             node_at_distance("H", 0), node_at_distance("T", -2000)]
    edges = [flat_edge("S", "B", 2), flat_edge("B", "T", 2),
             flat_edge("S", "H", 2.1), flat_edge("H", "T", 2.1)]
    limits = apply_shelter_preference(get_limits("intermediate"), prefer_shelters)
    result = calculate_route(
        nodes, edges, "S", "T", "distance", limits, points=[HUT]
    )
    assert result["path"] == ["S", middle, "T"]
    assert result["totals"]["shelters_count"] == 1
    if prefer_shelters:
        lookup = _build_shelter_proximity_lookup(nodes, [HUT], limits)
        shorter_cost = calculate_custom_path_score(
            ["S", "B", "T"], build_edge_map(edges), "distance", limits, lookup
        )
        assert result["custom_score"] < shorter_cost
        assert result["totals"]["distance_km"] == pytest.approx(4.2)
