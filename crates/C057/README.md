# `functoriality_of_tor` (C057)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

Functoriality of Tor in its first argument. A homomorphism `f: M → M'`,
given on generators by a matrix `F_0: P_0 → P'_0` between presentations,
is lifted to a chain map `F_k: P_k → P'_k` (solving `d'_k F_k = F_{k-1} d_k`
over Z), tensored with a resolution `Q` of `N`, and pushed to homology:
`f_*: Tor_n(M, N) → Tor_n(M', N)`.

Homology classes are expressed in explicit generators obtained from the
Smith decomposition of `d_{n+1}` in kernel coordinates, ordered torsion
first (ascending order) then free — the same order as `TorGroup`.

## Dependencies

- [C051 `tor_functor_definition`](../C051/README.md)
- [C054 `derived_homology`](../C054/README.md)

## Re-exports

- `derived_homology::verify_tor_computation`
- `tor_functor_definition::{ProjectiveResolution, TorComputation, TorGroup, TorIndex}`

## Public API

| Item | Description |
|---|---|
| `struct ModuleMap` | A homomorphism between modules on fixed generators: entry `(i, j)` is the coefficient of target generator `j` in the image of source generator `i`. |
| `fn ModuleMap::new(source_rank: usize, target_rank: usize) -> Self` | The zero map. |
| `fn ModuleMap::set(&mut self, i: usize, j: usize, val: i32)` | Set entry `(i, j)`; out-of-range indices are ignored. |
| `fn ModuleMap::get(&self, i: usize, j: usize) -> i32` | Entry `(i, j)` (0 out of range). |
| `fn ModuleMap::to_columns(&self) -> Vec<Vec<i64>>` | The map as a matrix acting on column vectors (`target_rank` rows, `source_rank` columns). |
| `fn ModuleMap::rank(&self) -> Option<usize>` | Rank of the map between free modules. |
| `fn ModuleMap::is_injective(&self) -> bool` | Injective as a map `Z^source → Z^target` (full column rank). |
| `fn ModuleMap::is_surjective(&self) -> bool` | Surjective as a map `Z^source → Z^target` (full row rank and a torsion-free cokernel). |
| `fn ModuleMap::is_zero(&self) -> bool` | Is every entry zero? |
| `fn compose_tor_maps(f: &ModuleMap, g: &ModuleMap) -> Option<ModuleMap>` | `g ∘ f` (apply `f`, then `g`). |
| `fn reduce_mod_target(map: &ModuleMap, target: &TorGroup) -> ModuleMap` | Reduce each column of `map` modulo the order of the corresponding generator of `target` (torsion generators first, then free). |
| `fn lift_chain_map(p: &ProjectiveResolution, target: &ProjectiveResolution, f0: &[Vec<i64>]) -> Result<Vec<Vec<Vec<i64>>>, String>` | Lift `f0: P_0 → P'_0` (rows `P'_0`, columns `P_0`) to a chain map between presentations/resolutions. |
| `struct InducedTorMap` | `f_*: Tor_n(M, N) → Tor_n(M', N)` in explicit generators. |
| `fn induced_tor_map(p: &ProjectiveResolution, p_prime: &ProjectiveResolution, q: &ProjectiveResolution, f0: &[Vec<i64>], degree: usize) -> Result<InducedTorMap, String>` | Compute `f_*` on `Tor_degree(M, N)` for `f: M → M'` given on generators by `f0` (rows `P'_0`, columns `P_0`). |

## Tests

`cargo test -p functoriality_of_tor` runs 7 unit tests.
