# `tor_zero_structure` (C055)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

`Tor_0(M, N) = M ⊗ N`. This crate computes `M ⊗ N` directly from
presentations and cross-checks it against `Tor_0` computed as homology of
the tensored resolution — two independent computations that must agree.

## Dependencies

- [C051 `tor_functor_definition`](../C051/README.md)
- [C052 `tensor_product_module`](../C052/README.md)
- [C054 `derived_homology`](../C054/README.md)

## Re-exports

- `derived_homology::verify_tor_computation`
- `tensor_product_module::TensorProductModule`
- `tor_functor_definition::{ProjectiveResolution, TorGroup, TorIndex}`

## Public API

| Item | Description |
|---|---|
| `struct Tor0Properties` | Summary of `Tor_0`. |
| `fn Tor0Properties::new(rank: usize, has_torsion: bool) -> Self` | Create Tor_0 properties |
| `fn Tor0Properties::from_group(group: &TorGroup) -> Self` | Properties of a computed `Tor_0` group. |
| `fn Tor0Properties::is_trivial(&self) -> bool` | Check if Tor_0 is the trivial group |
| `fn analyze_tor_zero(module: &TensorProductModule) -> Result<TorGroup, String>` | `Tor_0(M, N) = M ⊗ N` from a tensor product module, respecting its relations. |
| `fn presentation(r: &ProjectiveResolution) -> (usize, Vec<Vec<i64>>, usize)` | Presentation `(generators, relation matrix, relation count)` of the module a resolution resolves. |
| `fn tensor_of_presentations(p: &ProjectiveResolution, q: &ProjectiveResolution) -> Result<TensorProductModule, String>` | `M ⊗ N` built from the presentations of the resolved modules. |
| `fn verify_tor_zero_universal_property(p: &ProjectiveResolution, q: &ProjectiveResolution) -> Result<bool, String>` | Check the defining property `Tor_0(M, N) ≅ M ⊗ N`: `Tor_0` computed as homology of `Tot(P ⊗ Q)` must equal `M ⊗ N` computed from presentations. |
| `fn compute_tor_zero_from_ranks(rank_m: usize, rank_n: usize) -> TorGroup` | `Tor_0(Z^m, Z^n) = Z^{mn}` for free modules. |

## Tests

`cargo test -p tor_zero_structure` runs 4 unit tests.
