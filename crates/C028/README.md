# gap_verification (C028)

Aggregates constraint checks into a `VerificationResult` and adds structural/self-consistency checks beyond simple range/modulus constraints.

## Public API

- Re-exports `GapCandidateSet`, `GapConstraint`, `verify_gaps`, `filter_by_constraint`.
- `VerificationResult { total, passed, failed, pass_rate: f64 }`.
  - `new(passed, failed)` — derives `total`/`pass_rate`; `pass_rate = 1.0` for the degenerate `total == 0` case (vacuously "all passed").
  - `all_passed()` (`failed == 0`), `is_good()` (`pass_rate >= 0.9`).
- `verify_all_gaps(candidates, constraint) -> VerificationResult`.
- `verify_multi_constraint(candidates, constraints: &[GapConstraint]) -> VerificationResult` — AND across all constraints per candidate.
- `verify_gaps_around_primes(candidates) -> VerificationResult` — structural check: `next > prime`, `gap == next - prime`, `gap >= 2` (the last condition assumes primes beyond 2, since 2→3 has gap 1 — see gaps below).
- `verify_gaps_comprehensive(candidates) -> VerificationResult` — the strictest check: gap arithmetic correctness, strict ordering (`next > prime`), `gap >= 1`, and cross-candidate contiguity (candidate `i`'s `prime` must be `>= candidate[i-1].next_prime`).

## Pipeline role

Depends on `gap_candidate_set` (C023) and `gap_constraint_satisfaction` (C027). This is the crate `prime_gap_tests_integration` (C030) leans on most heavily for its `tier2_integration_test`'s pass/fail gate (`verification.is_good()`).

## Invariants / design notes

- `verify_gaps_around_primes`'s `gap >= 2` check is a real domain assumption that **fails for the 2→3 prime pair** (gap = 1), and its own test suite deliberately avoids that pair (`candidates` in `test_verify_gaps_around_primes` starts at `(3, 5, 2)`, skipping `(2, 3, 1)`). Any caller who includes the 2→3 pair will get an unexpected `failed` count here — this is an implicit, undocumented restriction to odd-prime gaps.
- `verify_gaps_comprehensive`'s contiguity check (`p < candidates[i-1].1`) assumes candidates are passed in ascending, non-overlapping order; it will falsely fail correctly-generated-but-reordered candidates (e.g. output from `order_gaps` with a non-prime-ascending ordering).
- `VerificationResult::new`'s `total == 0 => pass_rate = 1.0` convention (vacuous truth) is consistent with `is_good()` also returning true in that case — worth knowing since an empty verification silently reads as "100% good" rather than "no data."

## Gaps / TODOs

- The 2→3 gap-1 edge case in `verify_gaps_around_primes` is effectively an unstated precondition (odd primes only) that isn't documented on the function and isn't tested against.
- `verify_gaps_comprehensive`'s ordering assumption isn't documented either — a caller feeding it `gaps_in_range`-filtered or reordered candidates would get misleading `failed` counts that look like data corruption rather than an API contract violation.
