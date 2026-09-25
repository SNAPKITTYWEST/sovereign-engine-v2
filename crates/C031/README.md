# `recursive_solver_state` (C031)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Core state machine for recursive solver. Tracks the current state during
gap sequence resolution: cursor position, recursion depth, path history,
and accumulated constraints.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C010 `gap_tensor_trace`](../C010/README.md)

## Public API

| Item | Description |
|---|---|
| `const MAX_RECURSION_DEPTH: u32 = 100` | Maximum recursion depth allowed before backtracking. |
| `struct RecursiveSolverState` | Represents the recursive state during gap solving. |
| `struct GapConstraint` | A gap constraint: a prime must satisfy certain properties at this position. |
| `fn RecursiveSolverState::new() -> Self` | Create a new recursive solver state starting at position 0, depth 0. |
| `fn RecursiveSolverState::cursor(&self) -> usize` | Get the current cursor position. |
| `fn RecursiveSolverState::depth(&self) -> u32` | Get the current recursion depth. |
| `fn RecursiveSolverState::set_cursor(&mut self, position: usize)` | Set cursor to a new position. |
| `fn RecursiveSolverState::advance_cursor(&mut self)` | Increment cursor by 1. |
| `fn RecursiveSolverState::increase_depth(&mut self)` | Increment recursion depth. |
| `fn RecursiveSolverState::decrease_depth(&mut self)` | Decrement recursion depth. |
| `fn RecursiveSolverState::exceeds_max_depth(&self) -> bool` | Check if we've exceeded maximum recursion depth. |
| `fn RecursiveSolverState::push_state(&mut self, node: GapTensorNode)` | Push the current state (cursor, depth, node) onto the path stack. |
| `fn RecursiveSolverState::pop_state(&mut self) -> Option<(usize, u32, GapTensorNode)>` | Pop the most recent state from the path stack and restore it. |
| `fn RecursiveSolverState::peek_state(&self) -> Option<&(usize, u32, GapTensorNode)>` | Peek at the top of the path stack without removing it. |
| `fn RecursiveSolverState::path_depth(&self) -> usize` | Get the path stack length. |
| `fn RecursiveSolverState::add_constraint(&mut self, constraint: GapConstraint)` | Add a constraint to the accumulated constraints. |
| `fn RecursiveSolverState::constraints(&self) -> &[GapConstraint]` | Get all accumulated constraints. |
| `fn RecursiveSolverState::mark_constraint_satisfied(&mut self, idx: usize)` | Mark a constraint as satisfied. |
| `fn RecursiveSolverState::unsatisfied_constraint_count(&self) -> usize` | Count unsatisfied constraints. |
| `fn RecursiveSolverState::set_terminal_node(&mut self, node: GapTensorNode)` | Set the terminal node reached during solving. |
| `fn RecursiveSolverState::terminal_node(&self) -> Option<GapTensorNode>` | Get the terminal node (if set). |
| `fn RecursiveSolverState::set_contradictory(&mut self)` | Mark the state as contradictory. |
| `fn RecursiveSolverState::is_contradictory(&self) -> bool` | Check if the state is contradictory. |
| `fn RecursiveSolverState::clear_contradiction(&mut self)` | Clear contradictory state (e.g., after backtracking). |
| `fn RecursiveSolverState::snapshot(&self) -> SolverStateSnapshot` | Get a snapshot of the current state for inspection. |
| `struct SolverStateSnapshot` | A snapshot of the recursive solver state for inspection/logging. |

## Tests

`cargo test -p recursive_solver_state` runs 9 unit tests.
