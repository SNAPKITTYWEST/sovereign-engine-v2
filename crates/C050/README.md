# homological_tests_integration (C050)

## What it does
The integration-test crate for the whole homological-algebra layer (C041-C049): a hand-rolled test harness (`HomologicalTestSuite`) with 10 scenario tests exercising chain complex creation, chain arithmetic, differential application, `d²=0`, global exactness, homology computation, projective modules/homomorphisms, resolutions, certification, and one end-to-end workflow — independent of (and in addition to) each crate's own `#[cfg(test)]` unit tests.

## Public API
- `HomologicalTestSuite` (unit struct) — 10 `test_*()` associated functions, each returning a `TestResult`, plus `run_all() -> TestSummary`.
- `TestResult { name, passed, message }` — `passed(name)`, `failed(message)` (note: `failed()` does not take a name — see gap).
- `TestSummary { total, passed, failed, results }` — `from_results()`, `report() -> String` (✓/✗ formatted), `all_passed()`.

## Pipeline position
Depends on every other crate in the C041-C049 range (`chain_complex_shape`, `chain_complex_types`, `differential_operator`, `differential_squared_zero`, `exactness_predicate`, `homology_computation`, `projective_module_definition`, `projective_resolution`, `resolution_certification`) — it is the terminal aggregation/validation point of the homological-algebra sub-layer, mirroring C040's role for the recursive-solver sub-layer and C060's role for the Tor sub-layer.

## Notes / gaps
- **Gap:** `TestResult::failed(message)` hardcodes `name: "unknown".to_string()` — every failing test in a `run_all()` report shows up as `✗ unknown: <message>` rather than naming which of the 10 scenarios failed. The message body does describe the failure, but the test *name* is lost specifically on the failure path, which is the path where identifying the test matters most. `passed(name)` does capture the name correctly, so this is an asymmetry rather than a missing feature outright.
- Because C049 (`resolution_certification`)'s verification stages are stubs (see its own README), `test_resolution_certification` here only checks `cert.modules_checked != 0` — it doesn't (and given C049's current implementation, can't meaningfully) assert that certification correctly rejects a bad resolution. The integration suite inherits C049's blind spot rather than catching it.
- `test_end_to_end_workflow` is the most valuable test here — it chains d²=0 verification, homology computation, and exactness checking against one shared `DifferentialOperator`, which is closer to how the pipeline would actually be used than the crate-isolated unit tests elsewhere in the layer.
- 7 `#[cfg(test)]` wrapper tests around the public `test_*` methods, plus the 10 methods themselves — effectively double-layered testing (manual harness + Rust's own test runner calling into it).
