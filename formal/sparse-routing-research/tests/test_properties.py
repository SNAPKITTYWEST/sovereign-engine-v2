"""Property-based tests (report SECTION 19: "Include property-based tests
where appropriate")."""
import numpy as np
from hypothesis import given, settings, strategies as st

from sparse_routing.model import Edge, Node, SparseGraph
from sparse_routing.rank import exact_rank, numerical_rank
from sparse_routing.tensor import TensorNode


@given(st.integers(min_value=1, max_value=6), st.integers(min_value=0, max_value=10))
@settings(max_examples=50)
def test_property_sparsity_ratio_always_in_valid_range(n_nodes, extra_edges):
    """For any graph built with 1..6 nodes and up to a fully-connected
    edge set, rho(A) = |E|/|V|^2 must always land in [0, 1]."""
    g = SparseGraph()
    node_ids = [f"n{i}" for i in range(n_nodes)]
    for nid in node_ids:
        g.add_node(Node(nid, 1))
    max_possible = n_nodes * n_nodes
    n_edges = min(extra_edges, max_possible)
    count = 0
    for i in range(n_nodes):
        for j in range(n_nodes):
            if count >= n_edges:
                break
            g.add_edge(Edge(f"e{count}", node_ids[i], node_ids[j], 0.1, 0.0, 0.0, 1.0, "active", "t1", 1, "low"))
            count += 1
        if count >= n_edges:
            break
    ratio = g.sparsity_ratio()
    assert 0.0 <= ratio <= 1.0


@given(st.lists(st.integers(min_value=1, max_value=20), min_size=0, max_size=5))
@settings(max_examples=50)
def test_property_tensor_shape_validation_accepts_only_positive_dims(dims):
    """Any shape made entirely of positive integers must be accepted;
    this is the positive side of the I4 property (the negative side --
    that a shape containing a non-positive dimension is always rejected
    -- is checked directly in tests/test_tensor.py)."""
    t = TensorNode("t", tuple(dims), "float32")
    assert t.shape == tuple(dims)  # constructed without raising


@given(st.integers(min_value=1, max_value=5))
@settings(max_examples=20)
def test_property_identity_matrix_rank_equals_its_dimension(n):
    """For any n, the n x n identity matrix has exact rank n -- a basic
    linear-algebra property this implementation's exact_rank must never
    violate."""
    I = np.eye(n)
    result = exact_rank(I)
    assert result.rank == n


@given(st.integers(min_value=2, max_value=5))
@settings(max_examples=20)
def test_property_rank_deficient_construction_always_below_full_rank(n):
    """Constructing an n x n matrix whose last row is the sum of all
    others is always rank-deficient (rank <= n - 1), for any n -- a
    structural property of the construction, checked generically rather
    than only for the one 3x3 example used elsewhere."""
    rng = np.random.default_rng(seed=n)
    M = rng.integers(0, 5, size=(n - 1, n)).astype(float)
    last_row = M.sum(axis=0)
    full = np.vstack([M, last_row])
    result = exact_rank(full)
    assert result.rank <= n - 1


@given(st.integers(min_value=0, max_value=8), st.integers(min_value=0, max_value=8))
@settings(max_examples=50)
def test_property_recursion_bound_check_matches_actual_depth(depth, max_depth):
    """Build a tensor chain of exactly `depth` nested levels; the bound
    check must raise iff depth > max_depth, for any (depth, max_depth)
    pair -- not just the couple of fixed examples in test_tensor.py."""
    node = TensorNode(f"t{depth}", (1,), "float32")
    for level in range(depth - 1, -1, -1):
        node = TensorNode(f"t{level}", (1,), "float32", children=[node])
    if depth > max_depth:
        try:
            node.check_recursion_bound(max_depth)
            assert False, "expected I5 violation"
        except ValueError:
            pass
    else:
        node.check_recursion_bound(max_depth)  # must not raise
