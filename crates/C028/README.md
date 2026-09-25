# `gap_verification` (C028)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Comprehensive gap verification and validation.

## Dependencies

- [C023 `gap_candidate_set`](../C023/README.md)
- [C027 `gap_constraint_satisfaction`](../C027/README.md)

## Re-exports

- `gap_candidate_set::GapCandidateSet`
- `gap_constraint_satisfaction::{GapConstraint, verify_gaps, filter_by_constraint}`

## Public API

| Item | Description |
|---|---|
| `struct VerificationResult` | Result of gap verification. |
| `fn VerificationResult::new(passed: usize, failed: usize) -> Self` | Create from pass/fail counts. |
| `fn VerificationResult::all_passed(&self) -> bool` | Check if all gaps passed. |
| `fn VerificationResult::is_good(&self) -> bool` | Check if verification is "good" (>= 90% pass rate). |
| `fn verify_all_gaps(candidates: &[(u64, u64, u64)], constraint: &GapConstraint) -> VerificationResult` | Verify all gaps in a set against a constraint. |
| `fn verify_multi_constraint(candidates: &[(u64, u64, u64)], constraints: &[GapConstraint]) -> VerificationResult` | Verify using multiple constraints (all must pass). |
| `fn verify_gaps_around_primes(candidates: &[(u64, u64, u64)]) -> VerificationResult` | Verify that each `(p, q, gap)` is consistent with `p`, `q` being consecutive primes: `q > p`, `gap = q − p ≥ 1`, and the gap is even unless `p = 2` (every prime after 2 is odd, so the only odd gap is 2 → 3). |
| `fn verify_gaps_comprehensive(candidates: &[(u64, u64, u64)]) -> VerificationResult` | Comprehensive verification including structural checks. |

## Tests

`cargo test -p gap_verification` runs 5 unit tests.
