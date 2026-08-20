import unittest

from algorithms.astar import calculate_route as calculate_astar
from algorithms.common import (
    build_graph,
    calculate_route_totals,
    calculate_route_weight,
    make_directional_edge,
)
from algorithms.custom import calculate_route as calculate_custom
from algorithms.dijkstra import calculate_route as calculate_dijkstra
from algorithms.greedy import calculate_route as calculate_greedy
from algorithms.weights import (
    custom_hikeup_edge_weight,
    edge_weight,
)
from models.experience_config import get_limits
from routes.map_routes import build_single_route_response
from scripts.fill_edge_elevation_data import (
    calculate_hiking_time_minutes,
    update_edges,
)


NODES = [
    {
        "id": "lower",
        "lat": 49.0,
        "lng": 19.0,
        "elevation": 100,
    },
    {
        "id": "upper",
        "lat": 49.001,
        "lng": 19.001,
        "elevation": 220,
    },
]

EDGE = {
    "from": "lower",
    "to": "upper",
    "distance_km": 1.0,
    "time_min": 10,
    "difficulty": 2,
    "elevation_change_m": 120,
    "elevation_gain_m": 120,
    "elevation_loss_m": 0,
    "slope_percent": 12,
}


class DirectionalElevationTests(unittest.TestCase):
    def test_reverse_edge_swaps_gain_and_loss(self):
        reverse_edge = make_directional_edge(
            EDGE,
            "upper",
            "lower",
        )

        self.assertEqual(reverse_edge["from"], "upper")
        self.assertEqual(reverse_edge["to"], "lower")
        self.assertEqual(reverse_edge["elevation_gain_m"], 0)
        self.assertEqual(reverse_edge["elevation_loss_m"], 120)
        self.assertEqual(reverse_edge["elevation_change_m"], -120)

    def test_reverse_graph_uses_directional_elevation(self):
        graph = build_graph([EDGE])
        reverse_edge = graph["upper"][0]["edge"]

        self.assertEqual(reverse_edge["elevation_gain_m"], 0)
        self.assertEqual(reverse_edge["elevation_loss_m"], 120)

    def test_totals_and_weight_depend_on_route_direction(self):
        uphill = calculate_route_totals(
            ["lower", "upper"],
            [EDGE],
        )
        downhill = calculate_route_totals(
            ["upper", "lower"],
            [EDGE],
        )

        self.assertEqual(uphill["elevation_gain_m"], 120)
        self.assertEqual(uphill["elevation_loss_m"], 0)
        self.assertEqual(downhill["elevation_gain_m"], 0)
        self.assertEqual(downhill["elevation_loss_m"], 120)
        self.assertEqual(
            calculate_route_weight(
                ["lower", "upper"],
                [EDGE],
                "elevation",
            ),
            130,
        )
        self.assertEqual(
            calculate_route_weight(
                ["upper", "lower"],
                [EDGE],
                "elevation",
            ),
            10,
        )

    def test_missing_gain_and_loss_are_derived_from_change(self):
        edge = {
            "from": "lower",
            "to": "upper",
            "elevation_change_m": 30,
        }

        forward = make_directional_edge(
            edge,
            "lower",
            "upper",
        )
        reverse = make_directional_edge(
            edge,
            "upper",
            "lower",
        )

        self.assertEqual(forward["elevation_gain_m"], 30)
        self.assertEqual(forward["elevation_loss_m"], 0)
        self.assertEqual(reverse["elevation_gain_m"], 0)
        self.assertEqual(reverse["elevation_loss_m"], 30)


