"""AST node types (report SECTION 10's "TOKENS -> AST" stage).

These dataclasses mirror the canonical XML's element structure directly
(one class per element type) and hold LEXICALLY-validated but not yet
SEMANTICALLY-validated data -- e.g. a NodeAST's `id` is guaranteed to
match the NODE_IDENTIFIER token class by the time it exists, but nothing
here yet checks that two nodes don't share an id, or that an edge's
`source`/`destination` refer to a NodeAST that actually exists in the
same NetworkAST. Those cross-referential, semantic checks happen one
stage later, when `xml_parser.build_model()` turns a NetworkAST into the
real `sparse_routing.model.SparseGraph` / `sparse_routing.tensor.TensorNode`
/ `sparse_routing.rank.JacobianState` objects (the "VALIDATED MODEL" and
"ROUTING GRAPH" stages of SECTION 10's pipeline).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class NodeAST:
    id: str
    priority: int


@dataclass
class EdgeAST:
    id: str
    source: str
    destination: str
    computation_latency: float
    communication_latency: float
    synchronization_latency: float
    weight: float
    activation_state: str
    tensor_dependency: str
    routing_priority: int
    sparsity_class: str


@dataclass
class TensorAST:
    id: str
    shape: Tuple[int, ...]
    dtype: str
    rank_hint: Optional[int] = None
    sparse: bool = False
    children: List["TensorAST"] = field(default_factory=list)


@dataclass
class RoutingAST:
    root: str
    forbid_cycles: bool
    latency_threshold: float
    sparsity_max_ratio: float
    allow_expansion: bool


@dataclass
class JacobianAST:
    function_name: str
    input_dim: int
    output_dim: int
    matrix_rows: Optional[int]
    matrix_cols: Optional[int]
    matrix_text: Optional[str]
    thresholds_min: int
    thresholds_max: int
    slack: int


@dataclass
class AdaptationRuleAST:
    id: str
    condition: str
    action: str


@dataclass
class NetworkAST:
    name: str
    version: str
    max_recursion_depth: int
    rank_backend: str
    nodes: List[NodeAST]
    edges: List[EdgeAST]
    tensors: List[TensorAST]
    routing: RoutingAST
    jacobian: JacobianAST
    adaptation_rules: List[AdaptationRuleAST]
