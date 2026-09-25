# `runtime_state_snapshot` (C081)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

Snapshots of runtime tensor state. Each snapshot stores the tensor and
its invariant report, and is also appended to a tamper-evident
, so  can prove the stored history
is exactly what was recorded.

Also defines the interface every runtime binding implements to report
what it guarantees:  and . Claims are
re-checked against the recorded execution when certificates are issued.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C007 `gap_tensor_invariants`](../C007/README.md)
- [C010 `gap_tensor_trace`](../C010/README.md)

## Re-exports

- `gap_tensor_core::{GapTensorNode, CANDIDATE_PRIMES, SIGMA_GAP_MAX}`
- `gap_tensor_invariants::{check_nodes, check_tensor, InvariantReport, Violation}`
- `gap_tensor_trace::{GapTensor, TensorShape, TensorTrace, TraceError}`

## Public API

| Item | Description |
|---|---|
| `fn tensors_bitwise_equal(a: &GapTensor, b: &GapTensor) -> bool` | True iff the tensors have the same shape and bit-identical nodes. |
| `fn empty_state() -> GapTensor` | A single-node Nil tensor, used where a snapshot has no data. |
| `fn vector_state(nodes: Vec<GapTensorNode>) -> GapTensor` | A vector tensor of `nodes` (a single Nil node if `nodes` is empty). |
| `struct RuntimeSnapshot` | One recorded runtime state. |
| `fn RuntimeSnapshot::is_valid(&self) -> bool` | Did the state satisfy every tensor invariant? |
| `enum SnapshotError` | Why a snapshot store failed verification. |
| `struct SnapshotStore` | Append-only store of runtime snapshots backed by a chained trace. |
| `fn SnapshotStore::new() -> Self` | An empty store. |
| `fn SnapshotStore::capture(&mut self, label: impl Into<String>, tensor: &GapTensor) -> &RuntimeSnapshot` | Record a state. |
| `fn SnapshotStore::snapshots(&self) -> &[RuntimeSnapshot]` | All snapshots in order. |
| `fn SnapshotStore::len(&self) -> usize` | Number of snapshots. |
| `fn SnapshotStore::is_empty(&self) -> bool` | Nothing recorded yet? |
| `fn SnapshotStore::get(&self, step: usize) -> Option<&RuntimeSnapshot>` | Snapshot at `step`. |
| `fn SnapshotStore::latest(&self) -> Option<&RuntimeSnapshot>` | Most recent snapshot. |
| `fn SnapshotStore::last_valid(&self) -> Option<&RuntimeSnapshot>` | Most recent snapshot that satisfies every invariant. |
| `fn SnapshotStore::first_violation(&self) -> Option<(u64, Violation)>` | First invariant violation, with its step. |
| `fn SnapshotStore::trace(&self) -> &TensorTrace` | The backing trace. |
| `fn SnapshotStore::head_digest(&self) -> u64` | Digest identifying the whole history. |
| `fn SnapshotStore::verify(&self) -> Result<(), SnapshotError>` | Check the trace chain, and that every stored snapshot matches its trace entry and a fresh invariant check. |
| `fn SnapshotStore::snapshots_mut_for_testing(&mut self) -> &mut Vec<RuntimeSnapshot>` | Mutable access to stored snapshots (for tamper tests). |
| `struct RuntimeClaim` | A property a runtime binding guarantees about its recorded execution. |
| `fn RuntimeClaim::new(id: &str, statement: impl Into<String>) -> Self` | A claim. |
| `trait ClaimSource` | A runtime binding that reports claims and can re-check them against its recorded execution. |

## Tests

`cargo test -p runtime_state_snapshot` runs 3 unit tests.
