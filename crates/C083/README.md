# `prime_state_binding` (C083)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

Binds a run of the prime/gap engine (Tier 2) to the runtime snapshot
store: the primes up to a limit are enumerated, encoded as tensor nodes
and recorded. Claims about the run (all values prime, gaps consistent,
orderings are permutations, encoding faithful) are re-checkable.

## Dependencies

- [C021 `prime_predicate`](../C021/README.md)
- [C023 `gap_candidate_set`](../C023/README.md)
- [C024 `gap_ordering`](../C024/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)

## Public API

| Item | Description |
|---|---|
| `enum PrimeRunError` | Why a run could not be bound. |
| `struct PrimeStateBinding` | A recorded run of the prime engine. |
| `fn PrimeStateBinding::run(name: impl Into<String>, limit: u64) -> Result<Self, PrimeRunError>` | Enumerate primes up to `limit` and record them. |
| `fn PrimeStateBinding::primes(&self) -> &[u64]` | Primes enumerated. |
| `fn PrimeStateBinding::candidates(&self) -> &[(u64, u64, u64)]` | Consecutive-prime gaps `(p, q, q − p)`. |
| `fn PrimeStateBinding::limit(&self) -> u64` | The limit. |
| `fn PrimeStateBinding::store(&self) -> &SnapshotStore` | Recorded history. |

## Tests

`cargo test -p prime_state_binding` runs 3 unit tests.
