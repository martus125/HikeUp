"""Współdzielone, niemodyfikowane indeksy grafu routingu.

Kontekst jest budowany raz na proces backendu i przekazywany wszystkim
algorytmom. Nie przechowuje wyników tras ani danych profilu użytkownika.
"""

from dataclasses import dataclass
from functools import lru_cache

from algorithms.common import (
    build_edge_map,
    build_graph,
    get_shelter_routing_node_ids,
)
from services.map_service import load_full_map, load_points


@dataclass(frozen=True, slots=True)
class RoutingContext:
    """Indeksy mapy współdzielone przez wyszukiwania w jednym procesie."""

    nodes: list
    edges: list
    points: list
    graph: dict
    nodes_by_id: dict
    edges_by_nodes: dict
    node_ids: frozenset
    points_by_id: dict
    shelter_node_ids: frozenset


def build_routing_context(nodes, edges, points=None):
    """Buduje kontekst z przekazanych kolekcji bez kopiowania ich zawartości."""
    points = points or []
    nodes_by_id = {
        node.get("id"): node
        for node in nodes
        if isinstance(node, dict) and node.get("id") is not None
    }
    points_by_id = {
        point.get("id"): point
        for point in points
        if isinstance(point, dict) and point.get("id") is not None
    }

    return RoutingContext(
        nodes=nodes,
        edges=edges,
        points=points,
        graph=build_graph(edges),
        nodes_by_id=nodes_by_id,
        edges_by_nodes=build_edge_map(edges),
        node_ids=frozenset(nodes_by_id),
        points_by_id=points_by_id,
        shelter_node_ids=frozenset(get_shelter_routing_node_ids(points)),
    )


@lru_cache(maxsize=1)
def load_routing_context():
    """Ładuje i indeksuje mapę tylko raz na proces uruchomionego backendu."""
    full_map = load_full_map()
    return build_routing_context(
        full_map["nodes"],
        full_map["edges"],
        load_points(),
    )


def routing_context_is_cached():
    """Informuje, czy bieżący proces ma już przygotowany kontekst."""
    return load_routing_context.cache_info().currsize > 0
