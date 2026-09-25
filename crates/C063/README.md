# `maximal_ideal_predicate` (C063)

Tier 6 — Krull dimension. *Generated from the crate source; regenerate after API changes.*

Test whether an ideal is maximal.

## Dependencies

- [C061 `ideal_interface`](../C061/README.md)
- [C062 `prime_ideal_predicate`](../C062/README.md)

## Re-exports

- `ideal_interface::Ideal`
- `prime_ideal_predicate::{is_prime_ideal, PrimePoint}`

## Public API

| Item | Description |
|---|---|
| `fn is_maximal_ideal(ideal: &Ideal) -> bool` | Check if an ideal is maximal An ideal M is maximal iff R/M is a field Equivalently: M is maximal if it is prime and contains no other primes |
| `enum IdealComparison` | Compare two ideals by containment |
| `fn compare_ideals(left: &Ideal, right: &Ideal) -> IdealComparison` | Compare two ideals |
| `fn is_strictly_between(lower: &Ideal, candidate: &Ideal, upper: &Ideal) -> bool` | `lower ⊊ candidate ⊊ upper` as ideals (compared by their elements, not by their generator lists). |

## Tests

`cargo test -p maximal_ideal_predicate` runs 7 unit tests.
