# `gap_tensor_trace` (C010)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

A tamper-evident, append-only trace of tensor states. Each entry stores
the serialized tensor and a digest chained to the previous entry, so any
edit, reordering or truncation in the middle of the trace is detected by
.

Digest of entry `i`: FNV-1a 64 over
`prev_digest ‖ step ‖ label_len ‖ label ‖ payload` (integers little-endian),
where `prev_digest` is  for the first entry.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C005 `gap_tensor_equality`](../C005/README.md)
- [C006 `gap_tensor_serialization`](../C006/README.md)

## Re-exports

- `gap_tensor_serialization::{GapTensor, TensorShape}`

## Public API

| Item | Description |
|---|---|
| `const GENESIS_DIGEST: u64 = fnv1a64(b"gap_tensor_trace/genesis")` | Digest that the first entry chains from. |
| `struct TraceEntry` | One recorded tensor state. |
| `enum TraceError` | Errors from trace verification and access. |
| `struct TensorTrace` | Append-only chained trace of tensor states. |
| `fn TensorTrace::new() -> Self` | An empty trace. |
| `fn TensorTrace::from_entries(entries: Vec<TraceEntry>) -> Result<Self, TraceError>` | Rebuild a trace from stored entries, rejecting it unless it verifies. |
| `fn TensorTrace::record(&mut self, label: impl Into<String>, tensor: &GapTensor) -> u64` | Record a tensor state. |
| `fn TensorTrace::len(&self) -> usize` | Number of entries. |
| `fn TensorTrace::is_empty(&self) -> bool` | True iff nothing has been recorded. |
| `fn TensorTrace::entries(&self) -> &[TraceEntry]` | All entries in order. |
| `fn TensorTrace::head_digest(&self) -> u64` | Digest of the last entry, or `GENESIS_DIGEST` if empty. |
| `fn TensorTrace::verify(&self) -> Result<(), TraceError>` | Check step order, chaining and every digest. |
| `fn TensorTrace::replay(&self, index: usize) -> Result<GapTensor, TraceError>` | Decode the tensor recorded at `index`. |
| `fn TensorTrace::first_divergence(&self, left: usize, right: usize, mode: EqualityMode) -> Result<Option<usize>, TraceError>` | First flat node index at which the states at `left` and `right` differ under `mode`, or `None` if they are equal. |

## Tests

`cargo test -p gap_tensor_trace` runs 3 unit tests.
