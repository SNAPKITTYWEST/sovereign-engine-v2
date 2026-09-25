# `prime_gap_tests_integration` (C030)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

End-to-end scenarios across the Tier 2 prime/gap engine (C021–C029),
checked against exact facts about the 25 primes up to 100: π(100) = 25,
gap counts {1: 1, 2: 8, 4: 7, 6: 7, 8: 1}, and gaps summing to
97 − 2 = 95.  returns a per-scenario report
so a failure says which scenario broke and why.

## Dependencies

- [C021 `prime_predicate`](../C021/README.md)
- [C022 `prime_enumeration`](../C022/README.md)
- [C023 `gap_candidate_set`](../C023/README.md)
- [C024 `gap_ordering`](../C024/README.md)
- [C025 `gap_multiplicity`](../C025/README.md)
- [C026 `gap_absolute_difference`](../C026/README.md)
- [C027 `gap_constraint_satisfaction`](../C027/README.md)
- [C028 `gap_verification`](../C028/README.md)
- [C029 `prime_gap_relationship`](../C029/README.md)

## Re-exports

- `prime_predicate::is_prime`
- `prime_enumeration::{primes_up_to, nth_prime, prime_count}`
- `gap_candidate_set::GapCandidateSet`
- `gap_ordering::{order_gaps, GapOrdering}`
- `gap_multiplicity::analyze_gaps`
- `gap_constraint_satisfaction::GapConstraint`
- `gap_verification::{verify_all_gaps, VerificationResult}`
- `prime_gap_relationship::{prime_gap_pairs, maximal_gaps, PrimeGapPair}`

## Public API

| Item | Description |
|---|---|
| `struct ScenarioResult` | Outcome of one scenario. |
| `fn ScenarioResult::passed(&self) -> bool` | Did the scenario pass? |
| `struct IntegrationReport` | Outcome of all scenarios. |
| `fn IntegrationReport::all_passed(&self) -> bool` | True iff every scenario passed. |
| `fn IntegrationReport::failures(&self) -> Vec<&ScenarioResult>` | The failed scenarios. |
| `fn run_prime_gap_integration() -> IntegrationReport` | Run every scenario. |
| `fn tier2_integration_test() -> bool` | True iff every scenario of `run_prime_gap_integration` passes. |

## Tests

`cargo test -p prime_gap_tests_integration` runs 7 unit tests.
