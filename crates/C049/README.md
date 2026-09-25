# `resolution_certification` (C049)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Certification that a projective resolution is valid. Each level is only
granted after the corresponding check actually passes:

1. **Basic** — one differential per adjacent pair of modules, with source
   and target ranks matching the modules.
2. **SquaredZeroVerified** — every composite `d_i ∘ d_{i+1}` (and
   `ε ∘ d_1`) is the zero matrix, computed exactly.
3. **ExactnessVerified** — the augmented complex has zero homology at
   every `P_i` (ranks and torsion via Smith normal form).
4. **FullyCertified** — the augmentation is surjective (or implicit: the
   quotient map onto `coker d_1`).

## Dependencies

- [C044 `differential_squared_zero`](../C044/README.md)
- [C046 `projective_resolution`](../C046/README.md)
- [C047 `exactness_predicate`](../C047/README.md)
- [C048 `homology_computation`](../C048/README.md)

## Re-exports

- `projective_resolution::{ProjectiveModule, ProjectiveModuleHomomorphism, ProjectiveResolution}`

## Public API

| Item | Description |
|---|---|
| `enum CertificationLevel` | Certification level for a projective resolution. |
| `fn CertificationLevel::is_fully_certified(self) -> bool` | Check if this level includes full certification. |
| `fn CertificationLevel::to_string(self) -> &'static str` | Pretty-print the level. |
| `struct ResolutionCertificate` | Certification report for a projective resolution. |
| `fn ResolutionCertificate::new(resolution_len: usize) -> Self` | Create a new certificate. |
| `fn ResolutionCertificate::mark_basic(mut self) -> Self` | Mark as basic certified. |
| `fn ResolutionCertificate::mark_squared_zero_verified(mut self) -> Self` | Mark d² = 0 as verified. |
| `fn ResolutionCertificate::mark_exactness_verified(mut self) -> Self` | Mark exactness as verified. |
| `fn ResolutionCertificate::mark_augmentation_valid(mut self) -> Self` | Mark augmentation as valid. |
| `fn ResolutionCertificate::summary(&self) -> String` | Generate a full summary. |
| `struct ResolutionCertifier` | Resolution certifier: verifies that a projective resolution is valid. |
| `fn ResolutionCertifier::check_basic(resolution: &ProjectiveResolution) -> ResolutionCertificate` | Structural checks: modules present, one differential per adjacent pair, ranks consistent. |
| `fn ResolutionCertifier::verify_squared_zero(resolution: &ProjectiveResolution) -> ResolutionCertificate` | Verify that every composite through a module is exactly zero. |
| `fn ResolutionCertifier::verify_exactness(resolution: &ProjectiveResolution) -> ResolutionCertificate` | Verify that the augmented complex has zero homology at every module. |
| `fn ResolutionCertifier::verify_augmentation(resolution: &ProjectiveResolution) -> ResolutionCertificate` | Verify that the augmentation is surjective. |
| `fn ResolutionCertifier::certify_fully(resolution: &ProjectiveResolution) -> ResolutionCertificate` | Perform full certification. |
| `fn ResolutionCertifier::certify_batch(resolutions: &[ProjectiveResolution]) -> Vec<ResolutionCertificate>` | Batch certification of multiple resolutions. |
| `fn ResolutionCertifier::batch_summary(certs: &[ResolutionCertificate]) -> String` | Generate a certification report for a batch. |

## Tests

`cargo test -p resolution_certification` runs 11 unit tests.
