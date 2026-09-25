# `tensor_runtime_binding` (C082)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

Binds a live gap tensor to the runtime snapshot store: every mutation
goes through the binding, is validated at the prime level, and is
recorded. The binding's claims (only candidate primes written, invariants
held, history intact) are re-checkable against the recording.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C002 `gap_tensor_primes`](../C002/README.md)
- [C010 `gap_tensor_trace`](../C010/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)

## Public API

| Item | Description |
|---|---|
| `enum BindingError` | Why a write was refused. |
| `struct TensorBinding` | A tensor whose every state is recorded. |
| `fn TensorBinding::new(name: impl Into<String>, tensor: GapTensor) -> Self` | Bind `tensor`, recording its initial state. |
| `fn TensorBinding::tensor(&self) -> &GapTensor` | Current state. |
| `fn TensorBinding::store(&self) -> &SnapshotStore` | Recorded history. |
| `fn TensorBinding::rejected(&self) -> &[(usize, GapTensorNode)]` | Writes refused so far. |
| `fn TensorBinding::set_node(&mut self, index: usize, node: GapTensorNode) -> Result<&RuntimeSnapshot, BindingError>` | Write node `index` (flat, row-major). |
| `fn TensorBinding::apply(&mut self, label: &str, f: impl FnOnce(&mut GapTensor)) -> Result<&RuntimeSnapshot, BindingError>` | Apply a bulk update and record the result. |

## Tests

`cargo test -p tensor_runtime_binding` runs 3 unit tests.
