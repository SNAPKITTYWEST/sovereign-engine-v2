# `certificate_generation` (C087)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

Execution certificates. Every claim of every runtime binding becomes a
proof obligation (`runtime_{source}_{claim}`). The claim is re-checked
against the recorded execution through a decision procedure: success
discharges the obligation with a  (evidence grade
`Computed`), failure marks it failed with the counterexample. The
certificate records each source's history digest, binding it to exactly
that execution.

## Dependencies

- [C072 `obligation_management`](../C072/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)
- [C082 `tensor_runtime_binding`](../C082/README.md)
- [C083 `prime_state_binding`](../C083/README.md)
- [C084 `multiplicity_state_binding`](../C084/README.md)
- [C085 `recursion_runtime_binding`](../C085/README.md)

## Re-exports

- `obligation_management::ObligationStatus`
- `multiplicity_state_binding::ArenaBinding`
- `prime_state_binding::PrimeStateBinding`
- `recursion_runtime_binding::RecursionBinding`
- `tensor_runtime_binding::TensorBinding`

## Public API

| Item | Description |
|---|---|
| `fn claim_obligation_id(source: &str, claim: &str) -> String` | Obligation id for a runtime claim. |
| `struct ExecutionCertificate` | Certificate for one recorded execution. |
| `fn ExecutionCertificate::closed(&self) -> usize` | Claims that held. |
| `fn ExecutionCertificate::failed(&self) -> usize` | Claims that failed. |
| `fn ExecutionCertificate::all_hold(&self) -> bool` | Every claim held. |
| `fn ExecutionCertificate::holds(&self, source: &str, claim: &str) -> Option<bool>` | Did claim `claim` of `source` hold? |
| `fn ExecutionCertificate::summary(&self) -> String` | One-line summary (used as a trace label). |
| `fn certify(sources: &[&dyn ClaimSource]) -> ExecutionCertificate` | Issue a certificate for the given sources. |

## Tests

`cargo test -p certificate_generation` runs 3 unit tests.
