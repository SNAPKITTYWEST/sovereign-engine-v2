# gap_multiplicity (C025)

Frequency/statistics analysis of gap sizes across a candidate set: how often each gap size occurs, and basic descriptive statistics (mean, std-dev, anomaly detection).

## Public API

- Re-exports `GapCandidateSet` (from `gap_candidate_set`), `order_gaps`/`GapOrdering` (from `gap_ordering`).
- `GapMultiplicity { gap_size: u64, count: usize, positions: Vec<u64> }` — occurrences of one gap size and the primes where they occur.
- `analyze_gaps(candidates: &[...]) -> Vec<GapMultiplicity>` — groups candidates by gap size via `BTreeMap`, so output is sorted by `gap_size` ascending.
- `most_common_gaps(candidates, k) -> Vec<GapMultiplicity>` — re-sorts `analyze_gaps` output by `count` descending, truncates to `k`.
- `average_gap(candidates) -> f64`, `gap_std_dev(candidates) -> f64` (sample std-dev, `n-1` denominator; returns 0.0 for `< 2` candidates).
- `is_anomalous_gap(gap, candidates) -> bool` — flags `gap > mean + 2*std_dev`.

## Pipeline role

Depends on `gap_candidate_set` and `gap_ordering` (C023, C024) though it imports `order_gaps`/`GapOrdering` without actually calling them anywhere in this crate's own functions (pure re-export pass-through). Consumed by `prime_gap_tests_integration` (C030) via `analyze_gaps`.

## Invariants / design notes

- `analyze_gaps`'s ordering by `gap_size` (not by frequency) is a side effect of using `BTreeMap` as the grouping structure — this is convenient but means callers who want frequency order must go through `most_common_gaps`.
- `gap_std_dev` uses the sample (Bessel-corrected, `n-1`) formula rather than population (`n`) std-dev — a deliberate-looking but unstated statistical choice; worth knowing if these numbers are compared against any external/Lean-side statistical expectation.
- `is_anomalous_gap` recomputes both `average_gap` and `gap_std_dev` from scratch (two full passes over `candidates`) every call — no memoized `GapMultiplicity`-level cache.

## Gaps / TODOs

- The `order_gaps`/`GapOrdering` re-export is dead weight in this crate — nothing here uses them; likely leftover from an earlier draft or meant for a caller convenience that never materialized.
- No test for `is_anomalous_gap` at all.
- No handling of empty `candidates` in `is_anomalous_gap` beyond what `average_gap`/`gap_std_dev` already do (both return 0.0), which makes the anomaly check `gap > 0` for an empty set — semantically odd if ever called that way.
