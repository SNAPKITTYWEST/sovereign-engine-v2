# AST Specification — Sparse Latency Routing Hierarchy

## Audience

Implementers and auditors who need the formal shape of the parsed
representation between "raw XML text" and "the associative arrays
`bin/sparse_router.sh` computes over" — i.e. what this system's AST actually
is, concretely, not just as a diagram.

## Purpose

State the typed AST node grammar for a canonical `network.xml` document,
and state plainly which part of `bin/sparse_router.sh` realizes each node
type, so the mapping from "SECTION 6: AST specification" to the executable
pipeline in SECTION 10 is checkable rather than aspirational.

## Assumptions

- This implementation does **not** hand-roll a second, custom AST data
  structure in Bash. `xmllint`'s parse of `network.xml` — via libxml2 — *is*
  the AST: it is a real tree with typed nodes, attributes, and structural
  validity already checked against `network.xsd` before a single XPath query
  runs. Claiming to also build an independent "AST" object in Bash on top of
  that would be redundant at best and, if it silently diverged from the XML
  tree libxml2 already validated, actively misleading. What `bin/sparse_router.sh`
  builds instead is a **flattened symbol table** — the bash associative
  arrays declared near the top of the script (`NODE_IDS`, `EDGE_SRC`,
  `TENSOR_SHAPE`, and so on) — populated by walking the AST via targeted
  XPath expressions. That symbol table, not a second parallel tree, is what
  every downstream algorithm (Dijkstra, cycle detection, rank calculation)
  operates on.
- The grammar below is therefore a specification of two things at once,
  deliberately: the shape libxml2 already gives us for free (columns 1–2),
  and the concrete Bash realization derived from it (column 3). Where a
  node type has no separate Bash variable, that is stated explicitly rather
  than a placeholder being invented.

## Grammar

```
Network        ::= Execution Nodes Edges Tensors Routing Jacobian Parser Adaptation Verification
Execution      ::= max_recursion_depth: PositiveInt
                    hash_algorithm: "sha256"
                    rank_backend: "computed" | "structural"
Nodes          ::= Node+
Node           ::= id: Identifier, priority: Int
Edges          ::= Edge*
Edge           ::= id: Identifier, source: Identifier, destination: Identifier,
                    computation_latency: Decimal, communication_latency: Decimal,
                    synchronization_latency: Decimal, weight: Decimal,
                    activation_state: "active" | "inactive" | "pruned",
                    tensor_dependency: TensorIdentifier,
                    routing_priority: Int, sparsity_class: "low" | "medium" | "high"
Tensors        ::= Tensor+
Tensor         ::= id: TensorIdentifier, shape: CommaSeparatedPositiveInts,
                    dtype: String, rank_hint: NonNegativeInt?, sparse: Bool?,
                    recursion: Recursion?
Recursion      ::= max_depth: NonNegativeInt, Tensor+          # self-referential: a Recursion
                                                                # holds one or more nested Tensor
                                                                # nodes, each of which may itself
                                                                # hold a Recursion — this is the
                                                                # "recursively nested tensor" node
Routing        ::= Hierarchy Latency Sparsity
Hierarchy      ::= root: Identifier, forbid_cycles: Bool
Latency        ::= objective: "minimize", threshold: NonNegativeDecimal
Sparsity       ::= max_ratio: Decimal, allow_expansion: Bool
Jacobian       ::= Function Matrix? Rank
Function       ::= name: Identifier, input_dim: PositiveInt, output_dim: PositiveInt
Matrix         ::= rows: PositiveInt, cols: PositiveInt, text: SemicolonSeparatedCommaSeparatedDecimals
Rank           ::= thresholds_min: NonNegativeInt, thresholds_max: NonNegativeInt, slack: NonNegativeInt
Parser         ::= RegexRule+
RegexRule      ::= name: String, pattern: String
Adaptation     ::= Rule*
Rule           ::= id: Identifier, condition: Condition, action: Action
Condition      ::= "latency_exceeds_threshold" | "rank_decreases" | "rank_increases"
                  | "tensor_dimension_changes" | "sparsity_exceeds_maximum"
Action         ::= "evaluate_alternate_route" | "evaluate_redundant_edge_removal"
                  | "evaluate_capacity_expansion" | "recompute_dependent_routing_metadata"
                  | "reject_topology_expansion"
Verification   ::= Invariant+
Invariant      ::= id: String, description: String
```

## Concrete realization in `bin/sparse_router.sh`

