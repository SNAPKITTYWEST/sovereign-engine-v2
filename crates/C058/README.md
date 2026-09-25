# `tor_invariants_computation` (C058)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

Compute invariants from Tor: Betti numbers, torsion complexity, etc.

## Dependencies

- [C042 `chain_complex_types`](../C042/README.md)
- [C051 `tor_functor_definition`](../C051/README.md)
- [C054 `derived_homology`](../C054/README.md)

## Re-exports

- `tor_functor_definition::{TorGroup, TorComputation}`
- `derived_homology::verify_tor_computation`

## Public API

| Item | Description |
|---|---|
| `struct BettiNumbers` | Betti numbers extracted from Tor computation |
| `fn BettiNumbers::new() -> Self` | Create empty Betti numbers |
| `fn BettiNumbers::add(&mut self, degree: usize, rank: usize)` | Add a Betti number |
| `fn BettiNumbers::beta(&self, degree: usize) -> usize` | Get Betti number at degree |
| `fn BettiNumbers::total_rank(&self) -> usize` | Total rank (sum of all Betti numbers) |
| `fn BettiNumbers::regularity(&self) -> Option<usize>` | Highest degree with a non-zero Betti number. |
| `fn compute_betti_numbers(tor: &TorComputation) -> BettiNumbers` | Compute Betti numbers from Tor computation |
| `fn torsion_complexity(tor: &TorComputation) -> u64` | Torsion complexity: sum of the torsion exponents of every Tor group that has torsion (saturating). |
| `fn is_free_resolution(tor: &TorComputation) -> bool` | True iff every computed Tor group is torsion-free. |
| `fn global_dimension(tor: &TorComputation) -> Option<usize>` | Tor dimension of the pair: the highest degree with a non-trivial Tor group (`None` if every group is trivial). |

## Tests

`cargo test -p tor_invariants_computation` runs 5 unit tests.
