# `tor_spectrum_correspondence` (C096)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

Correspondence between Tor (Tier 5) and the prime spectrum (Tier 6):
the highest non-vanishing Tor degree of any pair of cyclic groups is at
most the Krull dimension of Spec(ℤ) (computed on a finite prefix). This
is the finite, checkable shadow of "ℤ is regular of dimension 1, so its
global dimension — which bounds Tor dimension — equals its Krull
dimension".

## Dependencies

- [C054 `derived_homology`](../C054/README.md)
- [C058 `tor_invariants_computation`](../C058/README.md)
- [C068 `dimension_upper_bounds`](../C068/README.md)
- [C091 `cross_layer_types`](../C091/README.md)

## Re-exports

- `dimension_upper_bounds::KrullDim`

## Public API

| Item | Description |
|---|---|
| `fn spec_z_prefix_dimension(bound: u64) -> KrullDim` | Krull dimension of `{(0)} ∪ {(p) : p ≤ bound}`. |
| `fn check_tor_dimension_bounded_with(max_order: i64, krull: KrullDim) -> CorrespondenceReport` | For `0 ≤ m, n ≤ max_order`, check that the Tor dimension of `(ℤ/m, ℤ/n)` satisfies the upper bound `krull`. |
| `fn check_tor_dimension_bounded_by_krull(max_order: i64) -> CorrespondenceReport` | The real check: bound by the dimension of the Spec(ℤ) prefix up to `max_order` (at least up to 2). |

## Tests

`cargo test -p tor_spectrum_correspondence` runs 2 unit tests.
