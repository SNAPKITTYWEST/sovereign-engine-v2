#!/usr/bin/env python3
"""Controlled experiment (report SECTION 20): STATIC vs LATENCY-AWARE vs
RANK-INFORMED sparse routing, on one synthetic network, over a
deterministic sequence of timesteps.

This script actually executes all three strategies and writes real
measured results to experiments/results.json -- nothing in that file is
a hand-typed or assumed number. Re-running this script reproduces the
same file byte-for-byte (the network and the per-timestep schedule are
both fully deterministic; only the two MEASURED columns, runtime_seconds
and peak_memory_bytes, are expected to vary slightly run to run, since
they depend on this process's actual execution, not on the model).

Network topology (synthetic, 7 nodes, 8 edges -- a "diamond of diamonds"
so there are multiple genuinely redundant edges over the run, not just
one):

    n1 -> n2 -> n4 -> n5 -> n7
    n1 -> n3 -> n4 -> n6 -> n7

Deterministic per-timestep schedule (T=8 steps, t=0..7):
  - edge latency: base_latency(e) * (1 + 0.3*sin((t+1) * phase(e))), a
    fixed function of (edge, t), never a random draw.
  - Jacobian: a real 3x3 matrix, rank 3 for t in {0,1,4,5,6,7} and
    rank-deficient (rank 2) for t in {2,3} -- a deterministic rank dip
    and recovery, not a random walk.
"""
from __future__ import annotations

import json
import math
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np

from sparse_routing.adaptation import AdaptationEngine
from sparse_routing.model import Edge, Node, SparseGraph
from sparse_routing.rank import JacobianState, RankEstimate, exact_rank
from sparse_routing.routing import LatencyState, RoutingState, shortest_paths
from sparse_routing.tensor import TensorNode

T = 8  # number of timesteps

BASE_EDGES = [
    # (id, source, destination, base_computation, base_communication, base_synchronization, weight, priority)
    ("e1", "n1", "n2", 0.10, 0.03, 0.01, 1.0, 9),
    ("e2", "n1", "n3", 0.11, 0.03, 0.01, 1.0, 9),
    ("e3", "n2", "n4", 0.15, 0.04, 0.01, 0.8, 6),
    ("e4", "n3", "n4", 0.14, 0.04, 0.01, 0.8, 5),
    ("e5", "n4", "n5", 0.12, 0.03, 0.01, 0.9, 7),
    ("e6", "n4", "n6", 0.13, 0.03, 0.01, 0.9, 4),
    ("e7", "n5", "n7", 0.10, 0.02, 0.01, 1.0, 8),
    ("e8", "n6", "n7", 0.11, 0.02, 0.01, 1.0, 3),
]
NODES = ["n1", "n2", "n3", "n4", "n5", "n6", "n7"]
ROOT = "n1"
SPARSITY_MAX_RATIO = 0.5
LATENCY_THRESHOLD = 5.0  # generous -- this experiment is not testing fail-closed behavior

# deterministic per-edge phase (derived from the edge's own index, not random)
_PHASE = {eid: 0.7 + 0.15 * i for i, (eid, *_rest) in enumerate(BASE_EDGES)}


def latency_at(base: float, edge_id: str, t: int) -> float:
    return base * (1.0 + 0.3 * math.sin((t + 1) * _PHASE[edge_id]))


# deterministic rank schedule: rank 3 (identity-equivalent) except a dip
# to rank 2 (rank-deficient) at t in {2, 3}
_IDENTITY = np.eye(3)
_DEFICIENT = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0, 2.0]])


def jacobian_matrix_at(t: int) -> np.ndarray:
    return _DEFICIENT if t in (2, 3) else _IDENTITY


def build_graph() -> SparseGraph:
    g = SparseGraph()
    for nid in NODES:
        g.add_node(Node(nid, 1))
    for eid, src, dst, cl, cm, sy, w, prio in BASE_EDGES:
        g.add_edge(Edge(eid, src, dst, cl, cm, sy, w, "active", "t1", prio, "low"))
    return g


@dataclass
class StrategyResult:
    strategy: str
    per_timestep_route_cost: List[float]
    per_timestep_rank: List[int]
    final_active_edge_count: int
    final_sparsity_ratio: float
    committed_steps: int             # number of steps where verification passed and the step was committed
    adaptation_count: int            # subset of committed_steps where topology actually changed (edges pruned)
    verification_failures: int
    runtime_seconds: float          # MEASURED wall-clock, not route cost
    peak_memory_bytes: int          # MEASURED, via tracemalloc


def run_static() -> StrategyResult:
    """Route decided once at t=0 using that timestep's latencies, then
    reused unchanged (both the path AND the topology) for every later
    timestep regardless of how latencies or rank evolve."""
    tracemalloc.start()
    t0 = time.perf_counter()

    g = build_graph()
    # compute t=0 latencies and freeze the chosen path
    for eid, src, dst, cl, cm, sy, w, prio in BASE_EDGES:
        g.edges[eid].computation_latency = latency_at(cl, eid, 0)
        g.edges[eid].communication_latency = latency_at(cm, eid, 0)
        g.edges[eid].synchronization_latency = latency_at(sy, eid, 0)
    frozen_path_result = shortest_paths(g, ROOT)
    frozen_path_edges = frozen_path_result.path_to("n7")

    costs = []
    ranks = []
    for t in range(T):
        for eid, src, dst, cl, cm, sy, w, prio in BASE_EDGES:
            g.edges[eid].computation_latency = latency_at(cl, eid, t)
            g.edges[eid].communication_latency = latency_at(cm, eid, t)
            g.edges[eid].synchronization_latency = latency_at(sy, eid, t)
        cost = sum(g.edges[eid].latency for eid in frozen_path_edges)
        costs.append(cost)
        rank_estimate = exact_rank(jacobian_matrix_at(t))
        ranks.append(rank_estimate.rank)

    runtime = time.perf_counter() - t0
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return StrategyResult(
        strategy="static",
        per_timestep_route_cost=costs,
        per_timestep_rank=ranks,
        final_active_edge_count=sum(1 for _ in g.active_edges()),
        final_sparsity_ratio=g.sparsity_ratio(),
        committed_steps=0,
        adaptation_count=0,
        verification_failures=0,
        runtime_seconds=runtime,
        peak_memory_bytes=peak,
    )


