import unittest
import types
from unittest.mock import patch

from flask import Flask

from algorithms.astar import calculate_route as calculate_astar
from algorithms.common import calculate_route_totals
from algorithms.custom import calculate_route as calculate_custom
from algorithms.dijkstra import calculate_route as calculate_dijkstra
from algorithms.greedy import calculate_route as calculate_greedy
from algorithms.weights import calculate_slope_percent
from models.experience_config import (
    apply_shelter_preference,
    criterion_from_route_preference,
    get_limits,
    infer_experience_level,
)
from routes.map_routes import map_bp


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
    def test_declared_experience_has_priority_over_senior_age(self):
        self.assertEqual(infer_experience_level(70, "expert"), "expert")
        self.assertEqual(infer_experience_level(70, "advanced"), "advanced")

    def test_senior_is_default_only_without_declared_experience(self):
        self.assertEqual(infer_experience_level(70, ""), "senior")
        self.assertEqual(infer_experience_level(40, ""), "intermediate")

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

    def test_no_suitable_route_keeps_dijkstra_as_comparison_only(self):
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

        self.assertEqual(result["path"], [])
        self.assertEqual(result["recommendation_status"], "no_suitable_route")
        evaluation = result["profile_evaluation"]
        self.assertFalse(evaluation["fallback_applied"])
        self.assertEqual(
            evaluation["comparison_route"]["path"],
            ["S", "T"],
        )
        self.assertIn(
            "max_difficulty_exceeded",
            evaluation["comparison_route"]["safety_violations"],
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

    def test_route_endpoint_returns_all_algorithms_and_compatible_fields(self):
        with patch("routes.map_routes.load_points", return_value=self.points), patch(
            "routes.map_routes.load_full_map",
            return_value={"nodes": NODES, "edges": EDGES},
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
            custom["profile_evaluation"]["experience_level"],
            "intermediate",
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

        with patch("routes.map_routes.load_points", return_value=self.points), patch(
            "routes.map_routes.load_full_map",
            return_value={"nodes": NODES, "edges": EDGES},
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

        with patch("routes.map_routes.load_points", return_value=self.points), patch(
            "routes.map_routes.load_full_map",
            return_value={"nodes": NODES, "edges": EDGES},
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

        with patch("routes.map_routes.load_points", return_value=points), patch(
            "routes.map_routes.load_full_map",
            return_value={"nodes": nodes, "edges": edges},
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
        self.assertEqual(custom["path_ids"], [])
        self.assertEqual(
            custom["recommendation_status"],
            "no_suitable_route",
        )
        self.assertEqual(
            custom["alternative_destinations"][0]["id"],
            "alternative-poi",
        )


if __name__ == "__main__":
    unittest.main()
