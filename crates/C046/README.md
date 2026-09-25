# `projective_resolution` (C046)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Projective resolutions of modules over Z. A projective resolution of a
module M is an exact sequence

`… → P_2 → P_1 → P_0 → M → 0`

where each `P_i` is projective (over a PID: free of finite rank).

Conventions:

* `modules[i]` is `P_i`.
* `differentials[k]` is `d_{k+1}: P_{k+1} → P_k` (source `modules[k+1]`,
  target `modules[k]`).
* If an augmentation `ε: P_0 → M` is set, `M` is the free target of `ε`.
  If no augmentation is set, the resolution is a *presentation*: `M` is
  defined as `coker(d_1)` and `ε` is the quotient map, so the sequence is
  exact at `P_0` by construction.

Exactness is decided exactly with Smith normal form: the homology at
`P_i` has free rank `rank P_i − rank(out) − rank(d_{i+1})` and torsion
given by the non-unit invariant factors of `d_{i+1}`.

## Dependencies

- [C041 `chain_complex_shape`](../C041/README.md)
- [C042 `chain_complex_types`](../C042/README.md)
- [C044 `differential_squared_zero`](../C044/README.md)
- [C045 `projective_module_definition`](../C045/README.md)

## Re-exports

- `chain_complex_shape::integer_matrix as matrix_ops`
- `projective_module_definition::{ProjectiveModule, ProjectiveModuleHomomorphism}`

## Public API

| Item | Description |
|---|---|
| `struct ResolutionHomology` | Homology of the augmented complex at one position: `Z^free_rank ⊕ ⊕ Z/t` for `t` in `torsion`. |
| `fn ResolutionHomology::is_zero(&self) -> bool` | Zero homology (exactness). |
| `struct ProjectiveResolution` | A projective resolution of a module M. |
| `fn ProjectiveResolution::new() -> Self` | An empty resolution. |
| `fn ProjectiveResolution::add_module(&mut self, module: ProjectiveModule)` | Append `P_{len}`. |
| `fn ProjectiveResolution::add_differential(&mut self, diff: ProjectiveModuleHomomorphism)` | Append the next differential `d_{k+1}: P_{k+1} → P_k` (k = number of differentials already added). |
| `fn ProjectiveResolution::set_augmentation(&mut self, aug: ProjectiveModuleHomomorphism)` | Set the augmentation `ε: P_0 → M`. |
| `fn ProjectiveResolution::module_at(&self, i: usize) -> Option<&ProjectiveModule>` | `P_i`. |
| `fn ProjectiveResolution::differential_at(&self, k: usize) -> Option<&ProjectiveModuleHomomorphism>` | `differentials[k]`, i.e. |
| `fn ProjectiveResolution::d(&self, i: usize) -> Option<&ProjectiveModuleHomomorphism>` | `d_i: P_i → P_{i-1}` for `i ≥ 1`. |
| `fn ProjectiveResolution::differentials_len(&self) -> usize` | Number of differentials. |
| `fn ProjectiveResolution::len(&self) -> usize` | Number of modules. |
| `fn ProjectiveResolution::is_empty(&self) -> bool` | No modules? |
| `fn ProjectiveResolution::rank_at(&self, i: usize) -> usize` | Rank of `P_i` (0 past the end). |
| `fn ProjectiveResolution::check_structure(&self) -> Result<(), String>` | Check that there is one differential per adjacent pair of modules and that every map's source and target ranks match its modules. |
| `fn ProjectiveResolution::composition_is_zero(&self, i: usize) -> Result<bool, String>` | Is the composite of the map out of `P_i` with `d_{i+1}` zero? |
| `fn ProjectiveResolution::homology_at(&self, i: usize) -> Result<ResolutionHomology, String>` | Homology of the augmented complex at `P_i`. |
| `fn ProjectiveResolution::is_exact_at(&self, i: usize) -> bool` | Is the augmented complex exact at `P_i`? |
| `fn ProjectiveResolution::augmentation_is_surjective(&self) -> Result<bool, String>` | Is the augmentation surjective? |
| `fn ProjectiveResolution::resolved_module(&self) -> Result<ResolutionHomology, String>` | The module being resolved: `coker(d_1)` for a presentation, or the free target of the augmentation. |
| `fn ProjectiveResolution::kernel_at(&self, i: usize) -> Vec<ChainElement>` | A Z-basis of the kernel of the map leaving `P_i`: `d_i` for `i ≥ 1`, `ε` for `i = 0` (empty when no augmentation is set). |
| `fn ProjectiveResolution::image_at(&self, i: usize) -> Vec<ChainElement>` | Images in `P_i` of the generators of `P_{i+1}` under `d_{i+1}`. |
| `fn ProjectiveResolution::verify_exactness(&mut self) -> bool` | Check exactness everywhere and surjectivity of the augmentation, and record the result. |
| `fn ProjectiveResolution::mark_exact(&mut self, exact: bool)` | Record exactness established elsewhere. |
| `fn ProjectiveResolution::is_marked_exact(&self) -> bool` | Recorded exactness. |
| `fn ProjectiveResolution::free_of_rank_one() -> Self` | Resolution of the free module Z: `0 → Z --id--> Z → 0`. |
| `fn ProjectiveResolution::cyclic_resolution(n: i64) -> Self` | Presentation of the cyclic group Z/n: `0 → Z --·n--> Z → Z/n → 0`. |
| `fn ProjectiveResolution::to_chain_shape(&self) -> ChainComplexShape` | The chain complex shape, with `P_i` at degree `-i`. |
| `fn ProjectiveResolution::summary(&self) -> String` | One-line summary. |

## Tests

`cargo test -p projective_resolution` runs 10 unit tests.