class ElevationAlgorithmsTests(unittest.TestCase):
    def test_all_algorithms_return_directional_totals(self):
        algorithms = [
            calculate_dijkstra,
            calculate_astar,
            calculate_greedy,
        ]

        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm.__module__):
                uphill = algorithm(
                    NODES,
                    [EDGE],
                    "lower",
                    "upper",
                    "elevation",
                )
                downhill = algorithm(
                    NODES,
                    [EDGE],
                    "upper",
                    "lower",
                    "elevation",
                )

                self.assertEqual(
                    uphill["totals"]["elevation_gain_m"],
                    120,
                )
                self.assertEqual(
                    downhill["totals"]["elevation_gain_m"],
                    0,
                )
                self.assertEqual(
                    downhill["totals"]["elevation_loss_m"],
                    120,
                )

        uphill_custom = calculate_custom(
            NODES,
            [EDGE],
            "lower",
            "upper",
            "elevation",
        )
        downhill_custom = calculate_custom(
            NODES,
            [EDGE],
            "upper",
            "lower",
            "elevation",
        )

        self.assertEqual(
            uphill_custom["totals"]["elevation_gain_m"],
            120,
        )
        self.assertEqual(
            downhill_custom["totals"]["elevation_gain_m"],
            0,
        )
        self.assertEqual(
            downhill_custom["totals"]["elevation_loss_m"],
            120,
        )

    def test_api_response_contains_elevation_gain(self):
        result = calculate_dijkstra(
            NODES,
            [EDGE],
            "lower",
            "upper",
            "elevation",
        )
        response = build_single_route_response(
            algorithm_key="dijkstra",
            algorithm_label="Dijkstra",
            route_result=result,
            routing_nodes=NODES,
            routing_edges=[EDGE],
            start_point=None,
            end_point=None,
            criterion="elevation",
        )

        self.assertEqual(response["total_elevation_gain_m"], 120)

    def test_extreme_slope_artifact_has_bounded_cost(self):
        limits = get_limits("intermediate")
        regular_edge = {
            **EDGE,
            "slope_percent": 100,
        }
        corrupted_edge = {
            **EDGE,
            "slope_percent": 10000,
        }

        self.assertEqual(
            custom_hikeup_edge_weight(
                regular_edge,
                "time",
                limits,
            ),
            custom_hikeup_edge_weight(
                corrupted_edge,
                "time",
                limits,
            ),
        )

    def test_difficulty_cost_does_not_depend_on_edge_count(self):
        complete_edge = {
            **EDGE,
            "distance_km": 1.0,
            "difficulty": 3,
            "elevation_change_m": 0,
            "elevation_gain_m": 0,
            "elevation_loss_m": 0,
        }
        half_edge = {
            **complete_edge,
            "distance_km": 0.5,
        }

        self.assertAlmostEqual(
            edge_weight(complete_edge, "difficulty"),
            edge_weight(half_edge, "difficulty") * 2,
        )

    def test_custom_keeps_safe_detour_within_absolute_limit(self):
        nodes = [
            {"id": "start", "lat": 49.0, "lng": 19.0, "elevation": 100},
            {"id": "middle", "lat": 49.005, "lng": 19.005, "elevation": 100},
            {"id": "end", "lat": 49.01, "lng": 19.01, "elevation": 100},
        ]
        edges = [
            {
                "from": "start",
                "to": "end",
                "distance_km": 1.0,
                "difficulty": 6,
                "elevation_change_m": 0,
                "elevation_gain_m": 0,
                "elevation_loss_m": 0,
                "slope_percent": 100,
            },
            {
                "from": "start",
                "to": "middle",
                "distance_km": 0.75,
                "difficulty": 1,
                "elevation_change_m": 0,
                "elevation_gain_m": 0,
                "elevation_loss_m": 0,
                "slope_percent": 0,
            },
            {
                "from": "middle",
                "to": "end",
                "distance_km": 0.75,
                "difficulty": 1,
                "elevation_change_m": 0,
                "elevation_gain_m": 0,
                "elevation_loss_m": 0,
                "slope_percent": 0,
            },
        ]
        baseline_route = calculate_dijkstra(
            nodes,
            edges,
            "start",
            "end",
            "distance",
        )
        limits = {
            **get_limits("beginner"),
            "max_detour_ratio": 1.2,
        }

        result = calculate_custom(
            nodes,
            edges,
            "start",
            "end",
            "time",
            limits,
            baseline_route,
        )

        self.assertEqual(result["path"], ["start", "middle", "end"])
        self.assertFalse(result["profile_evaluation"]["fallback_applied"])
        self.assertEqual(
            result["profile_evaluation"]["recommendation_status"],
            "recommended",
        )
        self.assertTrue(
            result["profile_evaluation"]["detour_preference_exceeded"]
        )
        self.assertEqual(
            result["profile_evaluation"]["detour_ratio"],
            1.5,
        )


class ElevationDataScriptTests(unittest.TestCase):
    def test_positive_micro_edge_time_does_not_round_to_zero(self):
        self.assertEqual(
            calculate_hiking_time_minutes(0.0001, 0),
            0.01,
        )

    def test_update_edges_populates_directional_fields(self):
        map_data = {
            "nodes": [dict(node) for node in NODES],
            "edges": [
                {
                    "from": "lower",
                    "to": "upper",
                    "distance_km": 1.0,
                }
            ],
        }

        statistics = update_edges(map_data)
        edge = map_data["edges"][0]

        self.assertEqual(statistics["updated"], 1)
        self.assertEqual(edge["elevation_change_m"], 120)
        self.assertEqual(edge["elevation_gain_m"], 120)
        self.assertEqual(edge["elevation_loss_m"], 0)
        self.assertEqual(edge["slope_percent"], 12)

    def test_update_edges_caps_unreliable_slope(self):
        map_data = {
            "nodes": [
                {"id": "a", "elevation": 100},
                {"id": "b", "elevation": 400},
            ],
            "edges": [
                {
                    "from": "a",
                    "to": "b",
                    "distance_km": 0.001,
                }
            ],
        }

        statistics = update_edges(map_data)
        edge = map_data["edges"][0]

        self.assertEqual(statistics["suspicious_slope"], 1)
        self.assertEqual(statistics["corrected_slope_capped"], 1)
        self.assertEqual(edge["slope_percent"], 100)

    def test_update_edges_spreads_dem_step_over_short_way(self):
        nodes = [
            {
                "id": f"n{index}",
                "elevation": 100 if index < 5 else 118,
            }
            for index in range(11)
        ]
        edges = [
            {
                "from": f"n{index}",
                "to": f"n{index + 1}",
                "distance_km": 0.01,
                "osm_way_id": "way/test",
            }
            for index in range(10)
        ]
        map_data = {"nodes": nodes, "edges": edges}

        statistics = update_edges(map_data)

        self.assertEqual(statistics["raw_zero_slope"], 9)
        self.assertEqual(statistics["raw_slope_above_100"], 1)
        self.assertEqual(statistics["corrected_zero_slope"], 0)
        self.assertTrue(
            all(edge["slope_percent"] == 10 for edge in edges)
        )
        self.assertEqual(
            map_data["routing_data_metadata"]["slope_calculation"]["window_m"],
            180.0,
        )


if __name__ == "__main__":
    unittest.main()
