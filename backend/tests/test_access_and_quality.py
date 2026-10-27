"""Restrictions must affect every algorithm, its metrics, API and saved paths."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from algorithms.access import allowed_directions
from algorithms.common import build_graph, build_edge_map, calculate_route_totals, calculate_route_weight
from algorithms.dijkstra import calculate_route as dijkstra
from algorithms.astar import calculate_route as astar
from algorithms.greedy import calculate_route as greedy
from algorithms.custom import calculate_route as custom
from scripts.enrich_access_data import enrich
from scripts.generate_full_map import build_full_map
from services.routing_context import build_routing_context
from validation import saved_path_exists, ValidationError
from test_auth import auth_app

NODES = [dict(id=key, lat=49 + index * .001, lng=19, elevation=100 + index * 10)
         for index, key in enumerate(("A", "B", "C"))]


def edge(start="A", end="B", **extra):
    return {"from": start, "to": end, "distance_km": 1, "difficulty": 2,
            "difficulty_known": True, "access_tags_known": True,
            "elevation_gain_m": 10, "elevation_loss_m": 0, **extra}


@pytest.mark.parametrize("tags,expected", [
    ({}, (1, -1)), ({"foot": "no"}, ()), ({"access": "private"}, ()),
    ({"access": "no", "foot": "yes"}, (1, -1)),
    ({"access": "yes", "foot": "private"}, ()),
    ({"foot": "customers"}, ()), ({"foot": "permit"}, ()),
    ({"access": "forestry", "foot": "permissive"}, (1, -1)),
    ({"oneway:foot": "yes"}, (1,)), ({"oneway:foot": "-1"}, (-1,)),
    ({"oneway:foot": "reversible"}, ()),
    ({"highway": "path", "oneway": "yes"}, (1,)),
    ({"highway": "residential", "oneway": "yes"}, (1, -1)),
    ({"highway": "path", "oneway": "yes", "oneway:foot": "no"}, (1, -1)),
    ({"foot:backward": "no"}, (1,)), ({"foot:forward": "no"}, (-1,)),
    ({"access": "no", "foot:forward": "yes"}, (1,)),
    ({"access:forward": "no", "foot": "yes"}, (1, -1)),
    ({"oneway:foot": "yes", "osm_direction": -1}, (-1,)),
    ({"seasonal": "yes"}, ()), ({"seasonal": "winter"}, ()),
    ({"seasonal": "no"}, (1, -1)),
    ({"foot:conditional": "no @ (Nov 01-Apr 30)"}, ()),
    ({"access:conditional": "yes @ (sunrise-sunset)", "foot": "yes"}, ()),
    ({"oneway:foot:conditional": "yes @ (Jun-Sep)"}, ()),
    ({"opening_hours": "08:00-18:00"}, ()),
    ({"opening_hours": "24/7"}, (1, -1)),
    ({"closed": "yes"}, ()), ({"source_geometry_matches": False}, ()),
])
def test_pedestrian_access_policy(tags, expected):
    assert allowed_directions(edge(**tags)) == expected


@pytest.mark.parametrize("algorithm", [dijkstra, astar, greedy, custom])
@pytest.mark.parametrize("criterion", ["distance", "time", "difficulty", "elevation"])
def test_all_algorithms_respect_direction_and_closures(algorithm, criterion):
    edges = [edge(**{"oneway:foot": "yes"}), edge("B", "C", foot="no")]
    context = build_routing_context(NODES, edges, NODES)
    forward = algorithm(NODES, edges, "A", "B", criterion, routing_context=context)
    assert forward["path"] == ["A", "B"]
    assert forward["totals"]["elevation_gain_m"] == 10
    assert algorithm(NODES, edges, "B", "A", criterion, routing_context=context) is None
    assert algorithm(NODES, edges, "A", "C", criterion, routing_context=context) is None


def test_reversed_osm_orientation_preserves_correct_elevation():
    edges = [edge(**{"oneway:foot": "yes", "osm_direction": -1})]
    result = dijkstra(NODES, edges, "B", "A")
    assert result["totals"]["elevation_gain_m"] == 0
    assert result["totals"]["elevation_loss_m"] == 10
    assert ("A", "B") not in build_edge_map(edges)
    assert build_graph(edges)["A"] == []
    with pytest.raises(ValueError):
        calculate_route_totals(["A", "B"], edges)
    with pytest.raises(ValueError):
        calculate_route_weight(["A", "B"], edges, "distance")


def test_unknown_difficulty_is_weighted_by_distance_and_not_inferred_from_number():
    edges = [edge(), edge("B", "C", distance_km=3, difficulty_known=False)]
    totals = calculate_route_totals(["A", "B", "C"], edges)
    assert totals["unknown_difficulty_percent"] == 75
    assert totals["unknown_difficulty_distance_km"] == 3
    assert totals["unknown_difficulty_edges"] == 1
    assert totals["difficulty_known"] is False
    legacy = edge()
    del legacy["difficulty_known"]
    assert calculate_route_totals(["A", "B"], [legacy])["unknown_difficulty_percent"] == 100


def test_warnings_and_profile_assessment_are_explicit():
    known = dijkstra(NODES, [edge()], "A", "B")
    assert known["warnings"] == []
    unknown = custom(NODES, [edge(difficulty_known=False, access_tags_known=False)], "A", "B")
    assert len(unknown["warnings"]) >= 2
    assert unknown["profile_evaluation"]["assessment_complete"] is False


def snapshot():
    return {"osm3s": {"timestamp_osm_base": "2026-10-27T00:00:00Z"}, "elements": [
        {"type": "way", "id": 10, "nodes": [1, 2],
         "tags": {"highway": "path", "oneway:foot": "yes", "sac_scale": "mountain_hiking"}},
        {"type": "node", "id": 1, "lat": 49, "lon": 19},
        {"type": "node", "id": 2, "lat": 49.001, "lon": 19},
    ]}


def test_import_preserves_tags_and_unknown_sac_is_not_known():
    data = snapshot()
    imported = build_full_map(data)
    imported_edge = imported["edges"][0]
    assert allowed_directions(imported_edge) == (1,)
    assert imported_edge["difficulty_known"] is True
    data["elements"][0]["tags"]["sac_scale"] = "unsupported"
    assert build_full_map(data)["edges"][0]["difficulty_known"] is False


def test_enrichment_preserves_geometry_elevations_and_handles_reversed_edges():
    source = edge("node/2", "node/1", osm_way_id="way/10", geometry=[[1, 2], [3, 4]])
    data = {"nodes": deepcopy(NODES), "edges": [source]}
    before = deepcopy(data)
    stats = enrich(data, snapshot())
    assert stats["matched_edges"] == 1
    assert data["nodes"] == before["nodes"]
    for key in ("geometry", "elevation_gain_m", "elevation_loss_m", "distance_km"):
        assert source[key] == before["edges"][0][key]
    assert source["osm_direction"] == -1
    assert source["difficulty_source"] == "osm:sac_scale"
    assert allowed_directions(source) == (-1,)


def test_missing_or_changed_way_cannot_silently_remain_routable():
    for way_id in ("way/10", "way/999"):
        source = edge(osm_way_id=way_id)
        enrich({"edges": [source]}, snapshot())
        assert allowed_directions(source) == ()


def test_api_handles_one_way_sink_and_saved_favorite_direction(auth_app):
    edges = [edge(**{"oneway:foot": "yes"})]
    context = build_routing_context(NODES, edges, NODES)
    client = auth_app[0].test_client()
    with patch("routes.map_routes.load_routing_context", return_value=context):
        response = client.post("/api/route", json=dict(start="A", end="B"))
        assert response.status_code == 200
        assert len(response.json["routes"]) == 4
        assert response.json["routes"][0]["totals"]["difficulty_known"] is True
        assert client.post("/api/route", json=dict(start="B", end="A")).status_code == 404
    saved_path_exists(dict(start_id="A", end_id="B", node_ids=["A", "B"]), context)
    with pytest.raises(ValidationError):
        saved_path_exists(dict(start_id="B", end_id="A", node_ids=["B", "A"]), context)
