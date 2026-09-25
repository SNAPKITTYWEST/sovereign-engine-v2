# `gap_multiplicity` (C025)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Analyze frequency and multiplicity of prime gaps.

## Dependencies

- [C023 `gap_candidate_set`](../C023/README.md)
- [C024 `gap_ordering`](../C024/README.md)

## Re-exports

- `gap_candidate_set::GapCandidateSet`
- `gap_ordering::{order_gaps, GapOrdering}`

## Public API

| Item | Description |
|---|---|
| `struct GapMultiplicity` | Multiplicity information for a gap size. |
| `fn analyze_gaps(candidates: &[(u64, u64, u64)]) -> Vec<GapMultiplicity>` | Analyze gap multiplicity in a candidate set. |
| `fn most_common_gaps(candidates: &[(u64, u64, u64)], k: usize) -> Vec<GapMultiplicity>` | Get the most common gap sizes. |
| `fn average_gap(candidates: &[(u64, u64, u64)]) -> f64` | Calculate average gap size. |
| `fn gap_std_dev(candidates: &[(u64, u64, u64)]) -> f64` | Sample standard deviation of gap sizes (divide by n − 1; 0 for fewer than two gaps). |
| `fn is_anomalous_gap(gap: u64, candidates: &[(u64, u64, u64)]) -> bool` | Check if a gap is anomalous (> mean + 2*std_dev). |

## Tests

`cargo test -p gap_multiplicity` runs 4 unit tests.
