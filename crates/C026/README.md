# `gap_absolute_difference` (C026)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Compute differences and distance metrics for prime gaps.

## Dependencies

- [C023 `gap_candidate_set`](../C023/README.md)
- [C024 `gap_ordering`](../C024/README.md)

## Re-exports

- `gap_candidate_set::GapCandidateSet`
- `gap_ordering::order_gaps`

## Public API

| Item | Description |
|---|---|
| `fn gap_differences(candidates: &[(u64, u64, u64)]) -> Vec<i64>` | Compute gap differences (consecutive gaps). |
| `fn absolute_gap_differences(candidates: &[(u64, u64, u64)]) -> Vec<u64>` | Compute absolute differences between gap sizes. |
| `fn gap_deviations(candidates: &[(u64, u64, u64)], target: u64) -> Vec<i64>` | Compute deviations from a target gap size. |
| `fn gap_sequence_distance(gaps1: &[u64], gaps2: &[u64]) -> f64` | Compute the L2 distance between two sequences of gaps. |
| `fn sequence_roughness(candidates: &[(u64, u64, u64)]) -> f64` | "Roughness" of a gap sequence: the population standard deviation (divide by n) of consecutive gap differences. |

## Tests

`cargo test -p gap_absolute_difference` runs 5 unit tests.
