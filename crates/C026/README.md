# gap_absolute_difference (C026)

Distance/difference metrics between gap sizes and between whole gap sequences.

## Public API

- Re-exports `GapCandidateSet` (from `gap_candidate_set`), `order_gaps` (from `gap_ordering`) — again unused within this crate.
- `gap_differences(candidates) -> Vec<i64>` — signed consecutive differences between successive gap sizes in the input order.
- `absolute_gap_differences(candidates) -> Vec<u64>` — same, absolute value.
- `gap_deviations(candidates, target: u64) -> Vec<i64>` — signed deviation of each gap from a target size.
- `gap_sequence_distance(gaps1: &[u64], gaps2: &[u64]) -> f64` — Euclidean (L2) distance between two gap sequences, zero-padding the shorter one.
- `sequence_roughness(candidates) -> f64` — std-dev (population, `n`, not sample) of `gap_differences`.

## Pipeline role

Depends on `gap_candidate_set`, `gap_ordering`. Consumed by `gap_constraint_satisfaction` (C027) via `gap_deviations`.

## Invariants / design notes

- `gap_differences`/`absolute_gap_differences` operate on the gaps **in the order given**, not in sorted or canonical prime order — if the caller passes an unordered `candidates` slice (e.g. from `order_gaps` with a non-size ordering), these "differences" are differences between whatever order the caller chose, which may not correspond to prime-index adjacency.
- `sequence_roughness` uses population std-dev (`/ diffs.len()`), while the sibling `gap_multiplicity::gap_std_dev` uses sample std-dev (`/ (len-1)`) — an inconsistency in statistical convention between two closely related crates in the same tier that a reviewer should reconcile or at least document.
- `gap_sequence_distance` zero-pads mismatched-length inputs rather than erroring or truncating — a deliberate choice, but it means comparing a short sequence to a long one always penalizes the difference in length as if the missing slots were literal `0` gaps.

## Gaps / TODOs

- `absolute_gap_differences`'s test (`test_absolute_gap_differences`) only asserts `d >= 0`, which is trivially true for the `u64` return type and doesn't actually verify correctness of the values — a placeholder-quality test.
- The population-vs-sample std-dev mismatch with C025 is worth flagging to whoever owns cross-crate statistical consistency.
- Unused `order_gaps` re-export, same as C025.