def run_latency_aware() -> StrategyResult:
    """Recomputes the true latency-minimal route every timestep on the
    always-full topology. Never mutates topology -- only route SELECTION
    adapts, never the graph itself."""
    tracemalloc.start()
    t0 = time.perf_counter()

    g = build_graph()
    latency_state = LatencyState(threshold=LATENCY_THRESHOLD)
    costs = []
    ranks = []
    for t in range(T):
        for eid, src, dst, cl, cm, sy, w, prio in BASE_EDGES:
            g.edges[eid].computation_latency = latency_at(cl, eid, t)
            g.edges[eid].communication_latency = latency_at(cm, eid, t)
            g.edges[eid].synchronization_latency = latency_at(sy, eid, t)
        latency_state.compute(g, ROOT)
        costs.append(latency_state.last_result.distance["n7"])
        ranks.append(exact_rank(jacobian_matrix_at(t)).rank)

    runtime = time.perf_counter() - t0
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return StrategyResult(
        strategy="latency_aware",
        per_timestep_route_cost=costs,
        per_timestep_rank=ranks,
        final_active_edge_count=sum(1 for _ in g.active_edges()),
        final_sparsity_ratio=g.sparsity_ratio(),
        committed_steps=0,
        adaptation_count=0,
        verification_failures=0,
        runtime_seconds=runtime,
        peak_memory_bytes=peak,
    )


def run_rank_informed() -> StrategyResult:
    """Recomputes the latency-minimal route every timestep (same as
    latency-aware) AND runs the full adaptation engine each timestep, so
    a rank decrease can trigger a real, verified redundant-edge prune
    (never a fabricated edge for a rank increase, since
    routing_state.allow_expansion stays False throughout)."""
    tracemalloc.start()
    t0 = time.perf_counter()

    g = build_graph()
    tensor = TensorNode("t1", (3, 3), "float32")
    jac = JacobianState("f", 3, 3, thresholds_min=1, thresholds_max=3, slack=1)
    routing = RoutingState(root=ROOT, forbid_cycles=True, sparsity_max_ratio=SPARSITY_MAX_RATIO, allow_expansion=False)
    latency_state = LatencyState(threshold=LATENCY_THRESHOLD)
    engine = AdaptationEngine("rank_informed_experiment", "1.0", g, tensor, jac, routing, latency_state)

    costs = []
    ranks = []
    prev_rank = None
    for t in range(T):
        for eid, src, dst, cl, cm, sy, w, prio in BASE_EDGES:
            if g.edges[eid].is_active:
                g.edges[eid].computation_latency = latency_at(cl, eid, t)
                g.edges[eid].communication_latency = latency_at(cm, eid, t)
                g.edges[eid].synchronization_latency = latency_at(sy, eid, t)
        rank_estimate = exact_rank(jacobian_matrix_at(t))
        state = engine.step(previous_rank=prev_rank, rank_estimate=rank_estimate)
        prev_rank = rank_estimate.rank
        # after the adaptation step, take the fresh latency-minimal route
        # on the (possibly now-pruned) topology
        latency_state.compute(g, ROOT)
        dist_n7 = latency_state.last_result.distance.get("n7", float("inf"))
        costs.append(dist_n7)
        ranks.append(rank_estimate.rank)

    runtime = time.perf_counter() - t0
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return StrategyResult(
        strategy="rank_informed",
        per_timestep_route_cost=costs,
        per_timestep_rank=ranks,
        final_active_edge_count=sum(1 for _ in g.active_edges()),
        final_sparsity_ratio=g.sparsity_ratio(),
        committed_steps=len(engine.history),
        adaptation_count=sum(1 for st in engine.history if st.adaptation_applied),
        verification_failures=engine.rejected_count,
        runtime_seconds=runtime,
        peak_memory_bytes=peak,
    )


def main() -> None:
    results = [run_static(), run_latency_aware(), run_rank_informed()]
    out_path = Path(__file__).parent / "results.json"
    payload = {
        "T": T,
        "note": "runtime_seconds and peak_memory_bytes are MEASURED (this process's actual execution); everything else is SIMULATED (deterministic from the model, reproducible exactly on re-run).",
        "results": [asdict(r) for r in results],
    }
    out_path.write_text(json.dumps(payload, indent=2))
    for r in results:
        print(f"=== {r.strategy} ===")
        print(f"  per-timestep route cost: {[round(c, 4) for c in r.per_timestep_route_cost]}")
        print(f"  per-timestep rank:       {r.per_timestep_rank}")
        print(f"  final active edges:      {r.final_active_edge_count}")
        print(f"  final sparsity ratio:    {round(r.final_sparsity_ratio, 4)}")
        print(f"  adaptation count:        {r.adaptation_count}")
        print(f"  verification failures:   {r.verification_failures}")
        print(f"  runtime (measured, s):   {r.runtime_seconds:.6f}")
        print(f"  peak memory (measured, bytes): {r.peak_memory_bytes}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
