"""Lexer: token classes for the canonical XML's attribute values (report
SECTION 10).

Regular expressions are used ONLY for lexical recognition -- confirming
that a single already-segmented attribute value (an XML parser, not this
module, is what segments `network.xml` into elements and attributes; see
`xml_parser.py`) has the right shape. No pattern here attempts to parse a
recursive structure (nested tensors, a routing hierarchy) -- that is the
AST/parser's job (`ast_nodes.py`, `xml_parser.py`), built on top of a real
tree-shaped XML document, exactly as report SECTION 10 requires ("Do not
attempt to use regex as a complete recursive grammar").

Every pattern is fully anchored (`^...$`), so a partial match can never
silently pass, and every pattern is a single linear scan (no nested
quantifiers, no ambiguous alternation) -- O(n) in the length of the
token, stated per report SECTION 13's complexity-analysis requirement.
"""
from __future__ import annotations

import re
from typing import Dict, Pattern

TOKEN_PATTERNS: Dict[str, Pattern[str]] = {
    "NODE_IDENTIFIER": re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$"),
    "TENSOR_IDENTIFIER": re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[0-9]+)*$"),
    "DIMENSION": re.compile(r"^[1-9][0-9]*$"),                       # a single positive-integer shape dimension
    "EDGE_IDENTIFIER": re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$"),        # same lexical shape as NODE_IDENTIFIER
    "LATENCY_VALUE": re.compile(r"^[0-9]+(\.[0-9]+)?$"),               # a nonnegative decimal, no sign
    "SIGNED_LATENCY_VALUE": re.compile(r"^-?[0-9]+(\.[0-9]+)?$"),      # accepts a leading '-', see note below
    "RANK_THRESHOLD": re.compile(r"^(0|[1-9][0-9]*)$"),                # a nonnegative integer
    "ROUTING_RULE_CONDITION": re.compile(
        r"^(latency_exceeds_threshold|rank_decreases|rank_increases|"
        r"tensor_dimension_changes|sparsity_exceeds_maximum)$"
    ),
    "ROUTING_RULE_ACTION": re.compile(
        r"^(evaluate_alternate_route|evaluate_redundant_edge_removal|"
        r"evaluate_capacity_expansion|recompute_dependent_routing_metadata|"
        r"reject_topology_expansion)$"
    ),
    "RECURSION_LIMIT": re.compile(r"^[0-9]+$"),                       # a nonnegative integer (0 is a legal bound)
    "BOOLEAN": re.compile(r"^(true|false)$"),
}

# NOTE on SIGNED_LATENCY_VALUE vs LATENCY_VALUE: a negative latency value
# must be lexically ACCEPTABLE (matched by SIGNED_LATENCY_VALUE) so it can
# reach the I3 invariant check (sparse_routing.model.graph.Edge.latency,
# checked by SparseGraph.check_no_negative_latency) and be reported with a
# specific, actionable diagnostic -- rather than being rejected here, at
# the lexical stage, with no way to say *why* it's wrong. LATENCY_VALUE
# (no sign) is what the canonical XML's declared token catalog considers
# "well-formed"; SIGNED_LATENCY_VALUE is what this parser actually applies
# when reading an edge's latency attributes, precisely so a negative value
# is a semantic (I3) failure, not an opaque lexical one. This is the same
# considered choice the companion Bash reference implementation documents
# in its spec/regex_lexer.md "Known lexical gap" section.


class LexError(ValueError):
    def __init__(self, token_class: str, value: str) -> None:
        super().__init__(f"value {value!r} does not match token class {token_class!r} (pattern: {TOKEN_PATTERNS[token_class].pattern})")
        self.token_class = token_class
        self.value = value


def lex_value(token_class: str, value: str) -> str:
    """Confirms `value` matches the named token class; returns it
    unchanged (a lexer's job is recognition, not transformation) or
    raises LexError. O(len(value))."""
    pattern = TOKEN_PATTERNS[token_class]
    if not pattern.match(value):
        raise LexError(token_class, value)
    return value
