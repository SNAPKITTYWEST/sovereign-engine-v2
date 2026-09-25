# `runtime_bridge_tests_integration` (C090)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

End-to-end scenarios for the runtime bridge (C081–C089): bindings record
real executions of Tiers 0–3, invariants are re-checked, certificates are
issued, rollbacks keep state valid, and the whole execution is captured
in one verifiable trace.  reports each
scenario by name.

## Dependencies

- [C081 `runtime_state_snapshot`](../C081/README.md)
- [C082 `tensor_runtime_binding`](../C082/README.md)
- [C083 `prime_state_binding`](../C083/README.md)
- [C084 `multiplicity_state_binding`](../C084/README.md)
- [C085 `recursion_runtime_binding`](../C085/README.md)
- [C086 `trace_recording_runtime`](../C086/README.md)
- [C087 `certificate_generation`](../C087/README.md)
- [C088 `rollback_mechanism`](../C088/README.md)
- [C089 `runtime_invariant_checking`](../C089/README.md)

## Re-exports

- `multiplicity_state_binding::ArenaBinding`
- `prime_state_binding::PrimeStateBinding`
- `recursion_runtime_binding::RecursionBinding`
- `tensor_runtime_binding::TensorBinding`

## Public API

| Item | Description |
|---|---|
| `struct StandardExecution` | A complete, clean execution of the four bindings. |
| `fn standard_execution() -> Result<StandardExecution, String>` | Run the standard execution. |
| `fn StandardExecution::certificate(&self) -> ExecutionCertificate` | Certificate for all four bindings. |
| `fn StandardExecution::trace(&self) -> RuntimeTrace` | Whole-execution trace: every binding's history, then the certificate. |
| `struct ScenarioResult` | Outcome of one scenario. |
| `struct RuntimeIntegrationReport` | Outcome of all scenarios. |
| `fn RuntimeIntegrationReport::all_passed(&self) -> bool` | True iff every scenario passed. |
| `fn RuntimeIntegrationReport::failures(&self) -> Vec<&ScenarioResult>` | Failed scenarios. |
| `fn run_runtime_integration() -> RuntimeIntegrationReport` | Run every scenario. |

## Tests

`cargo test -p runtime_bridge_tests_integration` runs 1 unit test.
