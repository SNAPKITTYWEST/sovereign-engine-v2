# Sparse Latency Routing Formalization Engine

## Audience

Anyone running, auditing, or extending this system: engineers integrating
it into a pipeline, and reviewers checking that the canonical XML, the
schema, the Bash implementation, and the test suite actually agree with
each other.

## Purpose

A directed sparse graph whose routing topology can be deterministically
adapted using measured latency and Jacobian-rank information, plus a
recursively-nested tensor model, expressed as one canonical XML source of
truth (`spec/network.xml`, checked by `spec/network.xsd`) and one
executable Bash implementation (`bin/sparse_router.sh`) that never
diverges from it.

## Assumptions

- `xmllint` (libxml2) is installed and on `PATH`. There is no fallback
  XML parser: `validate_xml()` calls `require_cmd xmllint` and fails
  closed (exit 69) if it is missing, rather than falling back to
  grep/sed, which cannot reliably parse XML.
- `python3` with `numpy` importable is required whenever
  `execution/rank_backend` is `computed` **and** a `<jacobian><matrix>`
  is supplied — `calculate_rank()` shells out to `numpy.linalg.matrix_rank`
  for the one thing Bash genuinely cannot do itself (real linear algebra).
  If either is missing, the run fails closed (exit 69) rather than
  silently falling back to the structural heuristic.
- Bash ≥ 4 (associative arrays).

## Layout

```
spec/network.xsd          canonical schema — the machine-checkable half of "XML is the source of truth"
spec/network.xml          canonical example instance (5 nodes, 5 edges, one recursively nested tensor,
                           a real rank-deficient 3x3 Jacobian matrix)
spec/regex_lexer.md        every lexical token class: pattern, where declared, where enforced, complexity
spec/ast_spec.md           the AST grammar and its concrete realization as bin/sparse_router.sh's symbol table
bin/sparse_router.sh        the implementation: parse -> build sparse graph -> recurse tensor ->
                           Jacobian/rank -> latency (Dijkstra) -> adapt -> verify -> hash-chain -> emit
tests/valid/                one schema-valid, invariant-clean fixture
tests/invalid/              nine fixtures, each violating exactly one invariant or feasibility condition
tests/adaptation/            three two-step fixture pairs (topology no-op, successful adaptation,
                           rejected adaptation) plus one tamper fixture for hash verification
tests/run_tests.sh           executes every fixture against bin/sparse_router.sh and asserts real exit codes
                           and, for adaptation cases, real emitted JSON fields
state/                     STATE_NNN.json / AUDIT_NNN.json emitted by `run` (created on first use)
```

## Usage

```
bin/sparse_router.sh run <network.xml> [--schema <network.xsd>] [--state-dir <dir>]
bin/sparse_router.sh verify <state.json> <network.xml> [--schema <network.xsd>]
```

`run` validates, parses, builds the sparse graph, recurses the tensor
model, computes rank and latency, evaluates the five adaptation rules
against whatever the previous state in `--state-dir` recorded, verifies
every invariant, and — only if every prior step passed — atomically
publishes `STATE_NNN.json` and `AUDIT_NNN.json` (write-to-temp then `mv`,
so a crash mid-write never leaves a half-written file that could be
mistaken for a real one — this is I12).

`verify` recomputes the canonical hash from a given `network.xml` (using
the `prev_hash` recorded inside the given state file) and confirms it
matches the `hash` field in that state file. A mismatch means the XML or
the recorded state have diverged — from tampering, from hand-editing, or
from drift — and is reported as exit 68, not silently ignored.

### Quick start

```
bin/sparse_router.sh run spec/network.xml
bin/sparse_router.sh verify state/STATE_000.json spec/network.xml
```

### Running the test suite

```
tests/run_tests.sh
```

This actually invokes `bin/sparse_router.sh` against all 17 fixtures (one
valid, nine invalid, seven adaptation/tamper) in fresh temporary state
directories, and asserts on real exit codes and, where relevant, real
emitted JSON fields — nothing in the suite is a canned expectation checked
against nothing.

## Exit codes

| Code | Meaning                                                                 |
|------|--------------------------------------------------------------------------|
| 0    | success — state published, or `verify` matched                          |
| 64   | usage error — bad arguments, missing files                              |
| 65   | data error — XML not well-formed, or fails schema validation             |
| 66   | invariant violation (I1–I9 structural/semantic failure)                 |
| 67   | adaptation could not satisfy the routing objective (fail-closed, not an invariant violation) |
| 68   | state/hash verification mismatch — tamper or drift detected              |
| 69   | required external tool unavailable (`xmllint` or `python3`+`numpy`)      |

## The twelve invariants

I1–I9 are enforced inline, at the earliest point in the pipeline where
they become checkable (mostly in `build_sparse_graph()`, `recurse_tensor()`,
`parse_jacobian()`, and `calculate_rank()`), so a violation is reported
with the specific data that caused it rather than after a generic
end-of-pipeline sweep. I4 and a second sparsity check are performed in
`verify_invariants()`, once the full graph exists. I10 is checked inside
`adapt_network()` itself (an adaptation with no recorded triggering
condition is itself a bug and is treated as one). I11 is the property
`verify` mechanically checks. I12 is enforced structurally — by the
write-temp-then-`mv` pattern in `emit_state()` — rather than by a separate
runtime check, since the failure mode I12 guards against (a partially
written state file) cannot occur once writes are atomic.

## Known limitations

Stated plainly, per the mathematical-honesty requirement this system was
built under: several of the properties below are genuinely proven given
stated assumptions, several are engineering choices with a stated
rationale, and at least one relationship this system explicitly does
**not** claim is worth naming directly, because it would be easy to
misread the code as claiming it.

