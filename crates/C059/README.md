# `tor_chain_complex_interface` (C059)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

Interface between Tor computation and chain complex objects.

## Dependencies

- [C046 `projective_resolution`](../C046/README.md)
- [C051 `tor_functor_definition`](../C051/README.md)
- [C054 `derived_homology`](../C054/README.md)
- [C058 `tor_invariants_computation`](../C058/README.md)

## Re-exports

- `projective_resolution::ProjectiveResolution`
- `tor_functor_definition::TorComputation`
- `derived_homology::compute_tor_from_resolution`
- `tor_invariants_computation::{BettiNumbers, compute_betti_numbers}`

## Public API

| Item | Description |
|---|---|
| `struct TorChainComplexData` | Wrapper for a complete Tor-computed chain complex |
| `fn TorChainComplexData::from_resolution(resolution: ProjectiveResolution) -> Result<Self, String>` | `Tor_*(M, Z)` for the module `M` resolved by `resolution` (`Tor_0 = M`, higher groups vanish). |
| `fn TorChainComplexData::from_resolutions(resolution: ProjectiveResolution, coefficients: &ProjectiveResolution) -> Result<Self, String>` | `Tor_*(M, N)` for `M` resolved by `resolution` and `N` resolved by `coefficients`. |
| `fn TorChainComplexData::update_tor(&mut self, tor: TorComputation)` | Update Tor computation |
| `fn TorChainComplexData::as_complex_data(&self) -> ChainComplexInterface` | Summary: number of resolution modules, total Betti rank, and the highest degree with free rank. |
| `struct ChainComplexInterface` | Summary of a Tor computation attached to a resolution. |
| `fn ChainComplexInterface::is_bounded(&self) -> bool` | Check if complex is bounded |
| `fn ChainComplexInterface::is_acyclic(&self) -> bool` | Check if complex is acyclic (only Tor_0) |
| `fn tor_to_complex_data(tor: &TorComputation, resolution_length: usize) -> ChainComplexInterface` | Convert Tor computation to standard chain complex data |

## Tests

`cargo test -p tor_chain_complex_interface` runs 4 unit tests.
