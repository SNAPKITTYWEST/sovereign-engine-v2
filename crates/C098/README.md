# `counterexample_harness` (C098)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

Negative tests of the verification machinery itself. Each case feeds a
correspondence check a deliberately broken input — a corrupted arena, a
lax runtime checker, a wrong threshold, a forged certificate, a wrong
candidate list, an understated dimension — and passes only if the check
reports the failure. A harness where every case is caught is evidence
that the Tier 9 checks can detect real mismatches rather than passing
vacuously.

## Dependencies

- [C091 `cross_layer_types`](../C091/README.md)
- [C092 `cross_layer_invariants`](../C092/README.md)
- [C093 `rust_lean_correspondence`](../C093/README.md)
- [C094 `prime_gap_correspondence`](../C094/README.md)
- [C095 `tensor_homology_correspondence`](../C095/README.md)
- [C096 `tor_spectrum_correspondence`](../C096/README.md)

## Public API

| Item | Description |
|---|---|
| `struct CounterexampleCase` | One counterexample case. |
| `struct CounterexampleReport` | All counterexample cases. |
| `fn CounterexampleReport::all_caught(&self) -> bool` | Was every broken input caught? |
| `fn CounterexampleReport::missed(&self) -> Vec<&CounterexampleCase>` | Cases that were not caught. |
| `fn run_counterexamples() -> CounterexampleReport` | Run every counterexample case. |

## Tests

`cargo test -p counterexample_harness` runs 1 unit test.
