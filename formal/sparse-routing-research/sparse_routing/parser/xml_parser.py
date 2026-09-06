"""XML parser: LEXER -> TOKENS -> AST -> VALIDATED MODEL -> ROUTING GRAPH
(report SECTION 10), reading the canonical XML defined in
`spec/network.xsd` / `spec/network.xml`.

Real XML parsing is done by `xml.etree.ElementTree` (the standard
library's tree parser) -- this module does not use regex to parse the
document's structure; regex (via `lexer.py`) is used only to validate
individual already-segmented attribute VALUES, exactly as report
SECTION 10 requires.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from sparse_routing.model import Edge, Node, SparseGraph
from sparse_routing.rank import JacobianState, exact_rank, numerical_rank, structural_rank
from sparse_routing.routing import RoutingState
from sparse_routing.tensor import TensorNode

from .ast_nodes import (
    AdaptationRuleAST,
    EdgeAST,
    JacobianAST,
    NetworkAST,
    NodeAST,
    RoutingAST,
    TensorAST,
)
from .lexer import LexError, lex_value


def _lex_bool(value: str) -> bool:
    lex_value("BOOLEAN", value)
    return value == "true"


def _parse_shape(text: str) -> Tuple[int, ...]:
    dims = []
    for part in text.split(","):
        part = part.strip()
        lex_value("DIMENSION", part)
        dims.append(int(part))
    return tuple(dims)


def parse_matrix_text(text: str, rows: int, cols: int) -> np.ndarray:
    """Parses a semicolon-separated-rows, comma-separated-values matrix
    literal (the same textual convention the companion Bash
    implementation's canonical XML uses), validating declared shape
    against actual content rather than trusting the `rows`/`cols`
    attributes blindly."""
    cleaned = "".join(text.split())  # strip all whitespace, matching the Bash tr -d '[:space:]'
    row_strs = [r for r in cleaned.rstrip(";").split(";") if r != ""]
    if len(row_strs) != rows:
        raise ValueError(f"matrix declares rows={rows} but has {len(row_strs)} row(s)")
    data = []
    for r in row_strs:
        vals = [float(v) for v in r.split(",") if v != ""]
        if len(vals) != cols:
            raise ValueError(f"matrix declares cols={cols} but a row has {len(vals)} value(s)")
        data.append(vals)
    return np.array(data, dtype=float)


def _parse_tensor_element(elem: ET.Element) -> TensorAST:
    tid = lex_value("TENSOR_IDENTIFIER", elem.attrib["id"])
    shape = _parse_shape(elem.attrib["shape"])
    dtype = elem.attrib["dtype"]
    rank_hint = int(elem.attrib["rank_hint"]) if "rank_hint" in elem.attrib else None
    sparse = elem.attrib.get("sparse", "false") == "true"
    children: List[TensorAST] = []
    recursion_elem = elem.find("recursion")
    if recursion_elem is not None:
        for child_elem in recursion_elem.findall("tensor"):
            children.append(_parse_tensor_element(child_elem))
    return TensorAST(id=tid, shape=shape, dtype=dtype, rank_hint=rank_hint, sparse=sparse, children=children)


def parse_network_xml_to_ast(path: str) -> NetworkAST:
    """LEXER -> TOKENS -> AST stage. Every attribute value that has a
    defined token class (lexer.TOKEN_PATTERNS) is validated against it
    here; a value that fails raises LexError, so no field with no
    defined semantic meaning silently passes through (report SECTION 11's
    "Do not allow XML fields that have no defined semantic meaning")."""
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "network":
        raise ValueError(f"expected root element <network>, found <{root.tag}>")

    name = lex_value("NODE_IDENTIFIER", root.attrib["name"])
    version = root.attrib["version"]

    execution = root.find("execution")
    max_recursion_depth = int(lex_value("RECURSION_LIMIT", execution.find("max_recursion_depth").text.strip()))
    rank_backend = execution.find("rank_backend").text.strip()
    if rank_backend not in ("computed", "structural"):
        raise ValueError(f"unsupported rank_backend: {rank_backend!r}")

    nodes = []
    for node_elem in root.find("nodes").findall("node"):
        nodes.append(NodeAST(
            id=lex_value("NODE_IDENTIFIER", node_elem.attrib["id"]),
            priority=int(node_elem.attrib["priority"]),
        ))

    edges = []
    for edge_elem in root.find("edges").findall("edge"):
        a = edge_elem.attrib
        edges.append(EdgeAST(
            id=lex_value("EDGE_IDENTIFIER", a["id"]),
            source=lex_value("NODE_IDENTIFIER", a["source"]),
            destination=lex_value("NODE_IDENTIFIER", a["destination"]),
            computation_latency=float(lex_value("SIGNED_LATENCY_VALUE", a["computation_latency"])),
            communication_latency=float(lex_value("SIGNED_LATENCY_VALUE", a["communication_latency"])),
            synchronization_latency=float(lex_value("SIGNED_LATENCY_VALUE", a["synchronization_latency"])),
            weight=float(a["weight"]),
            activation_state=a["activation_state"],
            tensor_dependency=lex_value("TENSOR_IDENTIFIER", a["tensor_dependency"]),
            routing_priority=int(a["routing_priority"]),
            sparsity_class=a["sparsity_class"],
        ))

    tensors = [_parse_tensor_element(t) for t in root.find("tensors").findall("tensor")]

    routing_elem = root.find("routing")
    hierarchy = routing_elem.find("hierarchy")
    latency_elem = routing_elem.find("latency")
    sparsity_elem = routing_elem.find("sparsity")
    routing = RoutingAST(
        root=lex_value("NODE_IDENTIFIER", hierarchy.attrib["root"]),
        forbid_cycles=_lex_bool(hierarchy.attrib["forbid_cycles"]),
        latency_threshold=float(lex_value("LATENCY_VALUE", latency_elem.attrib["threshold"])),
        sparsity_max_ratio=float(sparsity_elem.attrib["max_ratio"]),
        allow_expansion=_lex_bool(sparsity_elem.attrib["allow_expansion"]),
    )

    jacobian_elem = root.find("jacobian")
    function_elem = jacobian_elem.find("function")
    matrix_elem = jacobian_elem.find("matrix")
    rank_elem = jacobian_elem.find("rank")
    jacobian = JacobianAST(
        function_name=lex_value("NODE_IDENTIFIER", function_elem.attrib["name"]),
        input_dim=int(function_elem.attrib["input_dim"]),
        output_dim=int(function_elem.attrib["output_dim"]),
        matrix_rows=int(matrix_elem.attrib["rows"]) if matrix_elem is not None else None,
        matrix_cols=int(matrix_elem.attrib["cols"]) if matrix_elem is not None else None,
        matrix_text=matrix_elem.text if matrix_elem is not None else None,
        thresholds_min=int(lex_value("RANK_THRESHOLD", rank_elem.attrib["thresholds_min"])),
        thresholds_max=int(lex_value("RANK_THRESHOLD", rank_elem.attrib["thresholds_max"])),
        slack=int(lex_value("RANK_THRESHOLD", rank_elem.attrib["slack"])),
    )

    adaptation_rules = []
    rules_elem = root.find("adaptation").find("rules")
    if rules_elem is not None:
        for rule_elem in rules_elem.findall("rule"):
            a = rule_elem.attrib
            adaptation_rules.append(AdaptationRuleAST(
                id=lex_value("NODE_IDENTIFIER", a["id"]),
                condition=lex_value("ROUTING_RULE_CONDITION", a["condition"]),
                action=lex_value("ROUTING_RULE_ACTION", a["action"]),
            ))

    return NetworkAST(
        name=name, version=version, max_recursion_depth=max_recursion_depth,
        rank_backend=rank_backend, nodes=nodes, edges=edges, tensors=tensors,
        routing=routing, jacobian=jacobian, adaptation_rules=adaptation_rules,
    )


def _build_tensor_node(ast: TensorAST) -> TensorNode:
    return TensorNode(
        id=ast.id, shape=ast.shape, dtype=ast.dtype,
        children=[_build_tensor_node(c) for c in ast.children],
        rank_hint=ast.rank_hint, sparse=ast.sparse,
    )


@dataclass
class ParsedModel:
    """The result of the full pipeline: AST -> VALIDATED MODEL -> ROUTING
    GRAPH. Every field here is a real object from
    sparse_routing.model/tensor/rank/routing, ready to hand to an
    AdaptationEngine -- not a second parallel representation of the AST."""

    network_name: str
    network_version: str
    max_recursion_depth: int
    graph: SparseGraph
    tensor_root: Optional[TensorNode]
    jacobian_state: JacobianState
    routing_state: RoutingState
    adaptation_rules: List[AdaptationRuleAST]


def build_model(ast: NetworkAST) -> ParsedModel:
    """AST -> VALIDATED MODEL -> ROUTING GRAPH. Cross-referential checks
    that a single element's lexical validity can't catch (duplicate ids,
    an edge referencing an undeclared node) are enforced here, by the
    real model objects' own constructors (SparseGraph.add_node/add_edge,
    which raise I1/I2 violations directly)."""
    graph = SparseGraph()
    for n in ast.nodes:
        graph.add_node(Node(n.id, n.priority))
    for e in ast.edges:
        graph.add_edge(Edge(
            e.id, e.source, e.destination,
            e.computation_latency, e.communication_latency, e.synchronization_latency,
            e.weight, e.activation_state, e.tensor_dependency, e.routing_priority, e.sparsity_class,
        ))

    tensor_root = _build_tensor_node(ast.tensors[0]) if ast.tensors else None
    if tensor_root is not None:
        tensor_root.check_recursion_bound(ast.max_recursion_depth)

    jac = ast.jacobian
    jacobian_state = JacobianState(
        function_name=jac.function_name, input_dim=jac.input_dim, output_dim=jac.output_dim,
        thresholds_min=jac.thresholds_min, thresholds_max=jac.thresholds_max, slack=jac.slack,
    )
    jacobian_state.check_threshold_consistency()

    if jac.matrix_text is not None:
        matrix = parse_matrix_text(jac.matrix_text, jac.matrix_rows, jac.matrix_cols)
        jacobian_state.matrix = matrix
        if ast.rank_backend == "computed":
            jacobian_state.rank_estimate = exact_rank(matrix)
        else:
            active_deps = {e.tensor_dependency for e in ast.edges if e.activation_state == "active"}
            cap = min(jac.input_dim, jac.output_dim)
            jacobian_state.rank_estimate = structural_rank(len(active_deps), cap)
    else:
        active_deps = {e.tensor_dependency for e in ast.edges if e.activation_state == "active"}
        cap = min(jac.input_dim, jac.output_dim)
        jacobian_state.rank_estimate = structural_rank(len(active_deps), cap)

    jacobian_state.check_rank_validity()
    jacobian_state.check_within_configured_thresholds()

    routing_state = RoutingState(
        root=ast.routing.root, forbid_cycles=ast.routing.forbid_cycles,
        sparsity_max_ratio=ast.routing.sparsity_max_ratio, allow_expansion=ast.routing.allow_expansion,
    )
    routing_state.verify_policy(graph)

    return ParsedModel(
        network_name=ast.name, network_version=ast.version, max_recursion_depth=ast.max_recursion_depth,
        graph=graph, tensor_root=tensor_root, jacobian_state=jacobian_state,
        routing_state=routing_state, adaptation_rules=ast.adaptation_rules,
    )


def parse_network_xml(path: str) -> ParsedModel:
    """The single entry point: LEXER -> TOKENS -> AST -> VALIDATED MODEL
    -> ROUTING GRAPH, from a file path to a ready-to-use ParsedModel."""
    ast = parse_network_xml_to_ast(path)
    return build_model(ast)
