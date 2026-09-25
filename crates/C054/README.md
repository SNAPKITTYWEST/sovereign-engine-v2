# `derived_homology` (C054)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

Tor groups as homology of the tensored complex:
`Tor_n(M, N) = H_n(Tot(P ⊗ Q))` for free resolutions `P → M`, `Q → N`.
Homology is computed exactly (Smith normal form), so torsion in Tor is
found, e.g. `Tor_1(Z/4, Z/6) = Z/2`.

## Dependencies

- [C048 `homology_computation`](../C048/README.md)
- [C051 `tor_functor_definition`](../C051/README.md)
- [C052 `tensor_product_module`](../C052/README.md)
- [C053 `resolution_tensored`](../C053/README.md)

## Re-exports

- `homology_computation::HomologyGroup`
- `resolution_tensored::TensoredComplex`
- `tensor_product_module::TensorProductModule`
- `tor_functor_definition::{ProjectiveResolution, TorComputation, TorGroup, TorIndex}`

## Public API

| Item | Description |
|---|---|
| `fn compute_tor_from_resolution(complex: &TensoredComplex) -> Result<TorComputation, String>` | Tor groups of a tensored complex: `Tor_n = H_n(complex)` for every degree of the complex. |
| `fn resolution_data(r: &ProjectiveResolution) -> (Vec<usize>, Vec<Vec<Vec<i64>>>)` | Ranks and differential matrices of a resolution, in the layout used by `TensoredComplex::from_complexes`. |
| `fn tensor_resolutions(p: &ProjectiveResolution, q: &ProjectiveResolution) -> Result<TensoredComplex, String>` | `Tot(P ⊗ Q)` for two exact resolutions. |
| `fn tor_of(p: &ProjectiveResolution, q: &ProjectiveResolution) -> Result<TorComputation, String>` | `Tor_*(M, N)` for modules given by exact resolutions. |
| `fn verify_tor_computation(complex: &TensoredComplex, tor: &TorComputation) -> bool` | Recompute Tor from the complex and compare with `tor`. |
| `fn truncated_tor(complex: &TensoredComplex, max_degree: usize) -> Result<TorComputation, String>` | Tor groups of the complex in degrees below `max_degree`. |

## Tests

`cargo test -p derived_homology` runs 5 unit tests.
