# `homology_computation` (C048)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Computation of homology groups H_n = ker(d_n) / im(d_{n+1}).
Homology measures the "holes" in a chain complex: it's what survives d² = 0.

## Dependencies

- [C041 `chain_complex_shape`](../C041/README.md)
- [C043 `differential_operator`](../C043/README.md)
- [C044 `differential_squared_zero`](../C044/README.md)

## Re-exports

- `chain_complex_shape::integer_matrix`
- `chain_complex_shape::ChainComplexShape`
- `differential_operator::DifferentialOperator`

## Public API

| Item | Description |
|---|---|
| `struct HomologyGroup` | A homology group H_n at degree n. |
| `fn HomologyGroup::new(degree: i32, rank: usize) -> Self` | Create a new homology group. |
| `fn HomologyGroup::trivial(degree: i32) -> Self` | Create the trivial (zero) homology group. |
| `fn HomologyGroup::is_trivial(&self) -> bool` | Check if this homology group is trivial. |
| `fn HomologyGroup::add_torsion(&mut self, coeff: u64)` | Add torsion coefficient. |
| `fn HomologyGroup::betti_number(&self) -> usize` | Compute Betti number (rank of free part). |
| `fn HomologyGroup::to_string(&self) -> String` | Pretty-print the homology group. |
| `struct HomologyComputationResult` | Homology groups of a chain complex, one per degree of its shape. |
| `fn HomologyComputationResult::new() -> Self` | Create a new result. |
| `fn HomologyComputationResult::add_group(&mut self, group: HomologyGroup)` | Add a homology group. |
| `fn HomologyComputationResult::group_at(&self, degree: i32) -> Option<&HomologyGroup>` | Get the homology group at degree n. |
| `fn HomologyComputationResult::support_degrees(&self) -> Vec<i32>` | Get all degrees with nonzero homology. |
| `fn HomologyComputationResult::euler_characteristic(&self) -> i64` | Compute the Euler characteristic: sum of (-1)^n * rank(H_n). |
| `fn HomologyComputationResult::mark_verified(&mut self)` | Mark as verified. |
| `fn HomologyComputationResult::summary(&self) -> String` | Generate a summary report. |
| `struct HomologyComputer` | Homology computation engine. |
| `fn HomologyComputer::compute_at_degree(diff: &DifferentialOperator, degree: i32) -> Result<HomologyGroup, String>` | Compute `H_n = ker(d_n) / im(d_{n+1})` exactly over Z. |
| `fn HomologyComputer::compute_all(diff: &DifferentialOperator) -> Result<HomologyComputationResult, String>` | Compute homology for all degrees in the chain complex. |
| `fn HomologyComputer::compute_reduced_homology(diff: &DifferentialOperator, degree: i32) -> Result<HomologyGroup, String>` | Compute reduced homology (homology of the augmented complex). |

## Tests

`cargo test -p homology_computation` runs 11 unit tests.
