# `cross_layer_types` (C091)

Tier 9 — cross-layer certification. *Generated from the crate source; regenerate after API changes.*

Shared vocabulary for the Tier 9 cross-layer checks: tier identifiers,
conversions between the representations used by different tiers, finite
test families, and , the result every
correspondence check returns.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C021 `prime_predicate`](../C021/README.md)
- [C031 `recursive_solver_state`](../C031/README.md)
- [C041 `chain_complex_shape`](../C041/README.md)
- [C051 `tor_functor_definition`](../C051/README.md)
- [C061 `ideal_interface`](../C061/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)

## Re-exports

- `chain_complex_shape::ChainComplexShape`
- `gap_tensor_core::{GapTensorNode, CANDIDATE_PRIMES, SIGMA_GAP_MAX}`
- `ideal_interface::Ideal`
- `multiplicity_arena_core::MultiplicityArena`
- `recursive_solver_state::RecursiveSolverState`
- `runtime_state_snapshot::{ check_tensor, tensors_bitwise_equal, vector_state, ClaimSource, GapTensor, InvariantReport, RuntimeClaim, SnapshotStore, TensorShape, Violation, }`
- `tor_functor_definition::TorIndex`

## Public API

| Item | Description |
|---|---|
| `enum Tier` | The ten tiers of the pipeline. |
| `const Tier::ALL: [Tier` | All tiers in order. |
| `fn Tier::number(self) -> usize` | Tier number 0–9. |
| `fn Tier::from_number(n: usize) -> Option<Tier>` | Tier with number `n`. |
| `fn Tier::name(self) -> &'static str` | Human-readable name. |
| `fn Tier::crate_range(self) -> String` | Crate id range, e.g. |
| `fn prime_node(p: u64) -> Option<GapTensorNode>` | Tensor node for a prime (Tier 2 → Tier 0), `None` if it does not fit. |
| `fn ideal_of_node(node: &GapTensorNode) -> Ideal` | Principal ideal of a node's prime (Tier 0 → Tier 6); Nil ↦ (0). |
| `fn solver_path(state: &RecursiveSolverState) -> Vec<GapTensorNode>` | Nodes on a solver's path, bottom first (Tier 3 → Tier 0). |
| `fn tensor_family(alphabet: &[GapTensorNode], max_len: usize) -> Vec<GapTensor>` | Every vector tensor of length `1..=max_len` over `alphabet`. |
| `fn standard_alphabet() -> Vec<GapTensorNode>` | The standard alphabet: Nil, valid candidate nodes, a far candidate that causes dissonance, a non-candidate prime and a negative weight. |
| `fn standard_family() -> Vec<GapTensor>` | The standard test family: every tensor of length 1–3 over the standard alphabet (6 + 36 + 216 = 258 tensors). |
| `struct CorrespondenceReport` | Outcome of checking a correspondence over a family of cases. |
| `fn CorrespondenceReport::new(name: impl Into<String>) -> Self` | An empty report. |
| `fn CorrespondenceReport::check(&mut self, ok: bool, describe: impl FnOnce() -> String)` | Record one case; `describe` is only called on failure. |
| `fn CorrespondenceReport::error(&mut self, message: impl Into<String>)` | Record a case that could not be evaluated. |
| `fn CorrespondenceReport::holds(&self) -> bool` | Did every case hold? |
| `fn CorrespondenceReport::into_result(self) -> Result<u64, String>` | `Ok(cases)` if every case held, else the first failures (for a decision procedure). |

## Tests

`cargo test -p cross_layer_types` runs 4 unit tests.
