# Regex Lexer Specification — Sparse Latency Routing Hierarchy

## Audience

Implementers maintaining `bin/sparse_router.sh`, and anyone auditing whether
the canonical XML's `<parser>` section actually matches the lexical rules
the Bash implementation enforces at runtime.

## Purpose

Define, precisely and exhaustively, the lexical token classes recognized
anywhere an identifier, number, or structural expression is accepted in this
system, and state where each pattern is declared, where it is enforced, and
its complexity.

## Assumptions

- The lexer described here is a *validation* lexer, not a general-purpose
  tokenizer with a scanner loop: attribute values arrive already segmented
  by the XML parser (`xmllint`), so each token class is checked with a
  single anchored regex match (`[[ "$value" =~ $PATTERN ]]` in Bash, or an
  `xs:pattern` restriction in the schema), not by scanning a character
  stream.
- Every pattern below is fully anchored (`^...$`) so partial matches can
  never silently pass validation.
- No pattern below uses backtracking-prone constructs (nested quantifiers,
  ambiguous alternation over the same character class). Each is a single
  linear scan, so matching cost is O(n) in the length of the input string,
  never worse.

## Token classes

| Token          | Pattern                                     | Declared in                          | Enforced in                                              | Complexity |
|----------------|----------------------------------------------|---------------------------------------|-----------------------------------------------------------|------------|
| `IDENTIFIER`   | `^[A-Za-z_][A-Za-z0-9_]*$`                   | `network.xml` `<parser>`, `network.xsd` `identifier` simpleType | `RE_IDENTIFIER` in `build_sparse_graph()` (node/edge ids) | O(n), single pass |
| `INTEGER_DIM`  | `^[1-9][0-9]*$`                              | `network.xml` `<parser>`             | `RE_SHAPE_DIM` in `recurse_tensor()` (I7)                 | O(n) |
| `FLOAT_LATENCY`| `^[0-9]+\.[0-9]+$`                           | `network.xml` `<parser>`             | documentary only — see "Known lexical gap" below          | O(n) |
| `NODE_ID`      | `^n[1-9][0-9]*$`                             | `network.xml` `<parser>`             | documentary; actual node ids are validated against the more general `IDENTIFIER` pattern, since the schema's `identifier` type does not require an `n`-prefix | O(n) |
| `EDGE_ID`      | `^e[1-9][0-9]*$`                             | `network.xml` `<parser>`             | documentary; same relationship to `IDENTIFIER` as `NODE_ID` | O(n) |
| `TENSOR_EXPR`  | `^t[1-9][0-9]*(\.[1-9][0-9]*)*$`              | `network.xml` `<parser>`             | documentary; the schema's `tensorIdentifier` type (`[A-Za-z_][A-Za-z0-9_]*(\.[0-9]+)*`) is the pattern actually enforced against tensor ids, and is deliberately more permissive (it does not require a `t`-prefix, since a tensor could legitimately be named anything lexically valid as an identifier) | O(n) |
| `ROUTE_EXPR`   | `^(e[1-9][0-9]*)(->e[1-9][0-9]*)*$`           | `network.xml` `<parser>`             | documentary; this system does not currently serialize or parse a standalone "route expression" string anywhere in `bin/sparse_router.sh` — routes are represented internally as the `DIST`/`HOPS`/`LASTPRIO` associative arrays produced by `calculate_latency()`, not as a `ROUTE_EXPR`-formatted string. This token is reserved for a future textual route-log format. | O(n) |

Two additional patterns exist only in Bash, not in the XML `<parser>`
catalog above, because they check a semantic property (sign, in the case of
`RE_FLOAT`) that the declarative token list intentionally does not:

| Bash variable | Pattern                        | Used by                          | Why it isn't in `<parser>` |
|----------------|---------------------------------|-----------------------------------|------------------------------|
| `RE_FLOAT`     | `^-?[0-9]+(\.[0-9]+)?$`          | `build_sparse_graph()` (I6 check) | Deliberately accepts a leading `-` and an optional fractional part, unlike the stricter `FLOAT_LATENCY` token above. This is a considered choice, not an inconsistency: a negative latency value must be lexically *acceptable* so it reaches the I6 invariant check and produces a specific, actionable diagnostic ("I6 violation: edge e1 has a negative latency component: -0.10"), rather than being rejected earlier by an opaque lexer failure that can't say *why* the value is wrong. |

## Known lexical gap

`FLOAT_LATENCY` (`^[0-9]+\.[0-9]+$`) as declared in the XML `<parser>`
catalog does not accept a leading sign or an integer-only value (`"1"`
without a decimal point), while the schema types the latency attributes as
plain `xs:decimal` (which accepts both). This is intentional and is the same
consideration as `RE_FLOAT` above: the declarative token table describes
what a *well-formed* latency value looks like; the runtime invariant checker
is where sign and shape are actually enforced, with a diagnosis attached.
Treat the `<parser>` section as documentation of intent, and
`build_sparse_graph()` / `network.xsd` as the enforced contract — this is
the same schema/invariant-checker separation of concerns documented in
`network.xsd`'s header comment.

## Verification notes

- Every pattern in the "Token classes" table above was checked with
  `[[ "$value" =~ $PATTERN ]]` against both matching and non-matching
  sample strings during development of `tests/invalid/invalid_tensor_dim.xml`
  (dimension `"0"` correctly rejected by `INTEGER_DIM`) and
  `tests/invalid/negative_latency.xml` (`"-0.10"` correctly rejected by
  `FLOAT_LATENCY` semantics, though accepted lexically by `RE_FLOAT` so I6
  can report it specifically).
- The claim "each pattern is a single linear scan" is a structural
  observation about the patterns as written (no nested quantifiers, no
  overlapping alternation), not a benchmark measurement.

## Terminology

- **Token class**: a named category of lexically valid string, defined by
  one anchored regular expression.
- **Declarative** (of a pattern): recorded in `network.xml`'s `<parser>`
  section for documentation and audit purposes.
- **Enforced**: actually evaluated by `bin/sparse_router.sh` or checked by
  `xmllint --schema` against `network.xsd` at run time.
- **Anchored**: constrained with `^` and `$` so the pattern must match the
  entire string, not a substring.
