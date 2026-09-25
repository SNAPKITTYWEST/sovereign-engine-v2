# `homological_tests_integration` (C050)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Full integration tests for the homological algebra subsystem (Tier 4).
Tests chain complexes, differentials, homology, resolutions, and exactness.

## Dependencies

- [C041 `chain_complex_shape`](../C041/README.md)
- [C042 `chain_complex_types`](../C042/README.md)
- [C043 `differential_operator`](../C043/README.md)
- [C044 `differential_squared_zero`](../C044/README.md)
- [C045 `projective_module_definition`](../C045/README.md)
- [C046 `projective_resolution`](../C046/README.md)
- [C047 `exactness_predicate`](../C047/README.md)
- [C048 `homology_computation`](../C048/README.md)
- [C049 `resolution_certification`](../C049/README.md)

## Public API

| Item | Description |
|---|---|
| `struct HomologicalTestSuite` | Integration test suite for homological algebra. |
| `fn HomologicalTestSuite::test_chain_complex_creation() -> TestResult` | Test 1: Basic chain complex creation and operations. |
| `fn HomologicalTestSuite::test_chain_element_operations() -> TestResult` | Test 2: Chain element operations (addition, scalar multiplication). |
| `fn HomologicalTestSuite::test_differential_application() -> TestResult` | Test 3: Differential operator application. |
| `fn HomologicalTestSuite::test_squared_zero_verification() -> TestResult` | Test 4: Verify d² = 0. |
| `fn HomologicalTestSuite::test_global_exactness() -> TestResult` | Test 5: Global exactness check. |
| `fn HomologicalTestSuite::test_homology_computation() -> TestResult` | Test 6: Homology computation, including torsion. |
| `fn HomologicalTestSuite::test_projective_modules() -> TestResult` | Test 7: Projective module creation and homomorphisms. |
| `fn HomologicalTestSuite::test_projective_resolution() -> TestResult` | Test 8: Projective resolutions are verified exact, not just marked. |
| `fn HomologicalTestSuite::test_resolution_certification() -> TestResult` | Test 9: Full resolution certification. |
| `fn HomologicalTestSuite::test_end_to_end_workflow() -> TestResult` | Test 10: End-to-end chain complex workflow. |
| `fn HomologicalTestSuite::run_all() -> TestSummary` | Run all tests and return summary. |
| `struct TestResult` | Result of a single test. |
| `fn TestResult::passed(name: &str) -> Self` | Create a passed test. |
| `fn TestResult::failed(name: &str, message: &str) -> Self` | Create a failed test, keeping its name. |
| `struct TestSummary` | Summary of all test runs. |
| `fn TestSummary::from_results(results: Vec<TestResult>) -> Self` | Create summary from test results. |
| `fn TestSummary::report(&self) -> String` | Generate a report. |
| `fn TestSummary::all_passed(&self) -> bool` | Check if all tests passed. |

## Tests

`cargo test -p homological_tests_integration` runs 8 unit tests.
