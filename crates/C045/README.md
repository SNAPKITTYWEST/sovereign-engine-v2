# `projective_module_definition` (C045)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Projective modules over principal ideal domains and free modules.
A projective module P is one that has the "lifting property": if M -> N is surjective
and f: P -> N, then there exists g: P -> M with f = (M -> N) ∘ g.

Over a PID, projective modules are precisely the free modules.

## Dependencies

- [C041 `chain_complex_shape`](../C041/README.md)
- [C042 `chain_complex_types`](../C042/README.md)

## Public API

| Item | Description |
|---|---|
| `struct ProjectiveModule` | A projective module P, represented as a free module (since we work over a PID). |
| `fn ProjectiveModule::new(rank: usize, degree: i32) -> Self` | Create a new projective module of given rank at given degree. |
| `fn ProjectiveModule::with_generators(rank: usize, degree: i32, generators: Vec<String>) -> Self` | Create a projective module with custom generator names. |
| `fn ProjectiveModule::generator_name(&self, idx: usize) -> Option<&str>` | Get the name of a generator. |
| `fn ProjectiveModule::is_free(&self) -> bool` | Check if this module is free (always true for projective modules over PID). |
| `fn ProjectiveModule::len(&self) -> usize` | Get the rank of this module. |
| `fn ProjectiveModule::is_empty(&self) -> bool` | Check if this module is trivial (rank 0). |
| `struct ProjectiveModuleHomomorphism` | A homomorphism φ: P -> Q between projective modules. |
| `fn ProjectiveModuleHomomorphism::new(source: ProjectiveModule, target: ProjectiveModule, matrix: Vec<Vec<i64>>) -> Self` | Create a new homomorphism from a matrix. |
| `fn ProjectiveModuleHomomorphism::entry(&self, i: usize, j: usize) -> i64` | Get the matrix entry at (i, j). |
| `fn ProjectiveModuleHomomorphism::apply(&self, elem: &ChainElement) -> ChainElement` | Apply the homomorphism to an element. |
| `fn ProjectiveModuleHomomorphism::compose(&self, other: &ProjectiveModuleHomomorphism) -> ProjectiveModuleHomomorphism` | Compose this homomorphism with another (self: P -> Q, other: Q -> R). |
| `fn ProjectiveModuleHomomorphism::is_zero(&self) -> bool` | Check if this is the zero homomorphism. |
| `fn ProjectiveModuleHomomorphism::is_identity(&self) -> bool` | Check if this is the identity homomorphism. |
| `fn ProjectiveModuleHomomorphism::matrix(&self) -> &[Vec<i64>]` | The matrix (target_rank rows × source_rank columns). |
| `fn ProjectiveModuleHomomorphism::smith_form(&self) -> Result<SmithForm, MatrixError>` | Smith normal form of the matrix: rank, invariant factors (torsion of the cokernel) and a Z-basis of the kernel. |
| `fn ProjectiveModuleHomomorphism::try_rank(&self) -> Result<usize, MatrixError>` | Rank of the matrix, or an error if exact arithmetic overflows. |
| `fn ProjectiveModuleHomomorphism::rank(&self) -> usize` | Rank of the matrix. |
| `struct FreeResolution` | A free resolution of a projective module is a chain complex of projective modules and their homomorphisms. |
| `fn FreeResolution::new() -> Self` | Create a new free resolution. |
| `fn FreeResolution::add_module(&mut self, module: ProjectiveModule)` | Add a module to the resolution. |
| `fn FreeResolution::add_differential(&mut self, hom: ProjectiveModuleHomomorphism)` | Add a differential between the last two modules. |
| `fn FreeResolution::module_at(&self, i: usize) -> Option<&ProjectiveModule>` | Get the module at index i. |
| `fn FreeResolution::differential_at(&self, i: usize) -> Option<&ProjectiveModuleHomomorphism>` | Get the differential d_i: P_i -> P_{i-1}. |
| `fn FreeResolution::len(&self) -> usize` | Number of modules in the resolution. |
| `fn FreeResolution::is_empty(&self) -> bool` | Check if empty. |

## Tests

`cargo test -p projective_module_definition` runs 9 unit tests.
