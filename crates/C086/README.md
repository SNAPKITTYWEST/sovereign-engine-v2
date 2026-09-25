# `trace_recording_runtime` (C086)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

One tamper-evident trace for a whole execution: the recorded states of
every binding and the certificates issued for them, interleaved in a
single hash chain. Certificates are recorded as labelled entries (the
label is covered by the chain digest), so editing a certificate summary,
a state, or the order of entries is detected by .

## Dependencies

- [C010 `gap_tensor_trace`](../C010/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)
- [C087 `certificate_generation`](../C087/README.md)

## Public API

| Item | Description |
|---|---|
| `const CERTIFICATE_PREFIX: &str = "certificate "` | Label prefix of certificate entries. |
| `enum EntryKind` | Kind of a trace entry. |
| `struct RuntimeTrace` | A whole-execution trace. |
| `fn RuntimeTrace::new() -> Self` | An empty trace. |
| `fn RuntimeTrace::from_entries(entries: Vec<TraceEntry>) -> Result<Self, TraceError>` | Rebuild from entries, rejecting a broken chain. |
| `fn RuntimeTrace::record_state(&mut self, label: &str, tensor: &GapTensor) -> u64` | Record a free-form state. |
| `fn RuntimeTrace::record_store(&mut self, source: &str, store: &SnapshotStore)` | Append every snapshot of a binding's history. |
| `fn RuntimeTrace::record_certificate(&mut self, certificate: &ExecutionCertificate) -> u64` | Append a certificate summary. |
| `fn RuntimeTrace::verify(&self) -> Result<(), TraceError>` | Verify the whole chain. |
| `fn RuntimeTrace::len(&self) -> usize` | Number of entries. |
| `fn RuntimeTrace::is_empty(&self) -> bool` | Nothing recorded? |
| `fn RuntimeTrace::head_digest(&self) -> u64` | Digest of the whole execution. |
| `fn RuntimeTrace::entries(&self) -> &[TraceEntry]` | Raw entries. |
| `fn RuntimeTrace::kind(&self, index: usize) -> Option<EntryKind>` | Classify entry `index`. |
| `fn RuntimeTrace::replay(&self, index: usize) -> Result<GapTensor, TraceError>` | Replay entry `index`. |
| `fn RuntimeTrace::certificates(&self) -> Vec<String>` | Certificate summaries in order. |

## Tests

`cargo test -p trace_recording_runtime` runs 2 unit tests.
