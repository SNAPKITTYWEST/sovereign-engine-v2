# `prime_enumeration` (C022)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Prime number enumeration and sequence generation.

## Dependencies

- [C021 `prime_predicate`](../C021/README.md)

## Re-exports

- `prime_predicate::{is_prime, is_prime_candidate}`

## Public API

| Item | Description |
|---|---|
| `fn primes_up_to(limit: u64) -> Vec<u64>` | Generate all primes up to a given limit using Sieve of Eratosthenes. |
| `fn nth_prime(n: usize) -> Option<u64>` | Get the n-th prime (0-indexed). |
| `fn prime_count(limit: u64) -> usize` | Count the number of primes up to n (Prime Counting Function π(n)). |

## Tests

`cargo test -p prime_enumeration` runs 4 unit tests.
