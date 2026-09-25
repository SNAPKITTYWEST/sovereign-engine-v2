"""Deterministic single-source shortest-path routing (report SECTION 5).

    L(R) = sum(L(e) for e in R),   R* = argmin_R L(R)  s.t. R in valid_routes(G)

FORMALLY DEFINED: L(R) and the R* optimization problem above.
MECHANICALLY CHECKED: Dijkstra's algorithm finds the true argmin over all
routes from a fixed source, GIVEN that every L(e) >= 0 (checked separately
as I3, in sparse_routing.model.graph.SparseGraph.check_no_negative_latency
-- Dijkstra's optimality guarantee does not hold for negative weights, and
this module does not re-derive that proof; it depends on I3 holding).
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional

from sparse_routing.model import SparseGraph


@dataclass
class DijkstraResult:
    """Per-node result of a single-source shortest-path computation.

    Complexity: O((|V| + |E|) log |V|) time (binary heap), O(|V|) space
    for the distance/hop/predecessor maps plus O(|V|) for the heap in the
    worst case -- never O(|V|^2), which matters once |V| is large and
    the graph stays sparse.
    """

    distance: Dict[str, float]
    hops: Dict[str, int]
    last_edge_priority: Dict[str, int]
    predecessor_edge: Dict[str, Optional[str]]

    def path_to(self, target: str) -> List[str]:
        """Reconstruct the edge-id path from source to target, O(hops)."""
        path: List[str] = []
        node = target
        while self.predecessor_edge.get(node) is not None:
            eid = self.predecessor_edge[node]
            path.append(eid)
            node = self._edge_source[eid]  # type: ignore[attr-defined]
        path.reverse()
        return path


def shortest_paths(graph: SparseGraph, source: str) -> DijkstraResult:
    """Deterministic Dijkstra from `source` over active edges only.

    Tie-break order (report SECTION 5's "never random routing", applied
    identically to the Bash reference implementation this project's
    companion engine used): when two candidate distances are equal,
    prefer (1) fewer hops, (2) higher last-edge routing_priority,
    (3) lexicographically smaller destination node id. This is enforced
    by the heap key itself -- (distance, hops, -routing_priority, node_id)
    -- so tie-breaking is intrinsic to the ordering, not a secondary pass.
    """
    nodes = graph.node_ids_sorted()
    INF = float("inf")
    distance: Dict[str, float] = {n: INF for n in nodes}
    hops: Dict[str, int] = {n: 0 for n in nodes}
    last_edge_priority: Dict[str, int] = {n: 0 for n in nodes}
    predecessor_edge: Dict[str, Optional[str]] = {n: None for n in nodes}
    edge_source: Dict[str, str] = {}

    distance[source] = 0.0
    visited = set()
    # heap entries: (distance, hops, -routing_priority, node_id)
    heap: List[tuple] = [(0.0, 0, 0, source)]

    while heap:
        d, h, neg_prio, u = heapq.heappop(heap)
        if u in visited:
            continue
        if d > distance[u]:
            continue
        visited.add(u)
        for e in graph.out_edges(u, active_only=True):
            v = e.destination
            if v in visited:
                continue
            cand_d = d + e.latency
            cand_h = h + 1
            cand_key = (cand_d, cand_h, -e.routing_priority, v)
            cur_key = (distance[v], hops[v], -last_edge_priority[v], v)
            if cand_key < cur_key:
                distance[v] = cand_d
                hops[v] = cand_h
                last_edge_priority[v] = e.routing_priority
                predecessor_edge[v] = e.id
                edge_source[e.id] = u
                heapq.heappush(heap, (cand_d, cand_h, -e.routing_priority, v))

    result = DijkstraResult(distance, hops, last_edge_priority, predecessor_edge)
    result._edge_source = edge_source  # type: ignore[attr-defined]
    return result
