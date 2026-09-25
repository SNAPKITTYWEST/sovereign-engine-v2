# `end_to_end_trace_verification` (C097)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

End-to-end check of a whole runtime execution: the standard execution of
all four bindings is certified and recorded in one trace; every state in
the trace must replay to exactly the binding's recorded snapshot, the
certificate entry must equal the issued certificate, and every kind of
tampering (payload bit flip, label edit, deletion, reordering) must be
detected.

## Dependencies

- [C081 `runtime_state_snapshot`](../C081/README.md)
- [C086 `trace_recording_runtime`](../C086/README.md)
- [C087 `certificate_generation`](../C087/README.md)
- [C090 `runtime_bridge_tests_integration`](../C090/README.md)
- [C093 `rust_lean_correspondence`](../C093/README.md)

## Re-exports

- `rust_lean_correspondence::CorrespondenceReport`

## Public API

| Item | Description |
|---|---|
| `fn check_trace_replay_matches_execution() -> CorrespondenceReport` | Replay the standard execution's trace and try to tamper with it. |
| `fn run_end_to_end() -> Vec<CorrespondenceReport>` | All end-to-end checks: trace replay and certificate correspondence. |

## Tests

`cargo test -p end_to_end_trace_verification` runs 1 unit test.
