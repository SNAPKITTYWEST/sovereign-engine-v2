# prime_gap_tests_integration (C030)

The capstone integration crate for Tier 2: re-exports the full prime/gap API surface and provides `tier2_integration_test()`, an end-to-end smoke test exercised as a library function (not just a `#[test]`).

## Public API

- Re-exports from every Tier 2 crate: `is_prime`; `primes_up_to`, `nth_prime`, `prime_count`; `GapCandidateSet`; `order_gaps`, `GapOrdering`; `analyze_gaps`; `GapConstraint`; `verify_all_gaps`, `VerificationResult`; `prime_gap_pairs`, `maximal_gaps`, `PrimeGapPair`.
- `tier2_integration_test() -> bool` — a 6-step pipeline run as a plain function returning a bool (not `Result`, no error detail on failure): generate primes → build candidate set → verify against a `[1,10]` range constraint (requires `is_good()`, i.e. ≥90% pass rate) → analyze multiplicity → build prime-gap pairs → compute maximal gaps.

## Pipeline role

Depends on nearly the entire Tier 2 family: `prime_predicate`, `prime_enumeration`, `gap_candidate_set`, `gap_ordering`, `gap_multiplicity`, `gap_constraint_satisfaction`, `gap_verification`, `prime_gap_relationship` (C021-C029, excluding none). It is the terminal crate of Tier 2 — nothing in the C021-C030 range depends on it, and it's the natural place a Tier 3 (Krull dimension / commutative algebra layer, per the workspace's stated architecture) would pull a single "is Tier 2 healthy" check from.

## Invariants / design notes

- `tier2_integration_test` returns a bare `bool` and early-returns `false` at the first failing step, discarding which step failed — a caller (or CI) gets no diagnostic beyond pass/fail. Given this crate's role as an integration gate before certification (Tier 4 presumably consumes a signal like this), that's a real observability gap.
- The `90%` pass-rate threshold (via `VerificationResult::is_good()`) means this integration test can pass even with up to 10% of candidate gaps failing the `[1,10]` range constraint — a deliberately soft gate rather than a strict all-or-nothing check.
- Uses `GapCandidateSet::from_limit(100).candidates_with_gap(1)`, which (per C023) consumes the set — consistent usage, no misuse here.

## Gaps / TODOs

- `tier2_integration_test`'s bool-only return discards failure diagnostics — worth upgrading to a `Result<(), String>` or a step-tagged enum if this is meant to gate certification decisions in Tier 4.
- No test in this crate exercises the `false`-returning paths of `tier2_integration_test` (e.g. by feeding a limit too small to have 10 primes) — only the happy path is verified.
- This crate inherits the `is_first_occurrence` concern from C029 by re-exporting `maximal_gaps`/`PrimeGapPair` without re-testing that specific method.
