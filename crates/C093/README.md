# `rust_lean_correspondence` (C093)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

The correspondence between runtime claims (Rust) and proof obligations
(the Lean-style layer). For every runtime claim, a certificate must hold
exactly one obligation whose statement is the claim's statement. The
obligation is closed if and only if an independent re-check of the claim
succeeds; a closed obligation's proof must type-check against its
statement with `Computed` evidence; a failed one carries no proof; and the
certificate's digests must match the sources' histories.

 checks this over real
executions that deliberately include failing claims.

## Dependencies

- [C071 `type_checking_interface`](../C071/README.md)
- [C082 `tensor_runtime_binding`](../C082/README.md)
- [C083 `prime_state_binding`](../C083/README.md)
- [C084 `multiplicity_state_binding`](../C084/README.md)
- [C085 `recursion_runtime_binding`](../C085/README.md)
- [C087 `certificate_generation`](../C087/README.md)
- [C091 `cross_layer_types`](../C091/README.md)

## Re-exports

- `certificate_generation::{certify, claim_obligation_id, ExecutionCertificate, ObligationStatus}`
- `cross_layer_types::CorrespondenceReport`

## Public API

| Item | Description |
|---|---|
| `fn lean_statement(source: &str, statement: &str) -> LeanType` | Lean statement of a runtime claim, as written into certificates. |
| `fn check_certificate_against_sources(cert: &ExecutionCertificate, sources: &[&dyn ClaimSource], report: &mut CorrespondenceReport)` | Check `cert` against the sources it was issued for. |
| `struct Executions` | Real executions, some with deliberately failing claims. |
| `fn Executions::sources(&self) -> Vec<&dyn ClaimSource>` | All executions as claim sources. |
| `fn standard_executions() -> Result<Executions, String>` | Build the executions. |
| `fn check_certificates_discharge_obligations() -> CorrespondenceReport` | Certificates close exactly the claims that hold, per source and for all sources together. |

## Tests

`cargo test -p rust_lean_correspondence` runs 2 unit tests.
