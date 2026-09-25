# `final_certification_report` (C100)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

The pipeline's final report. It

1. decides every standard cross-layer lemma with the Tier 9 checks;
2. aggregates all tier and cross-layer obligations (Tier 7), re-checking
   every proof;
3. runs the full regression suite and the counterexample harness;
4. issues a verdict that says exactly what is and is not established.

The verdict is `Complete` only if every obligation is closed without
assumptions and nothing failed. Obligations over unbounded domains (for
example "is_prime is correct for all n") cannot be closed by computation;
while they are open the verdict is `Incomplete` and lists them.

## Dependencies

- [C071 `type_checking_interface`](../C071/README.md)
- [C080 `lean_obligation_aggregator`](../C080/README.md)
- [C091 `cross_layer_types`](../C091/README.md)
- [C092 `cross_layer_invariants`](../C092/README.md)
- [C093 `rust_lean_correspondence`](../C093/README.md)
- [C094 `prime_gap_correspondence`](../C094/README.md)
- [C095 `tensor_homology_correspondence`](../C095/README.md)
- [C096 `tor_spectrum_correspondence`](../C096/README.md)
- [C097 `end_to_end_trace_verification`](../C097/README.md)
- [C098 `counterexample_harness`](../C098/README.md)
- [C099 `full_regression_test_suite`](../C099/README.md)

## Re-exports

- `type_checking_interface::Evidence`

## Public API

| Item | Description |
|---|---|
| `struct CorrespondenceOutcome` | Outcome of deciding one cross-layer lemma. |
| `struct OpenItem` | An obligation that is still open, with what it needs. |
| `enum Verdict` | Final verdict. |
| `struct FinalCertificationReport` | The final certification report. |
| `fn decide_correspondences(lib: &mut CrossLayerLemmaLibrary) -> Vec<CorrespondenceOutcome>` | Decide every standard cross-layer lemma in `lib`. |
| `fn generate() -> Result<FinalCertificationReport, String>` | Build the report. |
| `fn FinalCertificationReport::render(&self) -> String` | Human-readable report (Markdown). |

## Tests

`cargo test -p final_certification_report` runs 1 unit test.
