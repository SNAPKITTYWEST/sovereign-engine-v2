# `krull_spectrum_tests_integration` (C070)

Tier 6 — Krull dimension. *Generated from the crate source; regenerate after API changes.*

Integration scenarios for the Krull tier (C061–C069) on Spec(Z) and its
subspaces, each checked against known mathematics: `dim Spec(Z) = 1` via
the chains `(0) ⊂ (p)`, closed points form a 0-dimensional space, the
generic point `(0)` is dense, and ideal arithmetic follows gcd/lcm.

## Dependencies

- [C061 `ideal_interface`](../C061/README.md)
- [C062 `prime_ideal_predicate`](../C062/README.md)
- [C063 `maximal_ideal_predicate`](../C063/README.md)
- [C064 `spectrum_definition`](../C064/README.md)
- [C065 `spectrum_order`](../C065/README.md)
- [C066 `spectrum_chains`](../C066/README.md)
- [C067 `krull_dimension_definition`](../C067/README.md)
- [C068 `dimension_upper_bounds`](../C068/README.md)
- [C069 `krull_certification`](../C069/README.md)

## Public API

| Item | Description |
|---|---|
| `struct KrullIntegrationSuite` | Full integration test suite |
| `fn KrullIntegrationSuite::test_empty_spectrum() -> bool` | The empty spectrum has dimension 0 and no chains. |
| `fn KrullIntegrationSuite::test_single_prime() -> bool` | A single closed point has dimension 0. |
| `fn KrullIntegrationSuite::test_two_primes() -> bool` | Finitely many closed points: dimension 0, one singleton chain each. |
| `fn KrullIntegrationSuite::test_divisibility_chain() -> bool` | Spec(Z) truncated to small primes has dimension 1, and every longest chain is `(0) ⊂ (p)`. |
| `fn KrullIntegrationSuite::test_zariski_topology_consistency() -> bool` | The generic point is dense; closed points are closed. |
| `fn KrullIntegrationSuite::test_specialization_properties() -> bool` | The specialization order on Spec(Z) is a partial order with (0) at the bottom. |
| `fn KrullIntegrationSuite::test_dimension_strategies() -> bool` | Upper-bound strategies never undercut the exact dimension. |
| `fn KrullIntegrationSuite::test_upper_bounds() -> bool` | Bounds are checked honestly: a true bound passes, a false one fails. |
| `fn KrullIntegrationSuite::test_dimension_certification() -> bool` | Certification passes for both spectra and catches a violated bound. |
| `fn KrullIntegrationSuite::test_catenary_property() -> bool` | Both model spectra are catenary. |
| `fn KrullIntegrationSuite::test_chain_extension() -> bool` | Chains extend only strictly upward. |
| `fn KrullIntegrationSuite::test_maximal_chains_consistency() -> bool` | Every maximal chain is valid and none is longer than the dimension allows. |
| `fn KrullIntegrationSuite::test_localization_behavior() -> bool` | Ideal arithmetic in Z: membership by gcd, intersection by lcm, prime and maximal ideals. |
| `fn KrullIntegrationSuite::test_integral_extension() -> bool` | An integral-extension bound equals the dimension it is built from. |
| `fn KrullIntegrationSuite::run_all() -> IntegrationTestResult` | Run all integration tests |
| `struct IntegrationTestResult` | Result of integration tests |
| `fn IntegrationTestResult::new() -> Self` | Create empty result |
| `fn IntegrationTestResult::add_test(&mut self, name: &str, passed: bool)` | Add test result |
| `fn IntegrationTestResult::all_passed(&self) -> bool` | All tests passed |
| `fn IntegrationTestResult::test(&self, name: &str) -> Option<bool>` | Get test result |
| `fn IntegrationTestResult::passed_count(&self) -> usize` | Count passed tests |
| `fn IntegrationTestResult::total_count(&self) -> usize` | Count total tests |
| `fn IntegrationTestResult::failed_tests(&self) -> Vec<String>` | Get failed tests |

## Tests

`cargo test -p krull_spectrum_tests_integration` runs 2 unit tests.
