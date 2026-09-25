# `multiplicity_arena_tests_integration` (C020)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

End-to-end scenarios across the arena stack (layout, bootstrap,
allocation, pointers, ownership, drain/rollback, fail-closed handling).
 returns a per-scenario report so a failure says
which scenario broke and why.

## Dependencies

- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)
- [C013 `multiplicity_arena_allocation`](../C013/README.md)
- [C014 `multiplicity_arena_initialization`](../C014/README.md)
- [C015 `multiplicity_arena_pointers`](../C015/README.md)
- [C016 `multiplicity_arena_ownership`](../C016/README.md)
- [C017 `multiplicity_arena_deallocation`](../C017/README.md)
- [C018 `multiplicity_arena_failure_handling`](../C018/README.md)

## Public API

| Item | Description |
|---|---|
| `struct ScenarioResult` | Outcome of one scenario. |
| `fn ScenarioResult::passed(&self) -> bool` | Did the scenario pass? |
| `struct IntegrationReport` | Outcome of all scenarios. |
| `fn IntegrationReport::all_passed(&self) -> bool` | True iff every scenario passed. |
| `fn IntegrationReport::failures(&self) -> Vec<&ScenarioResult>` | The failed scenarios. |
| `fn run_arena_integration() -> IntegrationReport` | Run every scenario. |

## Tests

`cargo test -p multiplicity_arena_tests_integration` runs 2 unit tests.
