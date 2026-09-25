# `full_regression_test_suite` (C099)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

Runs one regression suite per tier (0–8) and reports each by tier and
name: the integration suites of Tiers 1, 2, 4, 5, 6 and 8, the decided
recursion lemmas (Tier 3), serialization and trace round trips (Tier 0),
and the obligation aggregation (Tier 7, no refuted obligations).

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C002 `gap_tensor_primes`](../C002/README.md)
- [C003 `gap_tensor_spectral`](../C003/README.md)
- [C004 `gap_tensor_shape`](../C004/README.md)
- [C005 `gap_tensor_equality`](../C005/README.md)
- [C006 `gap_tensor_serialization`](../C006/README.md)
- [C007 `gap_tensor_invariants`](../C007/README.md)
- [C008 `gap_tensor_ordering`](../C008/README.md)
- [C009 `gap_tensor_arithmetic`](../C009/README.md)
- [C010 `gap_tensor_trace`](../C010/README.md)
- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)
- [C013 `multiplicity_arena_allocation`](../C013/README.md)
- [C014 `multiplicity_arena_initialization`](../C014/README.md)
- [C015 `multiplicity_arena_pointers`](../C015/README.md)
- [C016 `multiplicity_arena_ownership`](../C016/README.md)
- [C017 `multiplicity_arena_deallocation`](../C017/README.md)
- [C018 `multiplicity_arena_failure_handling`](../C018/README.md)
- [C019 `multiplicity_arena_statistics`](../C019/README.md)
- [C020 `multiplicity_arena_tests_integration`](../C020/README.md)
- [C021 `prime_predicate`](../C021/README.md)
- [C022 `prime_enumeration`](../C022/README.md)
- [C023 `gap_candidate_set`](../C023/README.md)
- [C024 `gap_ordering`](../C024/README.md)
- [C025 `gap_multiplicity`](../C025/README.md)
- [C026 `gap_absolute_difference`](../C026/README.md)
- [C027 `gap_constraint_satisfaction`](../C027/README.md)
- [C028 `gap_verification`](../C028/README.md)
- [C029 `prime_gap_relationship`](../C029/README.md)
- [C030 `prime_gap_tests_integration`](../C030/README.md)
- [C031 `recursive_solver_state`](../C031/README.md)
- [C032 `recursion_depth_management`](../C032/README.md)
- [C033 `recursive_solver_cursor`](../C033/README.md)
- [C034 `recursive_solver_selection`](../C034/README.md)
- [C035 `recursive_solver_transition`](../C035/README.md)
- [C036 `recursion_base_case`](../C036/README.md)
- [C037 `recursion_backtracking`](../C037/README.md)
- [C038 `recursion_contradiction_detection`](../C038/README.md)
- [C039 `recursion_solution_path`](../C039/README.md)
- [C040 `recursive_solver_trace`](../C040/README.md)
- [C041 `chain_complex_shape`](../C041/README.md)
- [C042 `chain_complex_types`](../C042/README.md)
- [C043 `differential_operator`](../C043/README.md)
- [C044 `differential_squared_zero`](../C044/README.md)
- [C045 `projective_module_definition`](../C045/README.md)
- [C046 `projective_resolution`](../C046/README.md)
- [C047 `exactness_predicate`](../C047/README.md)
- [C048 `homology_computation`](../C048/README.md)
- [C049 `resolution_certification`](../C049/README.md)
- [C050 `homological_tests_integration`](../C050/README.md)
- [C051 `tor_functor_definition`](../C051/README.md)
- [C052 `tensor_product_module`](../C052/README.md)
- [C053 `resolution_tensored`](../C053/README.md)
- [C054 `derived_homology`](../C054/README.md)
- [C055 `tor_zero_structure`](../C055/README.md)
- [C056 `tor_higher_degrees`](../C056/README.md)
- [C057 `functoriality_of_tor`](../C057/README.md)
- [C058 `tor_invariants_computation`](../C058/README.md)
- [C059 `tor_chain_complex_interface`](../C059/README.md)
- [C060 `tor_tests_integration`](../C060/README.md)
- [C061 `ideal_interface`](../C061/README.md)
- [C062 `prime_ideal_predicate`](../C062/README.md)
- [C063 `maximal_ideal_predicate`](../C063/README.md)
- [C064 `spectrum_definition`](../C064/README.md)
- [C065 `spectrum_order`](../C065/README.md)
- [C066 `spectrum_chains`](../C066/README.md)
- [C067 `krull_dimension_definition`](../C067/README.md)
- [C068 `dimension_upper_bounds`](../C068/README.md)
- [C069 `krull_certification`](../C069/README.md)
- [C070 `krull_spectrum_tests_integration`](../C070/README.md)
- [C071 `type_checking_interface`](../C071/README.md)
- [C072 `obligation_management`](../C072/README.md)
- [C073 `gap_lemmas_library`](../C073/README.md)
- [C074 `memory_lemmas_library`](../C074/README.md)
- [C075 `recursion_lemmas_library`](../C075/README.md)
- [C076 `homological_lemmas_library`](../C076/README.md)
- [C077 `tor_resolution_lemmas_library`](../C077/README.md)
- [C078 `krull_lemmas_library`](../C078/README.md)
- [C079 `cross_layer_lemmas_library`](../C079/README.md)
- [C080 `lean_obligation_aggregator`](../C080/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)
- [C082 `tensor_runtime_binding`](../C082/README.md)
- [C083 `prime_state_binding`](../C083/README.md)
- [C084 `multiplicity_state_binding`](../C084/README.md)
- [C085 `recursion_runtime_binding`](../C085/README.md)
- [C086 `trace_recording_runtime`](../C086/README.md)
- [C087 `certificate_generation`](../C087/README.md)
- [C088 `rollback_mechanism`](../C088/README.md)
- [C089 `runtime_invariant_checking`](../C089/README.md)
- [C090 `runtime_bridge_tests_integration`](../C090/README.md)

## Public API

| Item | Description |
|---|---|
| `struct SuiteResult` | Result of one suite. |
| `struct RegressionReport` | Results of all suites. |
| `fn RegressionReport::all_passed(&self) -> bool` | Did every suite pass? |
| `fn RegressionReport::failures(&self) -> Vec<&SuiteResult>` | Failed suites. |
| `fn run_regression() -> RegressionReport` | Run every suite. |

## Tests

`cargo test -p full_regression_test_suite` runs 1 unit test.
