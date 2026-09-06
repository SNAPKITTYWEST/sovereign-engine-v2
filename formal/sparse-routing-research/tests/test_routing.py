"""Shortest-path routing, latency calculation."""
import pytest

from sparse_routing.routing import LatencyState, RoutingState, shortest_paths


def test_shortest_path_matches_hand_computed_value(canonical_graph):
    """The companion Bash reference implementation computed
    route_total_latency=0.57 and bottleneck_node=n5 for this exact
    topology -- this is checked here as a cross-implementation agreement,
    not merely an internal consistency check."""
    ls = LatencyState(threshold=0.90)
    ls.compute(canonical_graph, "n1")
    assert ls.route_total_latency() == pytest.approx(0.57)
    assert ls.bottleneck_node() == "n5"


def test_deterministic_tie_break_prefers_higher_routing_priority():
    """Two equal-cost, equal-hop paths into the same node: the one whose
    last edge has the higher routing_priority wins, deterministically."""
    from sparse_routing.model import Edge, Node, SparseGraph

    g = SparseGraph()
    for nid in ("n1", "n2", "n3", "n4"):
        g.add_node(Node(nid, 1))
    g.add_edge(Edge("e1", "n1", "n2", 0.1, 0.0, 0.0, 1.0, "active", "t1", 1, "low"))
    g.add_edge(Edge("e2", "n1", "n3", 0.1, 0.0, 0.0, 1.0, "active", "t1", 1, "low"))
    # equal total latency reaching n4 via either e3 or e4; e4 has higher priority
    g.add_edge(Edge("e3", "n2", "n4", 0.1, 0.0, 0.0, 1.0, "active", "t1", 5, "low"))
    g.add_edge(Edge("e4", "n3", "n4", 0.1, 0.0, 0.0, 1.0, "active", "t1", 6, "low"))

    result = shortest_paths(g, "n1")
    assert result.last_edge_priority["n4"] == 6
    assert result.path_to("n4") == ["e2", "e4"]


def test_routing_policy_verification(canonical_graph):
    rs = RoutingState(root="n1", forbid_cycles=True, sparsity_max_ratio=0.35, allow_expansion=False)
    rs.verify_policy(canonical_graph)  # should not raise


def test_routing_policy_rejects_unknown_root(canonical_graph):
    rs = RoutingState(root="n99", forbid_cycles=True, sparsity_max_ratio=0.35, allow_expansion=False)
    with pytest.raises(ValueError, match="not a declared node"):
        rs.verify_policy(canonical_graph)


def test_latency_threshold_check(canonical_graph):
    ls = LatencyState(threshold=0.01)
    ls.compute(canonical_graph, "n1")
    assert ls.exceeds_threshold() is True

    ls2 = LatencyState(threshold=0.90)
    ls2.compute(canonical_graph, "n1")
    assert ls2.exceeds_threshold() is False


def test_measured_wall_clock_is_separate_from_simulated_latency(canonical_graph):
    """SECTION 15: measured runtime latency must never be conflated with
    simulated route cost."""
    ls = LatencyState(threshold=0.90)
    ls.compute(canonical_graph, "n1", benchmark=True)
    assert ls.last_wall_clock_seconds is not None
    assert ls.last_wall_clock_seconds != ls.route_total_latency()
    assert ls.route_total_latency() == pytest.approx(0.57)  # unaffected by wall-clock timing
