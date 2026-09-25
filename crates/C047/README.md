# `exactness_predicate` (C047)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Exactness checking for chain complexes and sequences.
A sequence is exact at a point if kernel = image.
A complex is exact everywhere if homology is zero everywhere.

## Dependencies

- [C041 `chain_complex_shape`](../C041/README.md)
- [C043 `differential_operator`](../C043/README.md)
- [C044 `differential_squared_zero`](../C044/README.md)
- [C048 `homology_computation`](../C048/README.md)

## Public API

| Item | Description |
|---|---|
| `struct ExactnessCertificate` | A certificate that a sequence is exact at a given degree. |
| `fn ExactnessCertificate::new(degree: i32, kernel_dim: usize, image_dim: usize) -> Self` | Certificate from ranks, assuming a torsion-free quotient. |
| `fn ExactnessCertificate::from_ranks(degree: i32, kernel_dim: usize, image_dim: usize, torsion_free: bool) -> Self` | Certificate from ranks and the torsion status of the quotient. |
| `fn ExactnessCertificate::failed(degree: i32) -> Self` | Certificate for a degree where the check could not be carried out (d² ≠ 0 or arithmetic overflow): never exact. |
| `fn ExactnessCertificate::summary(&self) -> String` | Pretty-print the certificate. |
| `struct ExactnessPredicateChecker` | Global exactness predicate: checks if a chain complex is exact everywhere. |
| `fn ExactnessPredicateChecker::check_at_degree(diff: &DifferentialOperator, degree: i32) -> ExactnessCertificate` | Check exactness at a specific degree. |
| `fn ExactnessPredicateChecker::check_global_exactness(diff: &DifferentialOperator) -> GlobalExactnessProof` | Check global exactness: the complex is exact everywhere. |
| `fn ExactnessPredicateChecker::check_from_homology(result: &HomologyComputationResult) -> bool` | Check if the homology computation result shows exactness. |
| `struct GlobalExactnessProof` | Global proof that a sequence is exact (acyclic). |
| `fn GlobalExactnessProof::cert_at(&self, degree: i32) -> Option<&ExactnessCertificate>` | Get certificate at a specific degree. |
| `fn GlobalExactnessProof::exact_count(&self) -> usize` | Count how many degrees are exact. |
| `fn GlobalExactnessProof::non_exact_count(&self) -> usize` | Count how many degrees are not exact. |
| `fn GlobalExactnessProof::summary(&self) -> String` | Generate a summary report. |

## Tests

`cargo test -p exactness_predicate` runs 8 unit tests.
