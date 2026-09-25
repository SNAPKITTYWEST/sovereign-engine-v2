# `spectrum_definition` (C064)

Tier 6 — Krull dimension. *Generated from the crate source; regenerate after API changes.*

Prime spectrum Spec(R) — set of all prime ideals.

## Dependencies

- [C061 `ideal_interface`](../C061/README.md)
- [C062 `prime_ideal_predicate`](../C062/README.md)

## Re-exports

- `ideal_interface::Ideal`
- `prime_ideal_predicate::{is_prime_ideal, PrimePoint}`

## Public API

| Item | Description |
|---|---|
| `struct Spectrum` | The prime spectrum of a ring |
| `fn Spectrum::empty() -> Self` | Create an empty spectrum |
| `fn Spectrum::new(primes: Vec<u64>) -> Self` | Create spectrum from a list of primes |
| `fn Spectrum::add_prime(&mut self, p: u64)` | Add a prime to the spectrum |
| `fn Spectrum::len(&self) -> usize` | Number of primes in the spectrum |
| `fn Spectrum::is_empty(&self) -> bool` | Check if spectrum is empty |
| `fn Spectrum::as_ideals(&self) -> Vec<Ideal>` | Get all primes as ideals |
| `fn Spectrum::contains_prime(&self, p: u64) -> bool` | Check if spectrum contains a prime |
| `fn Spectrum::specializes(&self, p: u64, q: u64) -> bool` | Specialization: `(p) ⊆ (q)` for two points of the spectrum. |
| `fn Spectrum::minimal_primes(&self) -> Vec<u64>` | Minimal primes: no other point of the spectrum is strictly contained in them (in Z: `(0)` if present). |
| `fn Spectrum::maximal_primes(&self) -> Vec<u64>` | Maximal primes: no other point of the spectrum strictly contains them (in Z: the non-zero primes). |
| `fn principal_contained(a: u64, b: u64) -> bool` | `(a) ⊆ (b)` in Z: `b \| a`, where `(0)` is contained in every ideal and only `(0)` is contained in `(0)`. |

## Tests

`cargo test -p spectrum_definition` runs 7 unit tests.
