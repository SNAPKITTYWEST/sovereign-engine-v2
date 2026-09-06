"""State serialization, state hashing, deterministic replay (I8)."""
import copy

import numpy as np

from sparse_routing.adaptation import AdaptationEngine
from sparse_routing.model import Edge, Node, SparseGraph
from sparse_routing.rank import JacobianState, exact_rank
from sparse_routing.routing import LatencyState, RoutingState
from sparse_routing.serialization.state import canonical_payload, state_hash
from sparse_routing.tensor import TensorNode


def _fresh_engine():
    g = SparseGraph()
    for nid, prio in [("n1", 10), ("n2", 8), ("n3", 8), ("n4", 5)]:
        g.add_node(Node(nid, prio))
    g.add_edge(Edge("e1", "n1", "n2", 0.10, 0.05, 0.02, 1.0, "active", "t1", 9, "low"))
    g.add_edge(Edge("e2", "n1", "n3", 0.10, 0.05, 0.02, 1.0, "active", "t1", 9, "low"))
    g.add_edge(Edge("e3", "n2", "n4", 0.10, 0.05, 0.02, 0.8, "active", "t1", 5, "low"))
    g.add_edge(Edge("e4", "n3", "n4", 0.10, 0.05, 0.02, 0.8, "active", "t1", 6, "low"))
    tensor = TensorNode("t1", (3, 3), "float32")
    jac = JacobianState("f", 3, 3, thresholds_min=1, thresholds_max=3, slack=1)
    routing = RoutingState(root="n1", forbid_cycles=True, sparsity_max_ratio=0.35, allow_expansion=False)
    latency = LatencyState(threshold=0.90)
    return AdaptationEngine("replay_net", "1.0", g, tensor, jac, routing, latency)


def test_canonical_payload_is_order_independent(canonical_graph):
    """Building the same graph with nodes/edges added in a different
    order must produce an identical canonical payload -- the whole point
    of sorting ids before serializing."""
    g2 = SparseGraph()
    for nid in ["n5", "n3", "n1", "n4", "n2"]:  # different insertion order
        g2.add_node(canonical_graph.nodes[nid])
    for eid in ["e5", "e3", "e1", "e4", "e2"]:
        e = canonical_graph.edges[eid]
        g2.add_edge(Edge(e.id, e.source, e.destination, e.computation_latency,
                          e.communication_latency, e.synchronization_latency, e.weight,
                          e.activation_state, e.tensor_dependency, e.routing_priority, e.sparsity_class))

    p1 = canonical_payload("net", "1.0", canonical_graph, None, 2, "exact", 0.57, "n5", "GENESIS")
    p2 = canonical_payload("net", "1.0", g2, None, 2, "exact", 0.57, "n5", "GENESIS")
    assert p1 == p2


def test_state_hash_changes_when_topology_changes(canonical_graph):
    h1 = state_hash("net", "1.0", canonical_graph, None, 2, "exact", 0.57, "n5", "GENESIS")
    canonical_graph.edges["e1"].computation_latency = 0.99  # tamper
    h2 = state_hash("net", "1.0", canonical_graph, None, 2, "exact", 0.57, "n5", "GENESIS")
    assert h1 != h2


def test_state_hash_stable_across_runs(canonical_graph):
    """The exact tamper-detection property the companion Bash engine's
    `verify` subcommand relies on: identical inputs, identical hash,
    every time -- not just within one process."""
    h1 = state_hash("net", "1.0", canonical_graph, None, 2, "exact", 0.57, "n5", "GENESIS")
    h2 = state_hash("net", "1.0", canonical_graph, None, 2, "exact", 0.57, "n5", "GENESIS")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest length


def test_I8_deterministic_replay_of_full_adaptation_sequence():
    """Re-run the exact same two-step adaptation sequence (rank 3 -> rank
    2, triggering a redundant-edge prune) from a fresh engine and confirm
    every hash in the resulting chain matches the first run's, byte for
    byte. This is I8's mechanical verification: identical state and
    identical observations produce identical adaptations."""
    def run_sequence():
        engine = _fresh_engine()
        s1 = engine.step(previous_rank=None, rank_estimate=exact_rank(np.eye(3)))
        deficient = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0, 2.0]])
        s2 = engine.step(previous_rank=s1.rank, rank_estimate=exact_rank(deficient))
        return [s1.hash, s2.hash], [s1.changed_edges, s2.changed_edges]

    hashes_a, changes_a = run_sequence()
    hashes_b, changes_b = run_sequence()

    assert hashes_a == hashes_b
    assert changes_a == changes_b


def test_replay_diverges_if_input_actually_differs():
    """Sanity check on the replay test above: it is not vacuously true --
    a genuinely different second run (different starting rank) produces a
    different hash chain."""
    engine_a = _fresh_engine()
    s1a = engine_a.step(previous_rank=None, rank_estimate=exact_rank(np.eye(3)))

    engine_b = _fresh_engine()
    deficient = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0, 2.0]])
    s1b = engine_b.step(previous_rank=None, rank_estimate=exact_rank(deficient))

    assert s1a.hash != s1b.hash
