# `tor_functor_definition` (C051)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

Definition and properties of the Tor functor (derived tensor product).
Core homological algebra: Tor^i_R(M, N) for modules M, N over ring R.

## Dependencies

- [C041 `chain_complex_shape`](../C041/README.md)
- [C044 `differential_squared_zero`](../C044/README.md)
- [C046 `projective_resolution`](../C046/README.md)
- [C048 `homology_computation`](../C048/README.md)

## Re-exports

- `chain_complex_shape::integer_matrix`
- `homology_computation::{HomologyComputer, HomologyGroup}`
- `projective_resolution::{ ProjectiveModule, ProjectiveModuleHomomorphism, ProjectiveResolution, ResolutionHomology, }`

## Public API

| Item | Description |
|---|---|
| `struct TorIndex` | Tor functor computation index |
| `fn TorIndex::new(degree: usize) -> Self` | Create a Tor index for degree i |
| `fn TorIndex::is_zero(&self) -> bool` | Tor_0 is the base case (tensor product) |
| `fn TorIndex::is_higher(&self) -> bool` | Tor_i for i > 0 measures higher-order torsion |
| `struct TorGroup` | A Tor group: Tor_i(M, N) ≅ Z^rank ⊕ ⊕ (Z/order)^multiplicity. |
| `fn TorGroup::new(index: TorIndex, rank: usize) -> Self` | Create a new Tor group for index i with given rank |
| `fn TorGroup::from_invariants(index: TorIndex, rank: usize, torsion: &[u64]) -> Self` | Build from free rank and a list of torsion orders (orders ≤ 1 are trivial and skipped). |
| `fn TorGroup::from_homology(index: TorIndex, homology: &HomologyGroup) -> Self` | Build from a homology group. |
| `fn TorGroup::add_torsion(&mut self, order: u64, multiplicity: usize)` | Add `multiplicity` torsion summands of order `order`. |
| `fn TorGroup::torsion_orders(&self) -> Vec<u64>` | Order of each torsion generator, in generator order. |
| `fn TorGroup::is_trivial(&self) -> bool` | Is this Tor group trivial? |
| `fn TorGroup::num_generators(&self) -> usize` | Total number of generators (free + torsion) |
| `fn TorGroup::torsion_exponent(&self) -> u64` | Exponent of torsion (LCM of all torsion orders), saturating at `u64::MAX`. |
| `struct TorComputation` | Tor computation result for a pair of modules |
| `fn TorComputation::new() -> Self` | Create an empty Tor computation |
| `fn TorComputation::insert_tor(&mut self, degree: usize, group: TorGroup)` | Insert a Tor group at a given degree |
| `fn TorComputation::tor(&self, degree: usize) -> Option<&TorGroup>` | Get Tor_i (returns None if not computed) |
| `fn TorComputation::tor_mut(&mut self, degree: usize) -> Option<&mut TorGroup>` | Get mutable Tor_i |
| `fn TorComputation::max_degree(&self) -> Option<usize>` | Highest degree computed |
| `fn TorComputation::is_split_exact(&self) -> bool` | Check if all Tor_i for i > 0 are trivial (exact sequence) |

## Tests

`cargo test -p tor_functor_definition` runs 6 unit tests.
