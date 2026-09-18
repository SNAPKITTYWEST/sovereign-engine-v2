"""LatencyState and RoutingState (report SECTION 7's S_t = (G_t, T_t, J_t, L_t)).

Distinguishes SIMULATED latency (the deterministic sum of the L(e) values
declared in the model -- reproducible, no wall-clock involved) from
MEASURED runtime latency (an optional wall-clock benchmark of how long
this Python implementation took to run its own algorithm -- a statement
about this code's performance, not about the mathematical route cost it
computes). Conflating the two would be a category error: a route's L(R)
does not change because this particular Python process was slow.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from sparse_routing.model import SparseGraph
from .dijkstra import DijkstraResult, shortest_paths


@dataclass
class LatencyState:
    """L_t. threshold/objective are the configured routing policy;
    `last_result` is the most recent DijkstraResult (SIMULATED, i.e.
    computed deterministically from the model's declared L(e) values,
    not measured wall-clock time)."""

    threshold: float
    objective: str = "minimize"
    last_result: Optional[DijkstraResult] = None
    last_wall_clock_seconds: Optional[float] = None   # MEASURED, see compute() below

    def compute(self, graph: SparseGraph, source: str, benchmark: bool = False) -> DijkstraResult:
        """SIMULATED route latency is always computed (deterministic,
        reproducible). MEASURED wall-clock time is recorded only if
        `benchmark=True` is explicitly requested, and is stored in a
        clearly separate field so a caller can never mistake this
        process's execution time for a route's L(R)."""
        if benchmark:
            t0 = time.perf_counter()
            result = shortest_paths(graph, source)
            self.last_wall_clock_seconds = time.perf_counter() - t0
        else:
            result = shortest_paths(graph, source)
            self.last_wall_clock_seconds = None
        self.last_result = result
        return result

    def route_total_latency(self) -> float:
        """The 'critical path': the largest finite distance from the
        route root to any reachable node -- SIMULATED, i.e. the exact sum
        of declared L(e) values along that shortest path, not measured
        time."""
        if self.last_result is None:
            raise ValueError("compute() must be called before route_total_latency()")
        finite = {n: d for n, d in self.last_result.distance.items() if d != float("inf")}
        if not finite:
            return 0.0
        return max(finite.values())

    def bottleneck_node(self) -> Optional[str]:
        if self.last_result is None:
            raise ValueError("compute() must be called before bottleneck_node()")
        finite = {n: d for n, d in self.last_result.distance.items() if d != float("inf")}
        if not finite:
            return None
        # deterministic tie-break: smallest node id among nodes at max distance
        max_d = max(finite.values())
        candidates = sorted(n for n, d in finite.items() if d == max_d)
        return candidates[0]

    def exceeds_threshold(self) -> bool:
        return self.route_total_latency() > self.threshold


@dataclass
class RoutingState:
    """G_t's routing policy configuration: root, whether cycles are
    forbidden, and the sparsity bound. Bundled separately from
    SparseGraph itself because the graph is topology; this is policy."""

    root: str
    forbid_cycles: bool
    sparsity_max_ratio: float
    allow_expansion: bool

    def verify_policy(self, graph: SparseGraph) -> None:
        if self.root not in graph.nodes:
            raise ValueError(f"routing root {self.root!r} is not a declared node")
        if self.forbid_cycles:
            graph.check_no_forbidden_cycle(self.root)
        graph.check_sparsity_bound(self.sparsity_max_ratio)
