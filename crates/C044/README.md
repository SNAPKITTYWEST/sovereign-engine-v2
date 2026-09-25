# `differential_squared_zero` (C044)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Verification that d² = 0 in a chain complex. This is the defining property
of a chain complex: composing the differential with itself yields zero.

## Dependencies

- [C041 `chain_complex_shape`](../C041/README.md)
- [C043 `differential_operator`](../C043/README.md)

## Public API

| Item | Description |
|---|---|
| `struct SquaredZeroCertificate` | Proof certificate that d² = 0 at a specific degree. |
| `fn SquaredZeroCertificate::new(degree: i32) -> Self` | Create a new certificate. |
| `fn SquaredZeroCertificate::mark_valid(mut self, generators_checked: usize, test_cases_passed: usize) -> Self` | Mark this certificate as valid with statistics. |
| `struct SquaredZeroVerifier` | Verifies that d² = 0 for a differential operator. |
| `fn SquaredZeroVerifier::verify_at_degree(diff: &DifferentialOperator, degree: i32) -> SquaredZeroCertificate` | Verify d² = 0 at a specific degree. |
| `fn SquaredZeroVerifier::verify_all(diff: &DifferentialOperator) -> Vec<SquaredZeroCertificate>` | Verify d² = 0 for all degrees in the chain complex. |
| `fn SquaredZeroVerifier::verify_global(diff: &DifferentialOperator) -> GlobalSquaredZeroProof` | Global verification: check d² = 0 everywhere and return unified status. |
| `struct GlobalSquaredZeroProof` | Global proof that d² = 0 everywhere in a chain complex. |
| `fn GlobalSquaredZeroProof::cert_at(&self, degree: i32) -> Option<&SquaredZeroCertificate>` | Get the certificate at a specific degree. |
| `fn GlobalSquaredZeroProof::summary(&self) -> String` | Pretty-print the proof. |

## Tests

`cargo test -p differential_squared_zero` runs 6 unit tests.
