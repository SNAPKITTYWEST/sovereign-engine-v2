# `tensor_homology_correspondence` (C095)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

Correspondence between the dissonance invariant of a gap tensor (Tier 0)
and homology (Tier 4). The *consonance path complex* of a tensor has one
vertex per non-nil node (in order) and an edge between consecutive
non-nil nodes whose primes differ by at most the gap bound, with
`d(edge) = v_{k+1} − v_k`. It is a disjoint union of paths, so

* `rank H₀` = number of path components = `1 + #dissonances` (0 if every
  node is Nil), and
* `H₁ = 0`.

 verifies this with the
Smith-normal-form homology of Tier 4 over a family of tensors.

## Dependencies

- [C042 `chain_complex_types`](../C042/README.md)
- [C048 `homology_computation`](../C048/README.md)
- [C091 `cross_layer_types`](../C091/README.md)

## Public API

| Item | Description |
|---|---|
| `fn path_complex(tensor: &GapTensor, max_gap: u32) -> DifferentialOperator` | The consonance path complex of `tensor` for gap bound `max_gap`. |
| `fn check_dissonance_equals_path_components_with(family: &[GapTensor], max_gap: u32) -> CorrespondenceReport` | Check `rank H₀ = 1 + #dissonances` and `H₁ = 0` for every tensor, using gap bound `max_gap` for the complex (the invariant always uses `SIGMA_GAP_MAX`). |
| `fn check_dissonance_equals_path_components(family: &[GapTensor]) -> CorrespondenceReport` | The real check (gap bound `SIGMA_GAP_MAX`). |

## Tests

`cargo test -p tensor_homology_correspondence` runs 3 unit tests.
