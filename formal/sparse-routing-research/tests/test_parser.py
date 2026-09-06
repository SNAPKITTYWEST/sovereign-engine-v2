"""Malformed XML, malformed AST, and the real lexer/AST/model pipeline."""
import tempfile
import textwrap

import pytest

from sparse_routing.parser import (
    AdaptationRuleAST,
    EdgeAST,
    JacobianAST,
    LexError,
    NetworkAST,
    NodeAST,
    RoutingAST,
    TensorAST,
    lex_value,
    parse_network_xml,
)
from sparse_routing.parser.xml_parser import build_model


def test_canonical_xml_parses_to_expected_model():
    pm = parse_network_xml("spec/network.xml")
    assert pm.network_name == "demo_network"
    assert set(pm.graph.nodes.keys()) == {"n1", "n2", "n3", "n4", "n5"}
    assert pm.jacobian_state.rank_estimate.rank == 2
    assert pm.jacobian_state.rank_estimate.source == "exact"
    assert pm.tensor_root.find("t1.1") is not None


def test_lexer_rejects_invalid_node_identifier():
    with pytest.raises(LexError):
        lex_value("NODE_IDENTIFIER", "1invalid")  # can't start with a digit


def test_lexer_rejects_invalid_dimension():
    with pytest.raises(LexError):
        lex_value("DIMENSION", "0")  # dimensions must be positive
    with pytest.raises(LexError):
        lex_value("DIMENSION", "-3")


def test_lexer_accepts_signed_latency_but_not_unsigned_token():
    # SIGNED_LATENCY_VALUE deliberately accepts a leading '-' (see
    # lexer.py's note) so a negative value can reach the I3 invariant
    # check with a specific diagnostic, rather than being rejected here.
    assert lex_value("SIGNED_LATENCY_VALUE", "-0.10") == "-0.10"
    with pytest.raises(LexError):
        lex_value("LATENCY_VALUE", "-0.10")  # the strict, unsigned token class


def test_malformed_xml_not_well_formed_is_rejected():
    """An unclosed tag: real XML parsing (xml.etree.ElementTree) must
    reject this before any lexing or model-building happens."""
    bad_xml = "<network name='x' version='1.0'><nodes><node id='n1'"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(bad_xml)
        path = f.name
    with pytest.raises(Exception):  # xml.etree.ElementTree.ParseError
        parse_network_xml(path)


def test_malformed_xml_invalid_token_is_rejected():
    """Well-formed XML, but a node id that fails the NODE_IDENTIFIER
    lexical token class (starts with a digit)."""
    bad_xml = textwrap.dedent("""\
        <?xml version="1.0"?>
        <network name="bad_net" version="1.0">
          <execution><max_recursion_depth>4</max_recursion_depth><rank_backend>structural</rank_backend></execution>
          <nodes><node id="9bad" priority="1"/></nodes>
          <edges></edges>
          <tensors><tensor id="t1" shape="1" dtype="float32"/></tensors>
          <routing>
            <hierarchy root="9bad" forbid_cycles="true"/>
            <latency threshold="1.0"/>
            <sparsity max_ratio="1.0" allow_expansion="false"/>
          </routing>
          <jacobian>
            <function name="f" input_dim="1" output_dim="1"/>
            <rank thresholds_min="0" thresholds_max="1" slack="0"/>
          </jacobian>
          <adaptation><rules/></adaptation>
          <verification><invariants/></verification>
        </network>
    """)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(bad_xml)
        path = f.name
    with pytest.raises(LexError):
        parse_network_xml(path)


def test_malformed_ast_edge_references_unknown_node_is_rejected():
    """A hand-built AST (bypassing XML entirely) with an edge referencing
    a node that was never declared -- build_model() must catch this via
    I1, exactly as it would if the same AST had come from XML."""
    ast = NetworkAST(
        name="bad_model", version="1.0", max_recursion_depth=4, rank_backend="structural",
        nodes=[NodeAST("n1", 1)],
        edges=[EdgeAST("e1", "n1", "n9", 0.1, 0.1, 0.1, 1.0, "active", "t1", 1, "low")],
        tensors=[TensorAST("t1", (1,), "float32")],
        routing=RoutingAST(root="n1", forbid_cycles=True, latency_threshold=1.0, sparsity_max_ratio=1.0, allow_expansion=False),
        jacobian=JacobianAST("f", 1, 1, None, None, None, 0, 1, 0),
        adaptation_rules=[],
    )
    with pytest.raises(ValueError, match="I1 violation"):
        build_model(ast)


def test_malformed_ast_impossible_rank_thresholds_rejected():
    ast = NetworkAST(
        name="bad_model", version="1.0", max_recursion_depth=4, rank_backend="structural",
        nodes=[NodeAST("n1", 1)],
        edges=[],
        tensors=[TensorAST("t1", (1,), "float32")],
        routing=RoutingAST(root="n1", forbid_cycles=True, latency_threshold=1.0, sparsity_max_ratio=1.0, allow_expansion=False),
        jacobian=JacobianAST("f", 2, 2, None, None, None, thresholds_min=3, thresholds_max=3, slack=0),
        adaptation_rules=[],
    )
    with pytest.raises(ValueError):
        build_model(ast)
