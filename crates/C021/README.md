# `prime_predicate` (C021)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Core prime number predicate and basic primality testing.
Foundation for Tier 2 prime/gap engine.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)

## Public API

| Item | Description |
|---|---|
| `fn is_prime(n: u64) -> bool` | Check if a number is prime using trial division. |
| `fn is_prime_candidate(n: u64) -> bool` | Exact primality by 6k ± 1 trial division: after ruling out 2 and 3 it only tries divisors of the form 6k ± 1 up to √n. |
| `fn try_prime_to_tensor_node(prime: u64) -> Option<GapTensorNode>` | A node for `prime` (multiplicity 1, weight 1.0), or `None` if the prime does not fit the node's 32-bit prime field. |
| `fn prime_to_tensor_node(prime: u64) -> GapTensorNode` | Create a GapTensorNode representing a prime in the candidate set. |

## Tests

`cargo test -p prime_predicate` runs 5 unit tests.
