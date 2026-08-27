import unittest
import types
from unittest.mock import patch

from flask import Flask

from algorithms.astar import calculate_route as calculate_astar
from algorithms.common import calculate_route_totals
from algorithms.custom import (
    calculate_route as calculate_custom,
    find_profile_suitable_destination_alternatives,
)
from algorithms.dijkstra import calculate_route as calculate_dijkstra
from algorithms.greedy import calculate_route as calculate_greedy
from algorithms.weights import calculate_slope_percent
from models.experience_config import (
    apply_shelter_preference,
    criterion_from_route_preference,
    get_limits,
    infer_experience_level,
)
from routes.map_routes import (
    build_alternative_destination_candidates,
    map_bp,
)
from services.routing_context import build_routing_context
from services import routing_context as routing_context_module


NODES = [
    {"id": "A", "lat": 49.00, "lng": 19.00, "elevation": 100},
    {"id": "B", "lat": 49.00, "lng": 19.01, "elevation": 150},
    {"id": "C", "lat": 49.01, "lng": 19.00, "elevation": 100},
    {"id": "D", "lat": 49.01, "lng": 19.01, "elevation": 200},
]


def edge(start, end, distance, difficulty, gain, slope):
    return {
        "from": start,
        "to": end,
        "distance_km": distance,
        "time_min": distance / 5 * 60 + gain / 600 * 60,
        "difficulty": difficulty,
        "elevation_change_m": gain,
        "elevation_gain_m": gain,
        "elevation_loss_m": 0,
        "slope_percent": slope,
    }


EDGES = [
    edge("A", "B", 1.0, 5, 50, 25),
    edge("B", "D", 1.0, 5, 50, 25),
    edge("A", "C", 1.2, 1, 0, 2),
    edge("C", "D", 1.2, 1, 0, 2),
]

POINTS = [
    {
        "id": "hut/C",
        "name": "Schronisko testowe",
        "type": "alpine_hut",
        "lat": 49.01,
        "lng": 19.00,
        "nearest_routing_node_id": "C",
        "distance_to_trail_m": 10,
    }
]

CLASSIC_ALGORITHMS = (
    calculate_dijkstra,
    calculate_astar,
    calculate_greedy,
)


class ExperienceConfigTests(unittest.TestCase):
    def test_declared_experience_has_priority_over_every_age_band(self):
        self.assertEqual(infer_experience_level(15, "advanced"), "advanced")
        self.assertEqual(infer_experience_level(70, "expert"), "expert")
        self.assertEqual(infer_experience_level(70, "beginner"), "beginner")

    def test_age_selects_only_automatic_experience_levels(self):
        self.assertEqual(infer_experience_level(19, ""), "beginner")
        self.assertEqual(infer_experience_level(20, ""), "intermediate")
        self.assertEqual(infer_experience_level(40, ""), "intermediate")
        self.assertEqual(infer_experience_level(64, ""), "intermediate")
        self.assertEqual(infer_experience_level(65, ""), "senior")
        self.assertEqual(infer_experience_level(None, ""), "intermediate")

    def test_advanced_profile_has_no_hard_route_limits(self):
        limits = get_limits("advanced")

        self.assertEqual(limits["max_difficulty"], 6)
        self.assertEqual(limits["absolute_max_slope_percent"], 100)
        self.assertEqual(limits["max_elevation_gain_m"], 0)
        self.assertEqual(limits["max_consecutive_steep"], 0)

    def test_route_preference_maps_to_algorithm_criterion(self):
        self.assertEqual(
            criterion_from_route_preference("najkrótsza"),
            "distance",
        )
        self.assertEqual(
            criterion_from_route_preference("najłatwiejsza"),
            "difficulty",
        )
        self.assertEqual(criterion_from_route_preference(""), "time")

    def test_shelter_bonus_requires_explicit_preference(self):
        limits = get_limits("intermediate")
        self.assertFalse(limits["prefer_shelters"])
        self.assertEqual(limits["shelter_bonus_factor"], 0.0)

        preferred = apply_shelter_preference(limits, True)
        self.assertTrue(preferred["prefer_shelters"])
        self.assertGreater(preferred["shelter_bonus_factor"], 0.0)


