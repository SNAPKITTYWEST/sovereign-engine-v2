# krull_spectrum_tests_integration

End-to-end integration test suite for the entire Krull-dimension layer
(C061-C069), exposed as a callable API rather than just `#[cfg(test)]` code.

## What it does

`KrullIntegrationSuite` is a unit struct with 14 associated functions
(`test_empty_spectrum`, `test_single_prime`, `test_divisibility_chain`,
`test_zariski_topology_consistency`, `test_specialization_properties`,
`test_dimension_strategies`, `test_upper_bounds`,
`test_dimension_certification`, `test_catenary_property`,
`test_chain_extension`, `test_maximal_chains_consistency`,
`test_localization_behavior`, `test_integral_extension`, plus the two
"primes" tests), each returning `bool` and exercising one cross-crate
interaction. `run_all()` executes all of them into an
`IntegrationTestResult` (name -> pass/fail map, mirroring
`CertificationResult` from C069).

## Public API

- `KrullIntegrationSuite` — 14 `pub fn test_*() -> bool` associated
  functions, plus `run_all() -> IntegrationTestResult`
- `IntegrationTestResult`: `add_test`, `all_passed`, `test(name)`,
  `passed_count`, `total_count`, `failed_tests`

## Pipeline role

Depends on every other crate in the Krull layer
(`ideal_interface` C061 through `krull_certification` C069). It is the
capstone integration crate for this layer, analogous to what
`full_regression_test_suite` (C099, currently unimplemented) is meant to be
for the whole workspace.

## Gaps / weak spots

- Because the "tests" are ordinary `pub fn` returning `bool`, they can be
  called from any downstream crate, not just via `cargo test` — this is
  presumably intentional (so a certification report can call `run_all()`
  programmatically) but it also means assertion failures inside these
  functions never panic; callers must remember to check the boolean.
- Several of these self-tests are weak: `test_zariski_topology_consistency`
  only asserts `!spec.is_empty()`, not any actual topology property;
  `test_catenary_property` and similar patterns
  (`x || !x`) elsewhere in this layer recur here too, e.g.
  `test_specialization_properties`'s transitivity check is conditionally
  skipped (`if ... { ... } else { true }`) rather than exercised on a case
  guaranteed to trigger it.
- `#[cfg(test)] mod tests` at the bottom duplicates calls into
  `KrullIntegrationSuite`, so the "real" tests and the "integration suite"
  are two overlapping layers of indirection over the same weak assertions.
