import numpy as np
import pytest

from sparse_routing.model import Edge, Node, SparseGraph
from sparse_routing.rank import JacobianState, exact_rank
from sparse_routing.routing import LatencyState, RoutingState
from sparse_routing.tensor import TensorNode


def build_diamond() -> SparseGraph:
    """n1 -> n2, n1 -> n3, n2 -> n4, n3 -> n4 (n4 has two active incoming
    edges, so one is structurally redundant)."""
    g = SparseGraph()
    for nid, prio in [("n1", 10), ("n2", 8), ("n3", 8), ("n4", 5)]:
        g.add_node(Node(nid, prio))
    g.add_edge(Edge("e1", "n1", "n2", 0.10, 0.05, 0.02, 1.0, "active", "t1", 9, "low"))
    g.add_edge(Edge("e2", "n1", "n3", 0.10, 0.05, 0.02, 1.0, "active", "t1", 9, "low"))
    g.add_edge(Edge("e3", "n2", "n4", 0.10, 0.05, 0.02, 0.8, "active", "t1", 5, "low"))
    g.add_edge(Edge("e4", "n3", "n4", 0.10, 0.05, 0.02, 0.8, "active", "t1", 6, "low"))
    return g


def build_canonical_five_node() -> SparseGraph:
    """Same 5-node topology as spec/network.xml, built directly from
    model objects (no XML parsing involved) -- used to cross-check the
    parser's output against a hand-built equivalent."""
    g = SparseGraph()
    for nid, prio in [("n1", 10), ("n2", 8), ("n3", 8), ("n4", 5), ("n5", 3)]:
        g.add_node(Node(nid, prio))
    g.add_edge(Edge("e1", "n1", "n2", 0.10, 0.05, 0.02, 1.0, "active", "t1", 9, "low"))
    g.add_edge(Edge("e2", "n1", "n3", 0.12, 0.04, 0.01, 1.0, "active", "t1", 9, "low"))
    g.add_edge(Edge("e3", "n2", "n4", 0.20, 0.05, 0.02, 0.8, "active", "t1.1", 5, "low"))
    g.add_edge(Edge("e4", "n3", "n4", 0.15, 0.03, 0.01, 0.8, "active", "t1.1", 6, "low"))
    g.add_edge(Edge("e5", "n4", "n5", 0.18, 0.02, 0.01, 1.0, "active", "t1", 4, "medium"))
    return g


@pytest.fixture
def diamond_graph() -> SparseGraph:
    return build_diamond()


@pytest.fixture
def canonical_graph() -> SparseGraph:
    return build_canonical_five_node()


@pytest.fixture
def rank_deficient_matrix() -> np.ndarray:
    return np.array([[1.0, 0.0, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0, 2.0]])


@pytest.fixture
def identity_matrix() -> np.ndarray:
    return np.eye(3)
