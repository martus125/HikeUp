"""Testy preferencji schronisk bez API i bazy danych."""
import math
import pytest
from unittest.mock import patch
from algorithms.common import build_edge_map, get_shelter_proximity_strength
from algorithms.custom import _build_shelter_proximity_lookup, calculate_route
from algorithms.weights import custom_hikeup_edge_weight, edge_weight
from models.experience_config import apply_shelter_preference, get_limits
from services.routing_context import build_routing_context

def node_at_distance(node_id, distance_m):
    return {'id': node_id, 'lat': 49.0 + math.degrees(distance_m / 6371000.0), 'lng': 20.0, 'elevation': 100}

def flat_edge(start, end, distance_km):
    return {'from': start, 'to': end, 'distance_km': distance_km, 'time_min': distance_km * 12, 'difficulty': 1, 'slope_percent': 0, 'elevation_gain_m': 0, 'elevation_loss_m': 0, 'elevation_change_m': 0}
SHELTER = {**node_at_distance('shelter/H', 0), 'type': 'shelter', 'nearest_routing_node_id': 'H', 'distance_to_trail_m': 0}

@pytest.mark.parametrize(
    "distance, expected",
    [(0, 1), (25, 0.99), (50, 0.98), (75, 0.965), (100, 0.95),
     (175, 0.625), (250, 0.3), (375, 0.175),
     (500, 0.05), (750, 0.025), (1000, 0), (1500, 0)],
)
def test_strength_at_boundaries_and_between_them(distance, expected):
    strength = get_shelter_proximity_strength(node_at_distance('N', distance), [SHELTER])
    assert strength == pytest.approx(expected)

def test_only_shelter_types_with_coordinates_affect_strength():
    node = node_at_distance('N', 0)
    for points in ([], [{**SHELTER, 'type': 'peak'}], [{'type': 'shelter'}]):
        assert get_shelter_proximity_strength(node, points) == 0
    assert get_shelter_proximity_strength(node, [{**SHELTER, 'type': 'shelter'}]) == 1

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
    lookup = _build_shelter_proximity_lookup(nodes, [SHELTER], enabled)
    other_lookup = _build_shelter_proximity_lookup(nodes, [SHELTER], enabled)
    disabled_lookup = _build_shelter_proximity_lookup(nodes, [SHELTER], {})
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
    baseline = calculate_route(nodes, edges, 'S', 'T', 'distance', disabled, points=[SHELTER])
    preferred = calculate_route(nodes, edges, 'S', 'T', 'distance', enabled, points=[SHELTER])
    assert baseline['path'] == ['S', 'A', 'T']
    assert baseline['totals']['shelters_count'] == 0
    assert preferred['path'] == ['S', 'B', 'H', 'T']
    assert preferred['totals']['shelters_count'] == 1
    assert preferred['totals']['distance_km'] == pytest.approx(4.2)
    assert preferred["profile_evaluation"]["shelter_preference_matched"]
    context_result = calculate_route(nodes, edges, 'S', 'T', 'distance', enabled, points=[SHELTER], routing_context=build_routing_context(nodes, edges, [SHELTER]))
    assert context_result['path'] == preferred['path']
    assert context_result['custom_score'] == preferred['custom_score']


@pytest.mark.parametrize("prefer_shelters, middle", [(False, "B"), (True, "H")])
def test_shelter_preference_requires_visiting_the_shelter_node(prefer_shelters, middle):
    # Bliskość shelter nie oznacza odwiedzenia jego węzła.
    nodes = [node_at_distance("S", 2000), node_at_distance("B", 500),
             node_at_distance("H", 0), node_at_distance("T", -2000)]
    edges = [flat_edge("S", "B", 2), flat_edge("B", "T", 2),
             flat_edge("S", "H", 2.1), flat_edge("H", "T", 2.1)]
    limits = apply_shelter_preference(get_limits("intermediate"), prefer_shelters)
    result = calculate_route(
        nodes, edges, "S", "T", "distance", limits, points=[SHELTER]
    )
    assert result["path"] == ["S", middle, "T"]
    assert result["totals"]["shelters_count"] == 1
    assert result["profile_evaluation"]["shelter_preference_matched"] == prefer_shelters
    if prefer_shelters:
        assert result["totals"]["distance_km"] == pytest.approx(4.2)


