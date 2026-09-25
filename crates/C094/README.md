# `prime_gap_correspondence` (C094)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

Correspondence between the gap tensor's candidate primes (Tier 0) and the
prime/gap engine (Tier 2):

* **candidate_gaps_match_engine**: the engine enumerates exactly the
  candidate primes up to the largest one, and the candidate gaps equal the
  engine's gaps as reported by the sieve, the gap candidate set and the
  prime-gap pairs;
* **gap_pairs_become_consonant_nodes**: every consecutive prime pair up to
  13, encoded as tensor nodes, passes every tensor invariant.

## Dependencies

- [C022 `prime_enumeration`](../C022/README.md)
- [C023 `gap_candidate_set`](../C023/README.md)
- [C029 `prime_gap_relationship`](../C029/README.md)
- [C091 `cross_layer_types`](../C091/README.md)

## Public API

| Item | Description |
|---|---|
| `fn check_candidate_gaps_match_engine_with(candidates: &[u32]) -> CorrespondenceReport` | Compare a candidate list with the engine. |
| `fn check_candidate_gaps_match_engine() -> CorrespondenceReport` | The real candidate check. |
| `fn check_gap_pairs_become_consonant_nodes_with(limit: u64) -> CorrespondenceReport` | Encode every consecutive prime pair up to `limit` as tensor nodes and check the tensor invariants. |
| `fn check_gap_pairs_become_consonant_nodes() -> CorrespondenceReport` | The real pair check (primes up to 13). |
| `fn check_engine_views_agree(limit: u64) -> CorrespondenceReport` | The three Tier 2 views of consecutive gaps agree up to `limit`. |

## Tests

`cargo test -p prime_gap_correspondence` runs 2 unit tests.
