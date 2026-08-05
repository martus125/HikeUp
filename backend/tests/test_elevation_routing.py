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
from routes.map_routes import build_single_route_response
from scripts.fill_edge_elevation_data import update_edges


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


class ElevationDataScriptTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