| AST node    | XPath used to read it                                    | Bash realization (symbol table)                                                                 |
|-------------|-----------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| `Network`   | `/network/@name`, `/network/@version`                     | `NET_NAME`, `NET_VERSION` (scalars)                                                                |
| `Execution` | `/network/execution/*`                                     | `MAX_RECURSION_DEPTH`, `HASH_ALGORITHM`, `RANK_BACKEND` (scalars, set in `parse_network()`)          |
| `Node`      | `/network/nodes/node[i]/@id`, `@priority`                  | `NODE_IDS` (array), `NODE_PRIORITY[id]` (assoc. array), set in `build_sparse_graph()`               |
| `Edge`      | `/network/edges/edge[i]/@*`                                | `EDGE_IDS` (array); `EDGE_SRC`, `EDGE_DST`, `EDGE_LAT`, `EDGE_PRIORITY`, `EDGE_TENSOR_DEP`, `EDGE_ACTIVE` (assoc. arrays), set in `build_sparse_graph()` |
| `Tensor`    | `${xpath}/@id`, `@shape`, `@dtype`, `@rank_hint` (recursive walk) | `TENSOR_IDS` (array); `TENSOR_SHAPE`, `TENSOR_DTYPE`, `TENSOR_RANKHINT` (assoc. arrays), set by `recurse_tensor()` |
| `Recursion` | `count(${xpath}/recursion/tensor)`, then `${xpath}/recursion/tensor[j]` per child | not materialized as its own object — `recurse_tensor()` recurses directly over the AST's `<recursion><tensor>` children, incrementing a `depth` parameter checked against `MAX_RECURSION_DEPTH` (I8) |
| `Hierarchy` | `/network/routing/hierarchy/@root`, `@forbid_cycles`        | `ROOT_NODE`, `FORBID_CYCLES` (scalars), set in `parse_routing()`                                     |
| `Latency`   | `/network/routing/latency/@threshold`                       | `LATENCY_THRESHOLD` (scalar)                                                                        |
| `Sparsity`  | `/network/routing/sparsity/@max_ratio`, `@allow_expansion`   | `SPARSITY_MAX_RATIO`, `ALLOW_EXPANSION` (scalars); `SPARSITY_RATIO` is *computed*, not parsed (`E / V^2` in `build_sparse_graph()`) |
| `Function`  | `/network/jacobian/function/@*`                              | `JAC_INPUT_DIM`, `JAC_OUTPUT_DIM` (scalars)                                                          |
| `Matrix`    | `/network/jacobian/matrix` (text + `@rows`/`@cols`)          | `JAC_MATRIX_TEXT`, `JAC_MATRIX_ROWS`, `JAC_MATRIX_COLS` (scalars), consumed by `calculate_rank()`'s embedded `python3`/numpy call |
| `Rank`      | `/network/jacobian/rank/@*`                                  | `RANK_MIN`, `RANK_MAX`, `RANK_SLACK` (scalars)                                                       |
| `RegexRule` | `/network/parser/regex/@name`, `@pattern`                    | documentary only at runtime — see `spec/regex_lexer.md`'s "Known lexical gap" section; the actually-enforced patterns are hardcoded in `bin/sparse_router.sh` as `RE_IDENTIFIER`, `RE_FLOAT`, `RE_SHAPE_DIM` |
| `Rule`      | `/network/adaptation/rules/rule/@*`                           | not materialized as an array of objects — queried on demand via `_rule_declared(condition)`, an XPath existence check (`count(...rule[@condition='$cond']) >= 1`), called from `adapt_network()` |
| `Invariant` | `/network/verification/invariants/invariant/@*`                | documentary only — the invariants themselves are enforced as inline Bash checks throughout `build_sparse_graph()`, `recurse_tensor()`, `parse_jacobian()`, `calculate_rank()`, and `verify_invariants()`, each tagged with its `I<n>` id in a `die` message; nothing reads this XML section at runtime to decide behavior |

## Why some AST nodes have "no dedicated Bash variable"

Three node types above (`Recursion`, `RegexRule`-as-enforced-pattern,
`Rule`, `Invariant`) are read from the AST directly at the point of use
rather than copied into a persistent symbol-table array first. This is a
deliberate efficiency and correctness choice, not an omission:

- `Recursion` is walked once, depth-first, exactly when `parse_tensor()`
  needs it — materializing it into a separate array first would mean
  walking the tree twice for no benefit.
- `Rule` existence is checked with a single XPath boolean test
  (`_rule_declared`) at the exact moment `adapt_network()` needs to know
  whether a condition has a declared rule — there is no scenario in this
  engine where the full rule list is iterated independently of evaluating
  triggering conditions.
- `Invariant` and the declarative `RegexRule` patterns are, by design,
  **read by humans and by `xmllint --schema`, not by `bin/sparse_router.sh`
  at runtime** — see `network.xsd`'s header comment on why schema
  validation and semantic invariant-checking are deliberately separate
  mechanisms. Pretending the script "parses" these two sections into
  active control flow would misstate what the code does.

## Verification notes

- The grammar above was checked field-by-field against `spec/network.xsd`
  (the actual schema) rather than written from memory; every attribute name
  and cardinality in the grammar has a corresponding `xs:attribute` /
  `xs:element` in `network.xsd`.
- The "Concrete realization" table was checked line-by-line against the
  current `bin/sparse_router.sh` (each Bash variable name was grep-matched
  against the script, not transcribed from an earlier draft).

## Terminology

- **AST (abstract syntax tree)**: here, the libxml2 DOM tree `xmllint`
  builds while parsing `network.xml`, after it has already been confirmed
  schema-valid.
- **Symbol table**: the flat set of Bash associative arrays populated by
  walking the AST once per run; this is what the algorithmic functions
  (Dijkstra, DFS, rank calculation) actually read and write.
- **Documentary** (of an AST node or pattern): present in the canonical XML
  for human/audit legibility, but not consulted by `bin/sparse_router.sh`'s
  control flow at runtime.
