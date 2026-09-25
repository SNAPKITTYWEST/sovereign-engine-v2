# recursion_lemmas_library

Same template again, targeted at recursive-solver termination/depth-bound
properties, tagged with `max_depth: Option<usize>`.

## What it does

`RecursionLemma { name, statement, status, proof, max_depth }`,
builder `with_max_depth(depth)`, `prove`, `is_proven`.
`RecursionLemmasLibrary` — identical shape to C073/C074 —
add/get/count plus `lemmas_with_max_depth(depth)`.

## Public API

- `LemmaStatus`, `RecursionLemma::new`, `with_max_depth`, `prove`,
  `is_proven`
- `RecursionLemmasLibrary::new`, `add_lemma`, `get_lemma[_mut]`,
  `count_proven`, `count_open`, `lemmas_with_max_depth`

## Pipeline role

Depends on `type_checking_interface` (C071) and four Tier-3 recursive-solver
crates (`recursive_solver_state` C031, `recursion_depth_management` C032,
`recursion_base_case` C036, `recursion_backtracking` C037), unused in the
file body. Feeds `cross_layer_lemmas_library` (C079) and
`lean_obligation_aggregator` (C080).

## Gaps / weak spots

- Same structural gap as C073/C074: no actual termination or depth-bound
  lemmas are populated; the four upstream recursion crates are declared
  dependencies but not referenced.
- If this crate is meant to eventually formalize termination for the
  recursive solver in Tier 2, that is the single most safety-relevant
  unproven claim in the whole repo (an unbounded/incorrectly-terminating
  solver would be a real correctness bug) — flagging as the highest-value
  gap to close first among the six lemma libraries.
