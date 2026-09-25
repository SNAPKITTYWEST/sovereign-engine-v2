# `runtime_invariant_checking` (C089)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

Re-checks the gap tensor invariants (Tier 0) over the recorded runtime
history of any binding, and compares the result with the report stored
at capture time. A mismatch means the recording and the static checker
disagree — which the cross-layer lemma
`runtime_invariants_match_static` rules out.

## Dependencies

- [C007 `gap_tensor_invariants`](../C007/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)
- [C082 `tensor_runtime_binding`](../C082/README.md)
- [C083 `prime_state_binding`](../C083/README.md)
- [C084 `multiplicity_state_binding`](../C084/README.md)
- [C085 `recursion_runtime_binding`](../C085/README.md)

## Re-exports

- `multiplicity_state_binding::ArenaBinding`
- `prime_state_binding::PrimeStateBinding`
- `recursion_runtime_binding::RecursionBinding`
- `runtime_state_snapshot::{GapTensor, Violation}`
- `tensor_runtime_binding::TensorBinding`

## Public API

| Item | Description |
|---|---|
| `struct StoreReport` | Invariant results for one recorded history. |
| `fn StoreReport::is_clean(&self) -> bool` | No violations and no disagreements. |
| `struct RuntimeInvariantReport` | Invariant results for several histories. |
| `fn RuntimeInvariantReport::total_violations(&self) -> usize` | Total violations across all histories. |
| `fn RuntimeInvariantReport::stored_reports_agree(&self) -> bool` | Did every stored report agree with its recomputation? |
| `struct RuntimeInvariantChecker` | Runtime invariant checker. |
| `fn RuntimeInvariantChecker::check_state(tensor: &GapTensor) -> Vec<Violation>` | Check a single tensor (same rules as the static checker). |
| `fn RuntimeInvariantChecker::check_store(source: &str, store: &SnapshotStore) -> StoreReport` | Re-check every snapshot of a history. |
| `fn RuntimeInvariantChecker::check_all(stores: &[(&str, &SnapshotStore)]) -> RuntimeInvariantReport` | Re-check several named histories. |
| `fn RuntimeInvariantChecker::check_bindings(tensor: &TensorBinding, primes: &PrimeStateBinding, arena: &ArenaBinding, recursion: &RecursionBinding) -> RuntimeInvariantReport` | Histories of the four standard bindings. |

## Tests

`cargo test -p runtime_invariant_checking` runs 3 unit tests.