class RoutingContextTests(unittest.TestCase):
    def test_cached_loader_builds_one_context_per_process(self):
        routing_context_module.load_routing_context.cache_clear()
        try:
            with patch(
                "services.routing_context.load_full_map",
                return_value={"nodes": NODES, "edges": EDGES},
            ) as load_map, patch(
                "services.routing_context.load_points",
                return_value=POINTS,
            ) as load_test_points:
                first = routing_context_module.load_routing_context()
                second = routing_context_module.load_routing_context()

            self.assertIs(first, second)
            self.assertIs(first.nodes, NODES)
            self.assertIs(first.edges, EDGES)
            self.assertEqual(first.node_ids, {"A", "B", "C", "D"})
            self.assertEqual(first.shelter_node_ids, {"C"})
            load_map.assert_called_once_with()
            load_test_points.assert_called_once_with()
        finally:
            routing_context_module.load_routing_context.cache_clear()

    def test_context_preserves_paths_totals_and_route_weights(self):
        context = build_routing_context(NODES, EDGES, POINTS)

        for algorithm in CLASSIC_ALGORITHMS:
            with self.subTest(algorithm=algorithm.__module__):
                regular = algorithm(
                    NODES,
                    EDGES,
                    "A",
                    "D",
                    "distance",
                    POINTS,
                )
                shared = algorithm(
                    NODES,
                    EDGES,
                    "A",
                    "D",
                    "distance",
                    POINTS,
                    context,
                )
                self.assertEqual(shared["path"], regular["path"])
                self.assertEqual(shared["totals"], regular["totals"])
                self.assertEqual(
                    shared["route_weight"],
                    regular["route_weight"],
                )

        limits = apply_shelter_preference(get_limits("beginner"), True)
        baseline = calculate_dijkstra(
            NODES,
            EDGES,
            "A",
            "D",
            "distance",
            POINTS,
        )
        regular_custom = calculate_custom(
            NODES,
            EDGES,
            "A",
            "D",
            "distance",
            limits,
            baseline,
            POINTS,
        )
        shared_custom = calculate_custom(
            NODES,
            EDGES,
            "A",
            "D",
            "distance",
            limits,
            baseline,
            POINTS,
            context,
        )
        self.assertEqual(shared_custom["path"], regular_custom["path"])
        self.assertEqual(shared_custom["totals"], regular_custom["totals"])
        self.assertEqual(
            shared_custom["recommendation_status"],
            regular_custom["recommendation_status"],
        )


