# `prime_gap_relationship` (C029)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Relate prime numbers to their gaps and establish relationships.

## Dependencies

- [C021 `prime_predicate`](../C021/README.md)
- [C022 `prime_enumeration`](../C022/README.md)
- [C023 `gap_candidate_set`](../C023/README.md)

## Re-exports

- `prime_predicate::is_prime`
- `prime_enumeration::{primes_up_to, nth_prime}`
- `gap_candidate_set::GapCandidateSet`

## Public API

| Item | Description |
|---|---|
| `struct PrimeGapPair` | Information about a prime and its surrounding gap. |
| `fn PrimeGapPair::is_first_occurrence(&self, pairs: &[PrimeGapPair]) -> bool` | Is this the first pair (smallest prime) in `pairs` with this gap? |
| `fn PrimeGapPair::normalized_gap(&self) -> f64` | Gap normalized by `ln(prime)`, the average gap size near `prime`. |
| `fn prime_gap_pairs(limit: u64) -> Vec<PrimeGapPair>` | Construct prime-gap relationships for all primes up to limit. |
| `fn primes_with_gap(pairs: &[PrimeGapPair], gap_size: u64) -> Vec<u64>` | Find all primes with a specific gap size. |
| `fn largest_gap_in_range(pairs: &[PrimeGapPair], start: u64, end: u64) -> Option<PrimeGapPair>` | Find the largest gap in a range. |
| `fn maximal_gaps(pairs: &[PrimeGapPair]) -> Vec<PrimeGapPair>` | Get the maximal gap (first gap of each size). |
| `fn gap_ratios(pairs: &[PrimeGapPair]) -> Vec<f64>` | Compute the ratio of gap to log(prime). |

## Tests

`cargo test -p prime_gap_relationship` runs 7 unit tests.
