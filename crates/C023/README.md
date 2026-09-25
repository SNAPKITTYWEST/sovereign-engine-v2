# `gap_candidate_set` (C023)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Manage candidate sets of primes for gap analysis.

## Dependencies

- [C022 `prime_enumeration`](../C022/README.md)

## Re-exports

- `prime_enumeration::{nth_prime, primes_up_to}`

## Public API

| Item | Description |
|---|---|
| `struct GapCandidateSet` | A set of candidate gap positions. |
| `fn GapCandidateSet::new(primes: Vec<u64>) -> Self` | Create a new candidate set from a list of primes (in any order; duplicates are dropped). |
| `fn GapCandidateSet::from_limit(limit: u64) -> Self` | Create candidate set from primes up to limit. |
| `fn GapCandidateSet::gaps(&self) -> Vec<u64>` | Get all gaps between consecutive primes. |
| `fn GapCandidateSet::contains_gap(&self, gap_size: u64) -> bool` | Check if a gap size appears in the set. |
| `fn GapCandidateSet::candidates_with_gap(self, min_size: u64) -> Vec<(u64, u64, u64)>` | Get candidates with gap >= min_size. |
| `fn GapCandidateSet::gap_count(&self) -> usize` | Count distinct gap sizes. |
| `fn GapCandidateSet::min_gap(&self) -> u64` | Get minimum gap size (0 when there are fewer than two primes). |
| `fn GapCandidateSet::max_gap(&self) -> u64` | Get maximum gap size (0 when there are fewer than two primes). |
| `fn GapCandidateSet::len(&self) -> usize` | Number of primes in the set. |
| `fn GapCandidateSet::is_empty(&self) -> bool` | Check if set is empty. |

## Tests

`cargo test -p gap_candidate_set` runs 6 unit tests.
