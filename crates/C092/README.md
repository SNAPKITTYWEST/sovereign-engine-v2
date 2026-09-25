# `cross_layer_invariants` (C092)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

Invariants that must survive the boundaries between tiers, checked over
finite families:

* **arena_preserves_tensors** (Tier 0 ↔ 1): writing a tensor to an arena's
  DATA region and reading it back preserves every node bit-for-bit and
  every invariant verdict;
* **runtime_invariants_match_static** (Tier 8 ↔ 0): the runtime invariant
  checker reports exactly the static violations, directly and through a
  recorded history;
* dissonance (Tier 0) agrees with gap-constraint satisfaction (Tier 2);
* every gap size occurring between candidate primes has a certified
  resolution of `Z/g` (Tier 2 ↔ 4).

Each check takes its inputs (and, where useful, the component under
test) as parameters so the counterexample harness can feed broken ones.

## Dependencies

- [C007 `gap_tensor_invariants`](../C007/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)
- [C027 `gap_constraint_satisfaction`](../C027/README.md)
- [C049 `resolution_certification`](../C049/README.md)
- [C089 `runtime_invariant_checking`](../C089/README.md)
- [C091 `cross_layer_types`](../C091/README.md)

## Re-exports

- `multiplicity_arena_layout::{ArenaLayout, Region}`

## Public API

| Item | Description |
|---|---|
| `fn check_arena_preserves_tensors_with(family: &[GapTensor], tamper: impl Fn(&mut MultiplicityArena, &ArenaLayout)) -> CorrespondenceReport` | Round-trip every tensor of `family` through an arena. |
| `fn check_arena_preserves_tensors(family: &[GapTensor]) -> CorrespondenceReport` | The real arena check. |
| `fn check_runtime_matches_static_with(family: &[GapTensor], runtime: impl Fn(&GapTensor) -> Vec<Violation>) -> CorrespondenceReport` | Compare a runtime checker with the static one, directly and through a recorded history. |
| `fn check_runtime_matches_static(family: &[GapTensor]) -> CorrespondenceReport` | The real runtime-vs-static check. |
| `fn check_dissonance_matches_gap_constraint(family: &[GapTensor], max_gap: u64) -> CorrespondenceReport` | The number of dissonance violations equals the number of consecutive non-nil prime pairs whose gap fails `GapConstraint::range(0, max_gap)`. |
| `fn check_candidate_gap_resolutions(candidates: &[u32]) -> CorrespondenceReport` | Every gap between distinct candidate primes has a fully certified resolution of `Z/g`. |
| `fn run_all(family: &[GapTensor], candidates: &[u32]) -> Vec<CorrespondenceReport>` | Run every check of this crate on the standard inputs. |

## Tests

`cargo test -p cross_layer_invariants` runs 2 unit tests.