- **Dijkstra's optimality here is a real, checkable guarantee — not a
  heuristic.** `calculate_latency()` finds the true latency-minimal route
  under the active topology, given nonnegative edge weights. Those
  weights are nonnegative *because* I6 rejects negative latency values
  before Dijkstra ever runs — the guarantee depends on that invariant
  holding, and would not hold if it didn't.
- **"Computed" rank is a real linear-algebra result; "structural" rank is
  an explicitly labeled proxy, never the same claim.** When
  `rank_backend=computed` and a `<jacobian><matrix>` is supplied,
  `RANK_SOURCE` is set to `"computed"` and the value comes from
  `numpy.linalg.matrix_rank` on that real matrix. When no matrix is
  supplied (or the backend is `structural`), `RANK_SOURCE` is
  `"structural"` and the value is a count of distinct active tensor
  dependencies, capped at `min(input_dim, output_dim)` — an engineering
  proxy for "how many independent routing paths carry distinguishable
  tensor state," and nothing in the emitted state or audit JSON is
  allowed to describe a structural value as "the Jacobian rank" without
  that qualifier.
- **Sparsity does not automatically produce lower latency, and this
  system never asserts that it does.** I5 (sparsity bound) and the
  latency objective are checked and optimized independently; a sparser
  graph can have *higher* minimal-route latency than a denser one if its
  surviving edges happen to be slower. Nothing in `adapt_network()` treats
  "fewer edges" as a proxy for "faster route."
- **This engine never fabricates topology.** `_evaluate_redundant_edge_removal()`
  can only mark an *existing* edge `pruned`; nothing in
  `bin/sparse_router.sh` can invent a new edge, node, or tensor that isn't
  already declared in the canonical XML. A `rank_increases` +
  `evaluate_capacity_expansion` trigger with `allow_expansion=false`
  is therefore recorded as a rejected condition
  (`sparsity_exceeds_maximum` alongside `rank_increases`), not silently
  granted — see `tests/adaptation/failed_step2.xml`.
- **Adaptation is per-run, not self-modifying.** A pruned edge (from a
  successful `rank_decreases` adaptation) is recorded in that run's
  emitted `STATE_NNN.json`/`AUDIT_NNN.json`, but is **not** written back
  into `network.xml`. A subsequent `run` against the same XML file starts
  from the original topology again, and compares its own freshly computed
  rank against the *previous run's recorded rank* (read from the latest
  `STATE_NNN.json` in `--state-dir`) — not against a topology this engine
  silently rewrote. This keeps "the canonical XML is the source of truth"
  literally true, at the cost of the engine not being able to "remember"
  a pruned edge across runs of the same file. Regenerating a new canonical
  XML from an adapted state is out of scope for this implementation.
- **The adaptation rule catalog is declared completely; the trigger
  engine implements three of its five conditions as live comparisons.**
  `adapt_network()` actively evaluates `latency_exceeds_threshold`,
  `rank_decreases`, and `rank_increases` (with `sparsity_exceeds_maximum`
  recorded as a consequence of a rejected `rank_increases`, per rule r5's
  intent). `tensor_dimension_changes` (rule r4) has no independent trigger
  in this version — tensor-dimension validity is enforced as a hard
  invariant (I7) rather than compared run-over-run for "change." Declaring
  a rule in `<adaptation><rules>` that has no corresponding live trigger
  is a real gap in this implementation, stated here rather than obscured.
- **The `FLOAT_LATENCY` lexical token and the enforced `RE_FLOAT` pattern
  differ on purpose.** See `spec/regex_lexer.md`'s "Known lexical gap"
  section: the declared token is stricter (no sign) than the pattern
  actually enforced (`RE_FLOAT` accepts a leading `-`), because a negative
  latency must be lexically *acceptable* so I6 can name it specifically
  in a diagnostic, rather than being opaquely rejected earlier by the
  lexer.
- **`xmllint --xpath` reparses the document on every call.** `xp()` and
  `xp_of()` invoke `xmllint` fresh for every single attribute or count
  query. For the canonical example (5 nodes, 5 edges, one nested tensor)
  this is dozens of subprocess calls per run — negligible in practice, but
  it means this implementation's parse cost is `O(queries * document size)`,
  not `O(document size)` for a single-pass parse. A production system
  processing large XML documents at high frequency would want a
  single-parse approach (e.g. a real XML library) instead of
  re-invoking `xmllint` per field.
- **`calc()`'s floating-point arithmetic is `awk`'s double-precision
  arithmetic**, not arbitrary-precision decimal. For the latency and
  sparsity-ratio magnitudes this system deals with, that is not a
  practical concern, but it is not the same guarantee as, say, Python's
  `decimal` module.

## Reproduction

```
cd sparse-latency-routing
xmllint --noout --schema spec/network.xsd spec/network.xml   # confirm schema validity
bin/sparse_router.sh run spec/network.xml                     # confirm genesis state (exit 0)
bin/sparse_router.sh verify state/STATE_000.json spec/network.xml  # confirm hash matches (exit 0)
tests/run_tests.sh                                             # confirm all 14 scenario types (26 assertions) pass
```

## Terminology

- **Fail closed**: on any of the nine documented failure conditions, the
  adaptation is not applied, no state is published, a nonzero exit code
  is returned, and the previous valid state (if any) is left untouched.
- **Canonical XML**: `network.xml` is the sole source of truth for
  topology, tensor structure, thresholds, and rules; the Bash
  implementation never holds authoritative state that isn't derivable
  from it plus the previous run's published state.
- **Structural (rank)**: an engineering proxy for rank, explicitly not a
  linear-algebra result, used only when no real Jacobian matrix is
  available to compute one from.