class AlgorithmContractTests(unittest.TestCase):
    def test_all_algorithms_return_standard_contract_and_metrics(self):
        baseline = calculate_dijkstra(
            NODES,
            EDGES,
            "A",
            "D",
            "distance",
            POINTS,
        )
        results = [
            baseline,
            calculate_astar(NODES, EDGES, "A", "D", "distance", POINTS),
            calculate_greedy(NODES, EDGES, "A", "D", "distance", POINTS),
            calculate_custom(
                NODES,
                EDGES,
                "A",
                "D",
                "distance",
                get_limits("beginner"),
                baseline,
                POINTS,
            ),
        ]

        for result in results:
            with self.subTest(algorithm=result["algorithm"]):
                self.assertIn("path", result)
                self.assertIn("totals", result)
                self.assertIn("metrics", result)
                self.assertIn("profile_evaluation", result)
                self.assertIn("warnings", result)

                for key in (
                    "distance_km",
                    "time_min",
                    "elevation_gain_m",
                    "elevation_loss_m",
                    "difficulty",
                    "average_difficulty",
                    "max_difficulty",
                    "max_slope_percent",
                    "average_slope_percent",
                    "shelters_count",
                ):
                    self.assertIn(key, result["totals"])

                metrics = result["metrics"]
                self.assertGreaterEqual(metrics["execution_time_ms"], 0)
                self.assertGreater(metrics["visited_nodes"], 0)
                self.assertGreaterEqual(metrics["analyzed_edges"], 0)
                self.assertGreater(metrics["queue_pushes"], 0)

    def test_classic_algorithms_have_empty_profile_fields(self):
        for algorithm in CLASSIC_ALGORITHMS:
            with self.subTest(algorithm=algorithm.__module__):
                result = algorithm(NODES, EDGES, "A", "D", "distance")
                self.assertEqual(result["profile_evaluation"], {})
                self.assertEqual(result["warnings"], [])

    def test_dijkstra_finds_expected_shortest_path(self):
        result = calculate_dijkstra(NODES, EDGES, "A", "D", "distance")
        self.assertEqual(result["path"], ["A", "B", "D"])
        self.assertAlmostEqual(result["route_weight"], 2.0)

    def test_astar_distance_cost_matches_dijkstra(self):
        dijkstra = calculate_dijkstra(NODES, EDGES, "A", "D", "distance")
        astar = calculate_astar(NODES, EDGES, "A", "D", "distance")
        self.assertAlmostEqual(astar["route_weight"], dijkstra["route_weight"])

    def test_all_algorithms_support_every_criterion(self):
        for criterion in ("time", "distance", "elevation", "difficulty"):
            baseline = calculate_dijkstra(NODES, EDGES, "A", "D", criterion)
            results = [
                baseline,
                calculate_astar(NODES, EDGES, "A", "D", criterion),
                calculate_greedy(NODES, EDGES, "A", "D", criterion),
                calculate_custom(
                    NODES,
                    EDGES,
                    "A",
                    "D",
                    criterion,
                    get_limits("intermediate"),
                    baseline,
                ),
            ]

            for result in results:
                with self.subTest(
                    criterion=criterion,
                    algorithm=result["algorithm"],
                ):
                    self.assertIsNotNone(result)
                    self.assertEqual(result["criterion"], criterion)
                    self.assertGreaterEqual(result["route_weight"], 0)

    def test_unknown_criterion_raises_clear_error(self):
        algorithms = (*CLASSIC_ALGORITHMS, calculate_custom)

        for algorithm in algorithms:
            with self.subTest(algorithm=algorithm.__module__):
                with self.assertRaisesRegex(ValueError, "Nieznane kryterium"):
                    algorithm(NODES, EDGES, "A", "D", "scenic")

    def test_dijkstra_does_not_count_stale_queue_entry_as_visited(self):
        nodes = [
            {"id": node_id, "lat": 49.0, "lng": 19.0, "elevation": 100}
            for node_id in ("S", "A", "B", "T")
        ]
        edges = [
            edge("S", "A", 10.0, 1, 0, 0),
            edge("S", "B", 1.0, 1, 0, 0),
            edge("B", "A", 1.0, 1, 0, 0),
            edge("A", "T", 20.0, 1, 0, 0),
        ]

        result = calculate_dijkstra(nodes, edges, "S", "T", "distance")

        self.assertEqual(result["path"], ["S", "B", "A", "T"])
        self.assertEqual(result["metrics"]["visited_nodes"], 4)


