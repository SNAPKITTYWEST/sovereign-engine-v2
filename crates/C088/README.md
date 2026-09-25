# `rollback_mechanism` (C088)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

Transactional updates of a runtime tensor. An update is applied to a
copy, checked with the runtime invariant checker, and committed only if
the new state is valid; otherwise the tensor keeps its last valid state
and the rollback is recorded in the (append-only) history, so the trace
shows every attempt and its outcome.

## Dependencies

- [C081 `runtime_state_snapshot`](../C081/README.md)
- [C089 `runtime_invariant_checking`](../C089/README.md)

## Public API

| Item | Description |
|---|---|
| `struct RollbackReport` | Why an update was rolled back. |
| `struct TransactionalTensor` | A tensor updated only through checked transactions. |
| `fn TransactionalTensor::new(tensor: GapTensor) -> Result<Self, Vec<Violation>>` | Start from `tensor`. |
| `fn TransactionalTensor::apply(&mut self, label: &str, f: impl FnOnce(&mut GapTensor)) -> Result<(), RollbackReport>` | Apply `f` as a transaction: commit if the result is valid, otherwise keep the current state and record a rollback. |
| `fn TransactionalTensor::tensor(&self) -> &GapTensor` | Current (always valid) state. |
| `fn TransactionalTensor::store(&self) -> &SnapshotStore` | Full history, including rollbacks. |
| `fn TransactionalTensor::commits(&self) -> usize` | Committed updates. |
| `fn TransactionalTensor::rollbacks(&self) -> &[RollbackReport]` | Rolled-back updates. |
| `fn TransactionalTensor::history_valid(&self) -> bool` | Every recorded state is valid (rollbacks record the retained state). |

## Tests

`cargo test -p rollback_mechanism` runs 3 unit tests.
