# `prime_ideal_predicate` (C062)

Tier 6 — Krull dimension. *Generated from the crate source; regenerate after API changes.*

Test whether an ideal is prime.

## Dependencies

- [C061 `ideal_interface`](../C061/README.md)

## Re-exports

- `ideal_interface::Ideal`

## Public API

| Item | Description |
|---|---|
| `fn is_prime_ideal(ideal: &Ideal) -> bool` | Is the ideal prime? |
| `fn is_weakly_prime(ideal: &Ideal) -> bool` | Check if an ideal is weakly prime (a weaker condition) |
| `fn to_prime_point(ideal: &Ideal) -> Option<PrimePoint>` | Convert ideal to prime spectrum point (if prime). |
| `struct PrimePoint` | A point in the prime spectrum |
| `fn PrimePoint::contains(&self, other: &PrimePoint) -> bool` | Check if this prime contains another prime |

## Tests

`cargo test -p prime_ideal_predicate` runs 6 unit tests.
