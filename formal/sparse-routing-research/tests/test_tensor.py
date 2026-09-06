"""Tensor recursion, recursion limits -- I4, I5."""
import pytest

from sparse_routing.tensor import TensorNode, TensorKind


def test_scalar_vector_matrix_higher_order_kinds():
    assert TensorNode("s", (), "float32").kind() == TensorKind.SCALAR
    assert TensorNode("v", (3,), "float32").kind() == TensorKind.VECTOR
    assert TensorNode("m", (3, 3), "float32").kind() == TensorKind.MATRIX
    assert TensorNode("h", (2, 3, 4), "float32").kind() == TensorKind.HIGHER_ORDER
    assert TensorNode("sp", (3, 3), "float32", sparse=True).kind() == TensorKind.SPARSE


def test_nested_tensor_depth():
    leaf = TensorNode("t1.1", (3,), "float32")
    root = TensorNode("t1", (3, 3), "float32", children=[leaf])
    assert root.depth() == 1
    assert root.kind() == TensorKind.NESTED


def test_I4_invalid_dimension_rejected():
    with pytest.raises(ValueError, match="I4 violation"):
        TensorNode("bad", (3, 0), "float32")
    with pytest.raises(ValueError, match="I4 violation"):
        TensorNode("bad2", (-1,), "float32")


def test_I5_recursion_bound_respected():
    leaf = TensorNode("t1.1", (3,), "float32")
    root = TensorNode("t1", (3, 3), "float32", children=[leaf])
    root.check_recursion_bound(1)  # depth 1 <= max_depth 1, should not raise
    root.check_recursion_bound(4)  # generous bound, should not raise


def test_I5_recursion_overflow_detected():
    """Three levels deep, but max_depth allows only one."""
    leaf3 = TensorNode("t1.1.1", (1,), "float32")
    leaf2 = TensorNode("t1.1", (3,), "float32", children=[leaf3])
    root = TensorNode("t1", (3, 3), "float32", children=[leaf2])
    assert root.depth() == 2
    with pytest.raises(ValueError, match="I5 violation"):
        root.check_recursion_bound(1)


def test_total_size_includes_children():
    leaf = TensorNode("t1.1", (3,), "float32")
    root = TensorNode("t1", (3, 3), "float32", children=[leaf])
    assert root.size() == 9
    assert root.total_size() == 9 + 3


def test_find_by_id():
    leaf = TensorNode("t1.1", (3,), "float32")
    root = TensorNode("t1", (3, 3), "float32", children=[leaf])
    assert root.find("t1.1") is leaf
    assert root.find("nonexistent") is None