def test_overlapping_shelter_radii_do_not_depend_on_input_order():
    node = node_at_distance("N", 0)
    near = {**node_at_distance("shelter/near", 50), "type": "shelter"}
    far = {**node_at_distance("shelter/far", 500), "type": "shelter"}
    assert get_shelter_proximity_strength(node, [near, far]) == pytest.approx(.98)
    assert get_shelter_proximity_strength(node, [far, near]) == pytest.approx(.98)


@pytest.mark.parametrize("mapping_key", ["routing_node_id", "nearest_routing_node_id", "node_id", "nearest_node"])
def test_shelter_mapping_uses_shared_resolver(mapping_key):
    nodes = [node_at_distance("S", 2000), node_at_distance("B", 500),
             node_at_distance("H", 0), node_at_distance("T", -2000)]
    edges = [flat_edge("S", "B", 2), flat_edge("B", "T", 2),
             flat_edge("S", "H", 2.1), flat_edge("H", "T", 2.1)]
    shelter = {key: value for key, value in SHELTER.items() if key != "nearest_routing_node_id"}
    shelter[mapping_key] = "H"
    result = calculate_route(nodes, edges, "S", "T", "distance",
                             apply_shelter_preference(get_limits("intermediate"), True), points=[shelter])
    assert result["path"] == ["S", "H", "T"]
    assert result["profile_evaluation"]["shelter_preference_matched"] is True


def test_shelter_cannot_extend_already_excessive_continuous_steep_section():
    nodes = [node_at_distance(key, 0) for key in ("S", "A", "H", "T")]
    edges = [flat_edge("S", "A", 1), flat_edge("A", "T", 1),
             flat_edge("S", "H", 1.05), flat_edge("H", "T", 1.05)]
    for index in (0, 2, 3):
        edges[index]["slope_percent"] = 30
    limits = apply_shelter_preference(get_limits("intermediate"), True)
    limits["max_consecutive_steep"] = 500
    result = calculate_route(nodes, edges, "S", "T", "distance", limits, points=[SHELTER])
    assert result["path"] == ["S", "A", "T"]
    assert result["recommendation_status"] == "difficult_route"
    evaluation = result["profile_evaluation"]
    assert evaluation["shelter_preference_matched"] is False
    assert "consecutive_steep_limit" in evaluation["shelter_rejected_variants"][0]["reasons"]


def test_shelter_elevation_limit_is_checked_on_both_legs_together():
    nodes = [node_at_distance(key, 0) for key in ("S", "A", "H", "T")]
    edges = [flat_edge("S", "A", 1), flat_edge("A", "T", 1),
             flat_edge("S", "H", 1.05), flat_edge("H", "T", 1.05)]
    for index in (2, 3):
        edges[index]["elevation_gain_m"] = 70
    limits = apply_shelter_preference(get_limits("intermediate"), True)
    limits.update(max_elevation_gain_m=100, shelter_preference_max_time_ratio=10,
                  shelter_preference_max_extra_time_min=1000, shelter_preference_max_extra_gain_m=1000)
    result = calculate_route(nodes, edges, "S", "T", "distance", limits, points=[SHELTER])
    assert result["path"] == ["S", "A", "T"]
    assert result["profile_evaluation"]["shelter_preference_matched"] is False
    assert "profile_limits" in result["profile_evaluation"]["shelter_rejected_variants"][0]["reasons"]


def test_api_normalizes_legacy_osm_shelter_type_without_mutating_source():
    from models.point_types import OSM_SHELTER_TYPE
    from services.map_service import load_points
    source = [{"id": "shelter/old", "type": OSM_SHELTER_TYPE}]
    load_points.cache_clear()
    try:
        with patch("services.map_service.load_json", return_value=source):
            assert load_points()[0]["type"] == "shelter"
        assert source[0]["type"] == OSM_SHELTER_TYPE
    finally:
        load_points.cache_clear()
