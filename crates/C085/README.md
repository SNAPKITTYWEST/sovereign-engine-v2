# `recursion_runtime_binding` (C085)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

Binds a recursive solver run (Tier 3) to the runtime snapshot store: each
push and pop of the solver path goes through a depth manager and the path
is recorded as a tensor. Claims (depth within limit, depth equals path
length, history intact) are re-checkable.

## Dependencies

- [C031 `recursive_solver_state`](../C031/README.md)
- [C032 `recursion_depth_management`](../C032/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)

## Public API

| Item | Description |
|---|---|
| `enum RecursionBindingError` | Why a solver step was refused. |
| `struct DepthEvent` | One recorded solver step. |
| `struct RecursionBinding` | A recorded solver run. |
| `fn RecursionBinding::new(name: impl Into<String>, max_depth: u32) -> Self` | A run limited to `max_depth`. |
| `fn RecursionBinding::push(&mut self, node: GapTensorNode) -> Result<u32, RecursionBindingError>` | Descend one level with `node`. |
| `fn RecursionBinding::pop(&mut self) -> Result<GapTensorNode, RecursionBindingError>` | Return one level, yielding its node. |
| `fn RecursionBinding::events(&self) -> &[DepthEvent]` | Recorded steps. |
| `fn RecursionBinding::store(&self) -> &SnapshotStore` | Recorded history. |
| `fn RecursionBinding::depth(&self) -> u32` | Current depth. |
| `fn RecursionBinding::state_mut_for_testing(&mut self) -> &mut RecursiveSolverState` | Solver state for fault-injection tests. |

## Tests

`cargo test -p recursion_runtime_binding` runs 2 unit tests.
