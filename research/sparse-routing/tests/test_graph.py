"""Graph creation, sparse validation, I1/I2/I3/I6."""
import numpy as np
import pytest

from sparse_routing.model import Edge, Node, SparseGraph


def test_graph_creation(canonical_graph):
    assert set(canonical_graph.nodes.keys()) == {"n1", "n2", "n3", "n4", "n5"}
    assert set(canonical_graph.edges.keys()) == {"e1", "e2", "e3", "e4", "e5"}


def test_duplicate_node_rejected():
    g = SparseGraph()
    g.add_node(Node("n1", 1))
    with pytest.raises(ValueError):
        g.add_node(Node("n1", 2))


def test_duplicate_edge_rejected():
    g = SparseGraph()
    g.add_node(Node("n1", 1))
    g.add_node(Node("n2", 1))
    g.add_edge(Edge("e1", "n1", "n2", 0.1, 0.1, 0.1, 1.0, "active", "t1", 1, "low"))
    with pytest.raises(ValueError):
        g.add_edge(Edge("e1", "n1", "n2", 0.1, 0.1, 0.1, 1.0, "active", "t1", 1, "low"))


def test_I1_edge_references_unknown_node():
    """I1: every edge references an existing node."""
    g = SparseGraph()
    g.add_node(Node("n1", 1))
    with pytest.raises(ValueError, match="I1 violation"):
        g.add_edge(Edge("e1", "n1", "n9", 0.1, 0.1, 0.1, 1.0, "active", "t1", 1, "low"))


def test_I2_malformed_activation_state_rejected():
    """I2: no malformed edge exists."""
    with pytest.raises(ValueError, match="I2 violation"):
        Edge("e1", "n1", "n2", 0.1, 0.1, 0.1, 1.0, "not_a_real_state", "t1", 1, "low")


def test_I2_nan_latency_rejected():
    with pytest.raises(ValueError, match="I2 violation"):
        Edge("e1", "n1", "n2", float("nan"), 0.1, 0.1, 1.0, "active", "t1", 1, "low")


def test_I3_negative_latency_rejected(canonical_graph):
    """I3: L(e) >= 0."""
    canonical_graph.edges["e1"].computation_latency = -0.5
    with pytest.raises(ValueError, match="I3 violation"):
        canonical_graph.check_no_negative_latency()


def test_I6_sparsity_bound(canonical_graph):
    """I6: rho(A) <= rho_max. Canonical graph has ratio 5/25 = 0.2."""
    assert canonical_graph.sparsity_ratio() == pytest.approx(0.2)
    canonical_graph.check_sparsity_bound(0.35)  # should not raise
    with pytest.raises(ValueError, match="I6 violation"):
        canonical_graph.check_sparsity_bound(0.1)


def test_sparse_adjacency_is_actually_sparse(canonical_graph):
    """Never a dense O(|V|^2) allocation -- to_sparse_adjacency returns a
    real scipy.sparse matrix, and its stored nnz equals |E|."""
    import scipy.sparse as sp
    A = canonical_graph.to_sparse_adjacency()
    assert sp.issparse(A)
    assert A.nnz == 5
    assert A.shape == (5, 5)


def test_forbidden_cycle_detected():
    g = SparseGraph()
    for nid in ("n1", "n2", "n3"):
        g.add_node(Node(nid, 1))
    g.add_edge(Edge("e1", "n1", "n2", 0.1, 0.0, 0.0, 1.0, "active", "t1", 1, "low"))
    g.add_edge(Edge("e2", "n2", "n3", 0.1, 0.0, 0.0, 1.0, "active", "t1", 1, "low"))
    g.add_edge(Edge("e3", "n3", "n1", 0.1, 0.0, 0.0, 1.0, "active", "t1", 1, "low"))
    with pytest.raises(ValueError, match="forbidden cycle"):
        g.check_no_forbidden_cycle("n1")


def test_no_cycle_in_dag(canonical_graph):
    canonical_graph.check_no_forbidden_cycle("n1")  # should not raise
