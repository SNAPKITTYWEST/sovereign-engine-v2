# `gap_ordering` (C024)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Ordering and sorting operations for prime gaps.

## Dependencies

- [C023 `gap_candidate_set`](../C023/README.md)

## Re-exports

- `gap_candidate_set::{GapCandidateSet}`

## Public API

| Item | Description |
|---|---|
| `enum GapOrdering` | Different orderings for gaps. |
| `fn order_gaps(candidates: Vec<(u64, u64, u64)>, ordering: GapOrdering) -> Vec<(u64, u64, u64)>` | Order a set of gap candidates. |
| `fn top_k_gaps(candidates: Vec<(u64, u64, u64)>, k: usize) -> Vec<(u64, u64, u64)>` | Get the k-largest gaps. |
| `fn gaps_in_range(candidates: Vec<(u64, u64, u64)>, min: u64, max: u64) -> Vec<(u64, u64, u64)>` | Get gaps in a specific range. |
| `fn gap_histogram(candidates: &[(u64, u64, u64)]) -> std::collections::BTreeMap<u64, usize>` | Create a histogram of gap sizes. |

## Tests

`cargo test -p gap_ordering` runs 4 unit tests.
