# `tor_tests_integration` (C060)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

Integration scenarios for the Tor tier (C051–C059), each checked against
known values: `Z/m ⊗ Z/n = Z/gcd(m,n)`, `Tor_1(Z/m, Z/n) = Z/gcd(m,n)`,
vanishing of higher Tor, agreement of `Tor_0` with the tensor product, and
functoriality of induced maps.

## Dependencies

- [C051 `tor_functor_definition`](../C051/README.md)
- [C052 `tensor_product_module`](../C052/README.md)
- [C053 `resolution_tensored`](../C053/README.md)
- [C054 `derived_homology`](../C054/README.md)
- [C055 `tor_zero_structure`](../C055/README.md)
- [C056 `tor_higher_degrees`](../C056/README.md)
- [C057 `functoriality_of_tor`](../C057/README.md)
- [C058 `tor_invariants_computation`](../C058/README.md)
- [C059 `tor_chain_complex_interface`](../C059/README.md)

## Re-exports

- `derived_homology::compute_tor_from_resolution`
- `functoriality_of_tor::ModuleMap`
- `resolution_tensored::TensoredComplex`
- `tensor_product_module::TensorProductModule`
- `tor_chain_complex_interface::TorChainComplexData`
- `tor_functor_definition::TorComputation`
- `tor_higher_degrees::is_short_exact_sequence`
- `tor_invariants_computation::compute_betti_numbers`
- `tor_zero_structure::analyze_tor_zero`

## Public API

| Item | Description |
|---|---|
| `struct ScenarioResult` | Outcome of one scenario. |
| `struct TorIntegrationReport` | Outcome of all scenarios. |
| `fn TorIntegrationReport::all_passed(&self) -> bool` | True iff every scenario passed. |
| `fn TorIntegrationReport::failures(&self) -> Vec<&ScenarioResult>` | Failed scenarios. |
| `fn run_tor_integration() -> TorIntegrationReport` | Run every scenario. |
| `fn tier5_integration_test() -> bool` | True iff every Tor-tier scenario passes. |

## Tests

`cargo test -p tor_tests_integration` runs 2 unit tests.
