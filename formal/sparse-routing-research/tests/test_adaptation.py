"""Adaptation, failed adaptation, I9 atomic commit."""
import numpy as np
import pytest

from sparse_routing.adaptation import AdaptationEngine
from sparse_routing.rank import JacobianState, exact_rank
from sparse_routing.routing import LatencyState, RoutingState
from sparse_routing.tensor import TensorNode


def make_engine(diamond_graph, threshold=0.90, allow_expansion=False):
    tensor = TensorNode("t1", (3, 3), "float32")
    jac = JacobianState("f", 3, 3, thresholds_min=1, thresholds_max=3, slack=1)
    routing = RoutingState(root="n1", forbid_cycles=True, sparsity_max_ratio=0.35, allow_expansion=allow_expansion)
    latency = LatencyState(threshold=threshold)
    return AdaptationEngine("test_net", "1.0", diamond_graph, tensor, jac, routing, latency)


def test_successful_adaptation_prunes_redundant_edge(diamond_graph):
    """rank decreases 3 -> 2: rule r2 fires, redundant edge e3 (lower
    routing_priority than e4) is pruned deterministically."""
    engine = make_engine(diamond_graph)
    s1 = engine.step(previous_rank=None, rank_estimate=exact_rank(np.eye(3)))
    assert s1.rank == 3
    assert s1.adaptation_applied is False

    deficient = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0, 2.0]])
    s2 = engine.step(previous_rank=s1.rank, rank_estimate=exact_rank(deficient))
    assert s2.rank == 2
    assert s2.adaptation_applied is True
    assert s2.changed_edges == ["e3"]
    assert "rank_decreases" in s2.triggering_conditions
    assert engine.graph.edges["e3"].activation_state == "pruned"
    assert engine.graph.edges["e4"].activation_state == "active"
    assert len(engine.history) == 2
    assert engine.rejected_count == 0


def test_rejected_adaptation_never_fabricates_topology(diamond_graph):
    """rank increases with allow_expansion=False: this engine never
    invents new edges, so the expansion is rejected, not applied."""
    engine = make_engine(diamond_graph, allow_expansion=False)
    deficient = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0, 2.0]])
    s1 = engine.step(previous_rank=None, rank_estimate=exact_rank(deficient))
    assert s1.rank == 2

    s2 = engine.step(previous_rank=s1.rank, rank_estimate=exact_rank(np.eye(3)))
    assert s2.rank == 3
    assert s2.adaptation_applied is False
    assert "rank_increases" in s2.triggering_conditions
    assert "sparsity_exceeds_maximum" in s2.triggering_conditions
    assert s2.changed_edges == []
    # no edge was actually created or removed
    assert all(e.is_active for e in engine.graph.edges.values())


def test_I9_atomic_commit_preserves_previous_state_on_infeasible_latency(diamond_graph):
    """Latency far below any achievable route: the proposal is
    infeasible, so commit_state() must NOT replace the previous valid
    state -- the previously committed state (or, if none exists yet, an
    explicit unverified marker) is what's returned, and the real graph is
    left untouched."""
    engine = make_engine(diamond_graph, threshold=0.001)  # impossibly low
    before_edges = {eid: e.activation_state for eid, e in engine.graph.edges.items()}

    s1 = engine.step(previous_rank=None, rank_estimate=exact_rank(np.eye(3)))
    assert s1.verification_passed is False
    assert len(engine.history) == 0  # nothing was ever committed
    assert engine.rejected_count == 1

    after_edges = {eid: e.activation_state for eid, e in engine.graph.edges.items()}
    assert before_edges == after_edges  # graph genuinely untouched


def test_I9_second_infeasible_step_still_preserves_last_good_state(diamond_graph):
    """Once a good state exists, a later infeasible step must return that
    same good state unchanged, not a corrupted or partial one."""
    engine = make_engine(diamond_graph, threshold=0.90)
    s1 = engine.step(previous_rank=None, rank_estimate=exact_rank(np.eye(3)))
    assert engine.rejected_count == 0
    assert len(engine.history) == 1

    # now make latency threshold impossible for the NEXT step by mutating
    # the engine's own LatencyState threshold (simulating an observation
    # that latency now vastly exceeds a much stricter configured bound)
    engine.latency_state.threshold = 0.0001
    s2 = engine.step(previous_rank=s1.rank, rank_estimate=exact_rank(np.eye(3)))
    assert s2 is s1  # returned the previous valid state, unchanged
    assert len(engine.history) == 1  # nothing new committed
    assert engine.rejected_count == 1


def test_tensor_dimension_change_is_traceable(diamond_graph):
    """I8: every adaptation must be traceable to an explicit rule/condition."""
    engine = make_engine(diamond_graph)
    s1 = engine.step(previous_rank=None, rank_estimate=exact_rank(np.eye(3)))
    engine.tensor_root = TensorNode("t1", (4, 4), "float32")  # shape changed
    s2 = engine.step(previous_rank=s1.rank, rank_estimate=exact_rank(np.eye(3)))
    assert "tensor_dimension_changes" in s2.triggering_conditions
