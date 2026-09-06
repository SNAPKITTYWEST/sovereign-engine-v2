"""TensorNode — the recursive tensor model (report SECTION 8).

    T = Tensor(shape, dtype, children, metadata)
    d(T) = 0                                   if T.children is empty
    d(T) = 1 + max(d(c) for c in T.children)   otherwise
    Constraint (I5): d(T) <= d_max

FORMALLY DEFINED: d(T) and the recursion bound above.
ENGINEERING CHOICE: "kind" (scalar/vector/matrix/higher_order/nested/sparse)
is a classification convenience derived from shape/children, not a
separate mathematical object.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Tuple


class TensorKind(str, Enum):
    SCALAR = "scalar"
    VECTOR = "vector"
    MATRIX = "matrix"
    HIGHER_ORDER = "higher_order"
    NESTED = "nested"          # has children, regardless of its own shape
    SPARSE = "sparse"          # sparse=True, independent of shape rank


@dataclass
class TensorNode:
    """A single node of the recursive tensor tree.

    shape: () for a scalar, (n,) for a vector, (m, n) for a matrix,
           (d1, ..., dk) for a higher-order tensor. Every di must be a
           positive integer (I4).
    children: nested TensorNode instances (the "recursion" of SECTION 8).
              An empty list means this node is a leaf.
    """

    id: str
    shape: Tuple[int, ...]
    dtype: str
    children: List["TensorNode"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    sparse: bool = False
    rank_hint: int | None = None

    def __post_init__(self) -> None:
        self.validate_shape()

    # -- I4: tensor validity ----------------------------------------------

    def validate_shape(self) -> None:
        """I4: all tensor dimensions are positive and valid.

        A scalar (shape == ()) is valid by definition (rank-0 tensor, no
        dimensions to check). Every declared dimension for rank >= 1 must
        be a positive integer -- 0 and negative values are rejected here,
        not deferred to a consumer that might forget to check.
        """
        for dim in self.shape:
            if not isinstance(dim, int) or isinstance(dim, bool) or dim <= 0:
                raise ValueError(f"I4 violation: tensor {self.id!r} has invalid dimension {dim!r} in shape {self.shape!r}")

    # -- I5: recursion bound ------------------------------------------------

    def depth(self) -> int:
        """d(T). FORMALLY DEFINED, computed recursively, O(size of subtree)."""
        if not self.children:
            return 0
        return 1 + max(child.depth() for child in self.children)

    def check_recursion_bound(self, max_depth: int) -> None:
        """I5: d(T) <= d_max, checked for this node and, recursively, for
        every descendant (a deep descendant violating the bound must be
        caught even if it is not this node's own .depth() that reports it
        first -- walking every node, not just checking the root's depth,
        catches a violation at its actual point of origin)."""
        self._check_recursion_bound_at(0, max_depth)

    def _check_recursion_bound_at(self, current_depth: int, max_depth: int) -> None:
        if current_depth > max_depth:
            raise ValueError(
                f"I5 violation: tensor {self.id!r} nesting reaches depth {current_depth} "
                f"which exceeds d_max={max_depth}"
            )
        for child in self.children:
            child._check_recursion_bound_at(current_depth + 1, max_depth)

    # -- classification -----------------------------------------------------

    def kind(self) -> TensorKind:
        if self.sparse:
            return TensorKind.SPARSE
        if self.children:
            return TensorKind.NESTED
        rank = len(self.shape)
        if rank == 0:
            return TensorKind.SCALAR
        if rank == 1:
            return TensorKind.VECTOR
        if rank == 2:
            return TensorKind.MATRIX
        return TensorKind.HIGHER_ORDER

    def size(self) -> int:
        """Number of scalar elements this node's own shape describes
        (does NOT include children -- see total_size for that)."""
        result = 1
        for dim in self.shape:
            result *= dim
        return result if self.shape else 1

    def total_size(self) -> int:
        """This node's element count plus every descendant's, recursively.
        A pure engineering convenience (used by the experiment's
        "computational overhead" metric), not a formal quantity."""
        return self.size() + sum(child.total_size() for child in self.children)

    def flatten(self) -> List["TensorNode"]:
        """Depth-first list of this node and every descendant. O(size of subtree)."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def find(self, tensor_id: str) -> "TensorNode | None":
        for node in self.flatten():
            if node.id == tensor_id:
                return node
        return None
