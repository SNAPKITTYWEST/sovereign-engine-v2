# `recursive_solver_selection` (C034)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Select the next gap to process based on constraints and heuristic scoring.
Implements gap ranking, constraint satisfaction scoring, and selection strategies.

## Dependencies

- [C023 `gap_candidate_set`](../C023/README.md)
- [C024 `gap_ordering`](../C024/README.md)
- [C025 `gap_multiplicity`](../C025/README.md)
- [C026 `gap_absolute_difference`](../C026/README.md)
- [C033 `recursive_solver_cursor`](../C033/README.md)

## Public API

| Item | Description |
|---|---|
| `enum SelectionStrategy` | Scoring heuristics for gap selection. |
| `struct GapSelectionScore` | Score information for a gap candidate. |
| `struct RecursiveSolverSelector` | Selector for choosing next gap during recursive solving. |
| `fn RecursiveSolverSelector::new(cursor: RecursiveSolverCursor, strategy: SelectionStrategy) -> Self` | Create a new selector with a cursor and strategy. |
| `fn RecursiveSolverSelector::set_strategy(&mut self, strategy: SelectionStrategy)` | Change the selection strategy. |
| `fn RecursiveSolverSelector::strategy(&self) -> SelectionStrategy` | Get the current strategy. |
| `fn RecursiveSolverSelector::score_candidates(&self) -> Vec<GapSelectionScore>` | Score all unvisited gaps. |
| `fn RecursiveSolverSelector::select_next(&mut self) -> Option<(usize, (u64, u64, u64))>` | Select the best next gap based on scoring. |
| `fn RecursiveSolverSelector::select_top_k(&self, k: usize) -> Vec<GapSelectionScore>` | Get the best N candidates. |
| `fn RecursiveSolverSelector::select_by_constraint(&mut self, required_gap: u64) -> Option<(usize, (u64, u64, u64))>` | Select based on constraint matching (gap size must satisfy constraints). |
| `fn RecursiveSolverSelector::history(&self) -> &[usize]` | Get the selection history. |
| `fn RecursiveSolverSelector::clear_history(&mut self)` | Clear selection history. |
| `fn RecursiveSolverSelector::cursor(&self) -> &RecursiveSolverCursor` | Get a reference to the cursor. |
| `fn RecursiveSolverSelector::cursor_mut(&mut self) -> &mut RecursiveSolverCursor` | Get a mutable reference to the cursor. |

## Tests

`cargo test -p recursive_solver_selection` runs 9 unit tests.
