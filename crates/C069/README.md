# `krull_certification` (C069)

Tier 6 — Krull dimension. *Generated from the crate source; regenerate after API changes.*

Certification that Krull dimension is correct.
Verify computation against bounds and algebraic properties.

## Dependencies

- [C010 `gap_tensor_trace`](../C010/README.md)
- [C064 `spectrum_definition`](../C064/README.md)
- [C065 `spectrum_order`](../C065/README.md)
- [C066 `spectrum_chains`](../C066/README.md)
- [C067 `krull_dimension_definition`](../C067/README.md)
- [C068 `dimension_upper_bounds`](../C068/README.md)

## Public API

| Item | Description |
|---|---|
| `struct DimensionProof` | Proof that a dimension computation is correct: the exhaustive chain enumeration's longest chains, checked to be strictly increasing and of length `dim + 1`, plus (optionally) upper bounds. |
| `fn DimensionProof::from_spectrum(spec: &Spectrum) -> Self` | Create proof from spectrum |
| `fn DimensionProof::verify(&self) -> bool` | The chain witness is valid, and any checked bounds hold. |
| `fn DimensionProof::check_bounds(&mut self, bounds: &BoundCollection)` | Check dimension against upper bounds |
| `struct CertificationChecker` | Certification checker with multiple properties |
| `fn CertificationChecker::new(spec: Spectrum) -> Self` | Create checker for spectrum |
| `fn CertificationChecker::check_all(&mut self) -> CertificationResult` | Run all certification checks. |
| `fn CertificationChecker::verify_bounds(&mut self, bounds: &BoundCollection) -> bool` | Verify against specific bounds |
| `fn CertificationChecker::proof(&self) -> &DimensionProof` | Get the proof |
| `struct CertificationResult` | Result of certification checks |
| `fn CertificationResult::new() -> Self` | Create empty result |
| `fn CertificationResult::add_check(&mut self, name: &str, passed: bool)` | Add a check result |
| `fn CertificationResult::all_passed(&self) -> bool` | All checks passed |
| `fn CertificationResult::check(&self, name: &str) -> Option<bool>` | Get individual check result |
| `fn CertificationResult::checks(&self) -> &std::collections::BTreeMap<String, bool>` | Get all checks |
| `fn CertificationResult::passed_count(&self) -> usize` | Count passed checks |
| `fn CertificationResult::total_count(&self) -> usize` | Count total checks |
| `fn CertificationResult::failed_checks(&self) -> Vec<String>` | Get failed checks |

## Tests

`cargo test -p krull_certification` runs 7 unit tests.