class CustomProfileTests(unittest.TestCase):
    def test_custom_without_profile_uses_intermediate_default(self):
        result = calculate_custom(NODES, EDGES, "A", "D", "distance")
        self.assertIsNotNone(result)
        self.assertEqual(
            result["profile_evaluation"]["experience_level"],
            "intermediate",
        )

    def test_all_required_profiles_work(self):
        for level in ("beginner", "intermediate", "expert"):
            with self.subTest(level=level):
                result = calculate_custom(
                    NODES,
                    EDGES,
                    "A",
                    "D",
                    "distance",
                    get_limits(level),
                    points=POINTS,
                )
                self.assertIsNotNone(result)
                evaluation = result["profile_evaluation"]
                self.assertEqual(evaluation["experience_level"], level)
                self.assertIn("profile_match_score", evaluation)
                self.assertGreaterEqual(evaluation["profile_match_score"], 0)
                self.assertLessEqual(evaluation["profile_match_score"], 100)

    def test_advanced_profile_recommends_even_the_hardest_connected_route(self):
        nodes = [
            {"id": "S", "lat": 49.0, "lng": 19.0, "elevation": 100},
            {"id": "T", "lat": 49.1, "lng": 19.1, "elevation": 3100},
        ]
        edges = [edge("S", "T", 3.0, 6, 3000, 100)]

        result = calculate_custom(
            nodes,
            edges,
            "S",
            "T",
            "difficulty",
            get_limits("advanced"),
        )

        self.assertEqual(result["path"], ["S", "T"])
        self.assertEqual(result["recommendation_status"], "recommended")
        self.assertTrue(result["profile_evaluation"]["within_safety_limits"])

    def test_beginner_and_expert_choose_different_routes(self):
        beginner = calculate_custom(
            NODES,
            EDGES,
            "A",
            "D",
            "distance",
            get_limits("beginner"),
            points=POINTS,
        )
        expert = calculate_custom(
            NODES,
            EDGES,
            "A",
            "D",
            "distance",
            get_limits("expert"),
            points=POINTS,
        )

        self.assertEqual(beginner["path"], ["A", "C", "D"])
        self.assertEqual(expert["path"], ["A", "B", "D"])
        self.assertEqual(beginner["totals"]["shelters_count"], 1)
        self.assertEqual(expert["totals"]["shelters_count"], 0)

    def test_safe_detour_wins_over_preferred_detour_limit(self):
        baseline = calculate_dijkstra(NODES, EDGES, "A", "D", "distance")
        limits = {
            **get_limits("beginner"),
            "max_detour_ratio": 1.1,
            "max_acceptable_detour_ratio": 1.3,
        }
        result = calculate_custom(
            NODES,
            EDGES,
            "A",
            "D",
            "distance",
            limits,
            baseline,
            POINTS,
        )
        evaluation = result["profile_evaluation"]

        self.assertEqual(result["path"], ["A", "C", "D"])
        self.assertFalse(evaluation["fallback_applied"])
        self.assertEqual(evaluation["recommendation_status"], "recommended")
        self.assertEqual(
            evaluation["selection_reason"],
            "safe_within_acceptable_detour",
        )
        self.assertAlmostEqual(evaluation["detour_ratio"], 1.2)
        self.assertTrue(evaluation["detour_preference_exceeded"])
        self.assertTrue(evaluation["within_safety_limits"])
        self.assertIn("limits", evaluation)
        self.assertIn("route", evaluation)
        self.assertIn("violations", evaluation)

    def test_too_hard_goal_returns_easiest_reasonable_custom_route(self):
        nodes = [
            {"id": node_id, "lat": 49.0, "lng": 19.0, "elevation": 100}
            for node_id in ("S", "M", "T")
        ]
        edges = [
            edge("S", "T", 1.0, 6, 0, 90),
            edge("S", "M", 1.2, 1, 0, 2),
            edge("M", "T", 1.2, 1, 0, 2),
        ]
        baseline = calculate_dijkstra(nodes, edges, "S", "T", "distance")
        limits = {
            **get_limits("beginner"),
            "max_detour_ratio": 1.2,
            "max_acceptable_detour_ratio": 1.5,
        }

        result = calculate_custom(
            nodes,
            edges,
            "S",
            "T",
            "distance",
            limits,
            baseline,
        )

        self.assertEqual(result["path"], ["S", "T"])
        self.assertEqual(result["recommendation_status"], "difficult_route")
        evaluation = result["profile_evaluation"]
        self.assertFalse(evaluation["fallback_applied"])
        self.assertFalse(evaluation["within_safety_limits"])
        self.assertEqual(
            evaluation["selection_reason"],
            "easiest_reasonable_route_to_requested_goal",
        )
        self.assertIn(
            "max_difficulty_exceeded",
            evaluation["safety_violations"],
        )

    def test_alternative_destination_prefers_better_profile_match(self):
        nodes = [
            {"id": "S", "lat": 49.0, "lng": 19.0, "elevation": 100},
            {"id": "N", "lat": 49.001, "lng": 19.001, "elevation": 200},
            {"id": "F", "lat": 49.01, "lng": 19.01, "elevation": 200},
        ]
        edges = [
            edge("S", "N", 0.2, 1, 100, 20),
            edge("S", "F", 0.3, 1, 100, 5),
        ]
        destinations = [
            {
                "point": {
                    "id": "near-peak",
                    "name": "Bliższy szczyt",
                    "type": "peak",
                    "lat": 49.001,
                    "lng": 19.001,
                },
                "routing_node_id": "N",
                "distance_from_requested_km": 0.2,
                "similarity_score": 0.2,
            },
            {
                "point": {
                    "id": "fitting-peak",
                    "name": "Łagodniejszy szczyt",
                    "type": "peak",
                    "lat": 49.01,
                    "lng": 19.01,
                },
                "routing_node_id": "F",
                "distance_from_requested_km": 1.0,
                "similarity_score": 1.0,
            },
        ]

        alternatives = find_profile_suitable_destination_alternatives(
            nodes,
            edges,
            "S",
            destinations,
            "distance",
            get_limits("beginner"),
        )

        self.assertEqual(alternatives[0]["id"], "fitting-peak")
        self.assertTrue(
            alternatives[0]["route"]["within_preferred_limits"]
        )
        self.assertFalse(
            alternatives[1]["route"]["within_preferred_limits"]
        )

    def test_alternative_can_be_easier_when_no_fully_suitable_peak_exists(self):
        nodes = [
            {"id": "S", "lat": 49.0, "lng": 19.0, "elevation": 100},
            {"id": "X", "lat": 49.01, "lng": 19.01, "elevation": 500},
        ]
        edges = [edge("S", "X", 0.8, 2, 400, 10)]
        destinations = [
            {
                "point": {
                    "id": "lower-peak",
                    "name": "Niższy szczyt",
                    "type": "peak",
                    "lat": 49.01,
                    "lng": 19.01,
                },
                "routing_node_id": "X",
                "distance_from_requested_km": 1.0,
                "similarity_score": 1.0,
                "same_destination_type": True,
            }
        ]

        alternatives = find_profile_suitable_destination_alternatives(
            nodes,
            edges,
            "S",
            destinations,
            "difficulty",
            get_limits("beginner"),
            reference_route_totals={
                "max_difficulty": 6,
                "max_slope_percent": 70,
                "elevation_gain_m": 800,
            },
            reference_profile_match_score=0,
        )

        self.assertEqual(alternatives[0]["id"], "lower-peak")
        self.assertFalse(alternatives[0]["route"]["within_safety_limits"])
        self.assertTrue(alternatives[0]["route"]["easier_than_requested"])
        self.assertEqual(
            alternatives[0]["route"]["recommendation_kind"],
            "easier_than_requested",
        )

    def test_shortest_route_wins_among_suitable_candidates(self):
        nodes = [
            {"id": node_id, "lat": 49.0, "lng": 19.0, "elevation": 100}
            for node_id in ("S", "A", "B", "T")
        ]
        edges = [
            edge("S", "T", 1.0, 6, 0, 90),
            edge("S", "A", 0.7, 1, 0, 14),
            edge("A", "T", 0.7, 1, 0, 14),
            edge("S", "B", 0.8, 1, 0, 2),
            edge("B", "T", 0.8, 1, 0, 2),
        ]
        baseline = calculate_dijkstra(nodes, edges, "S", "T", "distance")
        limits = {
            **get_limits("beginner"),
            "max_detour_ratio": 1.8,
            "max_acceptable_detour_ratio": 2.0,
        }

        result = calculate_custom(
            nodes,
            edges,
            "S",
            "T",
            "distance",
            limits,
            baseline,
        )

        self.assertEqual(result["path"], ["S", "A", "T"])
        self.assertEqual(result["recommendation_status"], "recommended")
        self.assertEqual(
            result["profile_evaluation"]["acceptable_candidate_count"],
            2,
        )

    def test_shelter_preference_can_choose_small_safe_detour(self):
        nodes = [
            {"id": "S", "lat": 49.0, "lng": 19.0, "elevation": 100},
            {"id": "A", "lat": 49.0, "lng": 19.01, "elevation": 100},
            {"id": "B", "lat": 49.005, "lng": 19.01, "elevation": 100},
            {"id": "T", "lat": 49.0, "lng": 19.02, "elevation": 100},
        ]
        edges = [
            edge("S", "A", 1.0, 1, 0, 0),
            edge("A", "T", 1.0, 1, 0, 0),
            edge("S", "B", 1.02, 1, 0, 0),
            edge("B", "T", 1.02, 1, 0, 0),
        ]
        points = [
            {
                "id": "hut/B",
                "name": "Schronisko przy wariancie B",
                "type": "alpine_hut",
                "lat": 49.005,
                "lng": 19.01,
                "nearest_routing_node_id": "B",
                "distance_to_trail_m": 5,
            }
        ]

        without_preference = calculate_custom(
            nodes,
            edges,
            "S",
            "T",
            "distance",
            get_limits("intermediate"),
            points=points,
        )
        with_preference = calculate_custom(
            nodes,
            edges,
            "S",
            "T",
            "distance",
            apply_shelter_preference(get_limits("intermediate"), True),
            points=points,
        )

        self.assertEqual(without_preference["path"], ["S", "A", "T"])
        self.assertEqual(with_preference["path"], ["S", "B", "T"])
        self.assertEqual(with_preference["totals"]["shelters_count"], 1)
        self.assertTrue(
            with_preference["profile_evaluation"][
                "shelter_preference_rerouted"
            ]
        )
        self.assertEqual(
            with_preference["profile_evaluation"]["selection_reason"],
            "safe_with_shelter_within_extra_limit",
        )


