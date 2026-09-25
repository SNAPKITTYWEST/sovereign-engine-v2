# `recursion_solution_path` (C039)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Records and manages the solution path during recursive solving.
Captures each transition as part of the final solution sequence.

## Dependencies

- [C010 `gap_tensor_trace`](../C010/README.md)
- [C031 `recursive_solver_state`](../C031/README.md)
- [C034 `recursive_solver_selection`](../C034/README.md)
- [C035 `recursive_solver_transition`](../C035/README.md)

## Public API

| Item | Description |
|---|---|
| `struct SolutionStep` | A step in a solution path. |
| `fn SolutionStep::new(step_number: usize, operator: TransitionOperator, from_pos: usize, to_pos: usize, from_d: u32, to_d: u32) -> Self` | Create a new solution step. |
| `fn SolutionStep::with_gap(mut self, gap: u64) -> Self` | Add gap value to the step. |
| `fn SolutionStep::mark_solution(mut self) -> Self` | Mark as a solution branch. |
| `struct SolutionPath` | A complete solution path consisting of multiple steps. |
| `fn SolutionPath::new() -> Self` | Create a new empty solution path. |
| `fn SolutionPath::add_step(&mut self, step: SolutionStep)` | Add a step to the path. |
| `fn SolutionPath::steps(&self) -> &[SolutionStep]` | Get all steps in the path. |
| `fn SolutionPath::step_count(&self) -> usize` | Get the number of steps. |
| `fn SolutionPath::mark_complete(&mut self)` | Mark path as complete (solution found). |
| `fn SolutionPath::is_complete(&self) -> bool` | Check if this is a complete solution. |
| `fn SolutionPath::cost(&self) -> usize` | Get the cost (depth) of this path. |
| `fn SolutionPath::set_constraints_satisfied(&mut self, count: usize)` | Set the number of constraints satisfied. |
| `fn SolutionPath::constraints_satisfied(&self) -> usize` | Get constraints satisfied. |
| `fn SolutionPath::final_position(&self) -> Option<usize>` | Get the final position reached. |
| `fn SolutionPath::final_depth(&self) -> Option<u32>` | Get the final depth reached. |
| `fn SolutionPath::format_path(&self) -> String` | Create a formatted string representation. |
| `struct SolutionPathRecorder` | Records and manages solution paths during solving. |
| `fn SolutionPathRecorder::new() -> Self` | Create a new recorder. |
| `fn SolutionPathRecorder::record_step(&mut self, step: SolutionStep)` | Add a step to the current path. |
| `fn SolutionPathRecorder::complete_path(&mut self, constraints_satisfied: usize)` | Complete the current path. |
| `fn SolutionPathRecorder::prune_path(&mut self)` | Prune the current path (dead end). |
| `fn SolutionPathRecorder::current_path(&self) -> &SolutionPath` | Get the current path. |
| `fn SolutionPathRecorder::completed_paths(&self) -> &[SolutionPath]` | Get completed solution paths. |
| `fn SolutionPathRecorder::pruned_paths(&self) -> &[SolutionPath]` | Get pruned paths. |
| `fn SolutionPathRecorder::best_path(&self) -> Option<&SolutionPath>` | Get the best completed path (shortest cost). |
| `fn SolutionPathRecorder::stats(&self) -> SolutionStats` | Get solution statistics. |
| `fn SolutionPathRecorder::reset(&mut self)` | Reset the recorder. |
| `struct SolutionStats` | Statistics about solution paths found. |

## Tests

`cargo test -p recursion_solution_path` runs 10 unit tests.
