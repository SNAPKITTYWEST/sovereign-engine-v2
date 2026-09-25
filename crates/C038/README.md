# `recursion_contradiction_detection` (C038)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Detect contradictions in gap constraints during recursive solving.
Identifies unsatisfiable constraints and marks branches as failed.

## Dependencies

- [C027 `gap_constraint_satisfaction`](../C027/README.md)
- [C031 `recursive_solver_state`](../C031/README.md)
- [C033 `recursive_solver_cursor`](../C033/README.md)

## Public API

| Item | Description |
|---|---|
| `struct Contradiction` | A contradiction found during constraint analysis. |
| `enum ContradictionType` | Types of contradictions that can occur. |
| `struct ContradictionDetector` | Detects contradictions in the solving process. |
| `fn ContradictionDetector::new() -> Self` | Create a new contradiction detector. |
| `fn ContradictionDetector::add_constraint(&mut self, constraint: GapConstraint)` | Add a constraint to check against. |
| `fn ContradictionDetector::check_gap(&mut self, position: usize, gap: u64) -> Option<Contradiction>` | Check a gap against all constraints. |
| `fn ContradictionDetector::check_conflicting_constraints(state: &RecursiveSolverState) -> Option<Contradiction>` | Check for conflicting constraints within state. |
| `fn ContradictionDetector::check_dead_end(cursor: &RecursiveSolverCursor, state: &RecursiveSolverState) -> Option<Contradiction>` | Check for dead ends (no valid moves). |
| `fn ContradictionDetector::check_inconsistent_state(state: &RecursiveSolverState) -> Option<Contradiction>` | Check for inconsistent state. |
| `fn ContradictionDetector::contradictions(&self) -> &[Contradiction]` | Get all detected contradictions. |
| `fn ContradictionDetector::contradiction_count(&self) -> usize` | Get contradiction count. |
| `fn ContradictionDetector::clear(&mut self)` | Clear all detected contradictions. |
| `fn ContradictionDetector::full_check(&mut self, state: &RecursiveSolverState, cursor: &RecursiveSolverCursor) -> Vec<Contradiction>` | Comprehensive contradiction check. |
| `fn ContradictionDetector::has_contradiction(&self) -> bool` | Check if any contradiction exists. |
| `struct ContradictionStats` | Statistics about contradictions. |
| `fn ContradictionStats::new() -> Self` | Create empty stats. |
| `fn ContradictionStats::record(&mut self, contradiction: &Contradiction)` | Record a contradiction. |

## Tests

`cargo test -p recursion_contradiction_detection` runs 6 unit tests.