class TotalsAndSlopeTests(unittest.TestCase):
    def test_slope_is_calculated_for_simple_edge(self):
        self.assertAlmostEqual(calculate_slope_percent(100, 1.0), 10.0)
        self.assertIsNone(calculate_slope_percent(100, 0))

    def test_totals_derive_missing_slope_and_count_shelter_once(self):
        edges = [
            {
                **EDGES[2],
                "slope_percent": None,
                "elevation_change_m": 120,
                "elevation_gain_m": 120,
            },
            EDGES[3],
        ]
        totals = calculate_route_totals(
            ["A", "C", "D"],
            edges,
            nodes=NODES,
            points=POINTS,
        )

        self.assertEqual(totals["max_slope_percent"], 10.0)
        self.assertEqual(totals["shelters_count"], 1)


class RouteEndpointTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(map_bp)
        app.testing = True
        self.client = app.test_client()
        self.points = [
            {
                "id": "start-poi",
                "name": "Start",
                "type": "peak",
                "lat": NODES[0]["lat"],
                "lng": NODES[0]["lng"],
                "nearest_routing_node_id": "A",
            },
            {
                "id": "end-poi",
                "name": "Koniec",
                "type": "peak",
                "lat": NODES[-1]["lat"],
                "lng": NODES[-1]["lng"],
                "nearest_routing_node_id": "D",
            },
            *POINTS,
        ]
        self.routing_context = build_routing_context(
            NODES,
            EDGES,
            self.points,
        )

    def test_peak_alternative_candidates_include_related_saddle(self):
        start_point = {
            "id": "start-poi",
            "type": "viewpoint",
            "lat": 49.0,
            "lng": 19.0,
        }
        end_point = {
            "id": "hard-peak",
            "type": "peak",
            "lat": 49.01,
            "lng": 19.01,
            "elevation": 1800,
        }
        points = [
            start_point,
            end_point,
            {
                "id": "nearby-saddle",
                "name": "Łagodna przełęcz",
                "type": "saddle",
                "lat": 49.012,
                "lng": 19.012,
                "elevation": 1400,
                "nearest_routing_node_id": "X",
            },
            {
                "id": "nearby-water",
                "name": "Staw",
                "type": "water",
                "lat": 49.013,
                "lng": 19.013,
                "nearest_routing_node_id": "W",
            },
        ]
        routing_nodes = [
            {"id": "S", "lat": 49.0, "lng": 19.0},
            {"id": "D", "lat": 49.01, "lng": 19.01},
            {"id": "X", "lat": 49.012, "lng": 19.012},
            {"id": "W", "lat": 49.013, "lng": 19.013},
        ]

        candidates = build_alternative_destination_candidates(
            points,
            start_point,
            end_point,
            routing_nodes,
            "S",
            "D",
            {"S", "D", "X", "W"},
        )

        self.assertEqual(
            [candidate["point"]["id"] for candidate in candidates],
            ["nearby-saddle"],
        )
        self.assertFalse(candidates[0]["same_destination_type"])

    def test_route_endpoint_returns_all_algorithms_and_compatible_fields(self):
        with patch(
            "routes.map_routes.load_routing_context",
            return_value=self.routing_context,
        ):
            response = self.client.post(
                "/api/route",
                json={
                    "start": "start-poi",
                    "end": "end-poi",
                    "criterion": "distance",
                    "user_id": None,
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["routes"]), 4)
        self.assertEqual(
            data["preprocessing_metrics"]["nodes_count"],
            len(NODES),
        )
        self.assertEqual(
            data["preprocessing_metrics"]["edges_count"],
            len(EDGES),
        )
        self.assertIn(
            "routing_context_load_ms",
            data["preprocessing_metrics"],
        )
        self.assertEqual(
            {route["algorithm"] for route in data["routes"]},
            {"dijkstra", "astar", "greedy", "custom_hikeup"},
        )

        for route in data["routes"]:
            with self.subTest(algorithm=route["algorithm"]):
                self.assertIn("path", route)
                self.assertIn("positions", route)
                self.assertIn("totals", route)
                self.assertIn("metrics", route)
                self.assertIn("distance", route)
                self.assertIn("total_distance_km", route)

        custom = next(
            route
            for route in data["routes"]
            if route["algorithm"] == "custom_hikeup"
        )
        self.assertEqual(
            custom["recommendation_status"],
            "unpersonalized",
        )
        self.assertFalse(custom["personalization_enabled"])
        self.assertEqual(custom["path_ids"], ["A", "B", "D"])
        self.assertIsNone(
            custom["profile_evaluation"]["experience_level"]
        )

    def test_guest_is_unpersonalized_and_beginner_gets_easiest_route(self):
        nodes = [
            {"id": "S", "lat": 49.0, "lng": 19.0, "elevation": 100},
            {"id": "T", "lat": 49.01, "lng": 19.01, "elevation": 900},
        ]
        edges = [edge("S", "T", 1.0, 6, 800, 90)]
        points = [
            {
                "id": "start-poi",
                "name": "Start",
                "type": "viewpoint",
                "lat": 49.0,
                "lng": 19.0,
                "nearest_routing_node_id": "S",
            },
            {
                "id": "end-poi",
                "name": "Trudny cel",
                "type": "peak",
                "lat": 49.01,
                "lng": 19.01,
                "nearest_routing_node_id": "T",
            },
        ]
        routing_context = build_routing_context(nodes, edges, points)

        with patch(
            "routes.map_routes.load_routing_context",
            return_value=routing_context,
        ):
            guest_response = self.client.post(
                "/api/route",
                json={
                    "start": "start-poi",
                    "end": "end-poi",
                    "criterion": "distance",
                    "user_id": None,
                },
            )

        database_module = types.ModuleType("database")
        database_module.get_user_profile = lambda _user_id: {
            "user_id": 15,
            "age_years": 30,
            "experience_level": "beginner",
            "route_preference": "najkrótsza",
            "prefer_shelters": False,
        }
        with patch(
            "routes.map_routes.load_routing_context",
            return_value=routing_context,
        ), patch.dict("sys.modules", {"database": database_module}):
            profile_response = self.client.post(
                "/api/route",
                json={
                    "start": "start-poi",
                    "end": "end-poi",
                    "criterion": "distance",
                    "user_id": 15,
                },
            )

        self.assertEqual(guest_response.status_code, 200)
        guest_custom = next(
            route
            for route in guest_response.get_json()["routes"]
            if route["algorithm"] == "custom_hikeup"
        )
        self.assertEqual(guest_custom["path_ids"], ["S", "T"])
        self.assertEqual(
            guest_custom["recommendation_status"],
            "unpersonalized",
        )

        self.assertEqual(profile_response.status_code, 200)
        profile_custom = next(
            route
            for route in profile_response.get_json()["routes"]
            if route["algorithm"] == "custom_hikeup"
        )
        self.assertEqual(profile_custom["path_ids"], ["S", "T"])
        self.assertEqual(
            profile_custom["recommendation_status"],
            "difficult_route",
        )

    def test_route_endpoint_rejects_unknown_criterion(self):
        response = self.client.post(
            "/api/route",
            json={
                "start": "start-poi",
                "end": "end-poi",
                "criterion": "scenic",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Nieznane kryterium", response.get_json()["message"])

    def test_route_endpoint_passes_database_profile_only_to_custom(self):
        database_module = types.ModuleType("database")
        database_module.get_user_profile = lambda _user_id: {
            "user_id": 7,
            "age_years": 25,
            "experience_level": "beginner",
            "route_preference": "najszybsza",
            "prefer_shelters": True,
        }

        with patch(
            "routes.map_routes.load_routing_context",
            return_value=self.routing_context,
        ), patch.dict(
            "sys.modules",
            {"database": database_module},
        ):
            response = self.client.post(
                "/api/route",
                json={
                    "start": "start-poi",
                    "end": "end-poi",
                    "criterion": "distance",
                    "user_id": 7,
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["criterion"], "distance")
        routes = data["routes"]
        dijkstra = next(route for route in routes if route["algorithm"] == "dijkstra")
        custom = next(
            route for route in routes if route["algorithm"] == "custom_hikeup"
        )

        self.assertEqual(dijkstra["path_ids"], ["A", "B", "D"])
        self.assertEqual(custom["path_ids"], ["A", "C", "D"])
        self.assertEqual(
            custom["profile_evaluation"]["experience_level"],
            "beginner",
        )
        self.assertTrue(
            custom["profile_evaluation"]["shelter_preference_enabled"]
        )

    def test_endpoint_uses_saved_preference_when_criterion_is_missing(self):
        database_module = types.ModuleType("database")
        database_module.get_user_profile = lambda _user_id: {
            "user_id": 9,
            "age_years": 70,
            "experience_level": "expert",
            "route_preference": "najłatwiejsza",
            "prefer_shelters": False,
        }

        with patch(
            "routes.map_routes.load_routing_context",
            return_value=self.routing_context,
        ), patch.dict("sys.modules", {"database": database_module}):
            response = self.client.post(
                "/api/route",
                json={
                    "start": "start-poi",
                    "end": "end-poi",
                    "user_id": 9,
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["criterion"], "difficulty")
        self.assertTrue(
            all(route["criterion"] == "difficulty" for route in data["routes"])
        )
        custom = next(
            route
            for route in data["routes"]
            if route["algorithm"] == "custom_hikeup"
        )
        self.assertEqual(
            custom["profile_evaluation"]["experience_level"],
            "expert",
        )

    def test_endpoint_suggests_suitable_similar_destination(self):
        nodes = [
            {"id": "S", "lat": 49.0, "lng": 19.0, "elevation": 100},
            {"id": "D", "lat": 49.01, "lng": 19.01, "elevation": 900},
            {"id": "X", "lat": 49.012, "lng": 19.012, "elevation": 700},
        ]
        edges = [
            edge("S", "D", 1.0, 6, 800, 90),
            edge("S", "X", 1.2, 1, 100, 5),
        ]
        points = [
            {
                "id": "start-poi",
                "name": "Start",
                "type": "viewpoint",
                "lat": 49.0,
                "lng": 19.0,
                "nearest_routing_node_id": "S",
            },
            {
                "id": "end-poi",
                "name": "Trudny szczyt",
                "type": "peak",
                "lat": 49.01,
                "lng": 19.01,
                "elevation": 900,
                "nearest_routing_node_id": "D",
            },
            {
                "id": "alternative-poi",
                "name": "Łatwiejszy szczyt",
                "type": "peak",
                "lat": 49.012,
                "lng": 19.012,
                "elevation": 700,
                "nearest_routing_node_id": "X",
            },
        ]
        database_module = types.ModuleType("database")
        database_module.get_user_profile = lambda _user_id: {
            "user_id": 8,
            "age_years": 30,
            "experience_level": "beginner",
            "route_preference": "najkrótsza",
        }

        routing_context = build_routing_context(nodes, edges, points)
        with patch(
            "routes.map_routes.load_routing_context",
            return_value=routing_context,
        ), patch.dict("sys.modules", {"database": database_module}):
            response = self.client.post(
                "/api/route",
                json={
                    "start": "start-poi",
                    "end": "end-poi",
                    "criterion": "distance",
                    "user_id": 8,
                },
            )

        self.assertEqual(response.status_code, 200)
        custom = next(
            route
            for route in response.get_json()["routes"]
            if route["algorithm"] == "custom_hikeup"
        )
        self.assertEqual(custom["path_ids"], ["S", "D"])
        self.assertEqual(
            custom["recommendation_status"],
            "difficult_route",
        )
        self.assertEqual(
            custom["alternative_destinations"][0]["id"],
            "alternative-poi",
        )
        self.assertTrue(
            custom["alternative_destinations"][0]["route"]
            ["within_preferred_limits"]
        )


if __name__ == "__main__":
    unittest.main()
