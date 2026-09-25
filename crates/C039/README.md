# recursion_solution_path (C039)

## What it does
Records the sequence of `TransitionOperator` applications that constitute one attempted solution, and manages multiple such paths (completed, pruned, in-progress) via `SolutionPathRecorder`.

## Public API
- `SolutionStep { step_number, operator, from_position, to_position, from_depth, to_depth, gap_value, is_solution_branch }`; builder methods `with_gap()`, `mark_solution()`.
- `SolutionPath` — `new()`, `add_step()`, `steps()`, `step_count()`, `mark_complete()`, `is_complete()`, `cost()` (= last step's `to_depth`), `set_constraints_satisfied()`/`constraints_satisfied()`, `final_position()`, `final_depth()`, `format_path() -> String` (human-readable multi-line dump).
- `SolutionPathRecorder::new()` — `record_step()`, `complete_path(constraints_satisfied)`, `prune_path()`, `current_path()`, `completed_paths()`, `pruned_paths()`, `best_path()` (min by `cost`), `stats() -> SolutionStats`, `reset()`.
- `SolutionStats { completed_paths, pruned_paths, best_cost, average_steps }`.

## Pipeline position
Depends on `gap_tensor_trace` (C010, declared, unused), `recursive_solver_state` (C031, declared, unused), `recursive_solver_selection` (C034, declared, unused), and `recursive_solver_transition` (C035) for `TransitionOperator`. This is the only actually-used dependency — the other three are dead weight in Cargo.toml. Feeds `recursive_solver_trace` (C040), which wraps `SolutionPath` into the full execution trace.

## Notes / gaps
- **Gap:** three of four declared dependencies (C010, C031, C034) are unused. The crate is self-contained around `TransitionOperator` alone; it doesn't reference solver state, gap tensors, or selection directly, despite what Cargo.toml implies.
- `SolutionPath::cost()` is defined as the `to_depth` of the *most recently added* step, not a sum or max over all steps — i.e., "cost" here means final depth reached, not total step count or cumulative weight. Worth confirming this matches the intended notion of solution cost before reusing it for path comparison (`best_path()` picks min by this field).
- 9 unit tests.
