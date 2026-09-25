# recursive_solver_transition (C035)

## What it does
The transition engine: applies state-changing operators (`Advance`, `Retreat`, `ApplyConstraint`, `Backtrack`, `Terminal`) to a bundle of `(RecursiveSolverState, DepthManager, RecursiveSolverCursor)`, recording a `TransitionResult` for each.

## Public API
- `TransitionOperator` enum (5 variants).
- `TransitionResult { operator, success, message, new_cursor_pos }`, with `success()`/`failure()` constructors.
- `SolverTransitionEngine::new(state, depth_manager, cursor)`.
- `transition_advance()`, `transition_retreat()`, `transition_apply_constraint(&GapConstraint)`, `transition_backtrack()`, `transition_terminal(GapTensorNode)`.
- `execute_transitions(&[TransitionOperator]) -> Vec<TransitionResult>` — batch runner; note it synthesizes placeholder inputs internally (`GapConstraint::unbounded()`, `GapTensorNode::NIL`) for the `ApplyConstraint`/`Terminal` ops rather than taking per-op parameters.
- Accessors: `state()`, `cursor()`, `cursor_mut()`, `transitions()`, `depth_manager()`.

## Pipeline position
Wires together C031 (state), C032 (depth manager), C033 (cursor), C027 (`gap_constraint_satisfaction::GapConstraint`, the *other* constraint type — see C031's README note), and C001 (`GapTensorNode`). This is the central orchestrator that C037 (backtracking), C039 (solution path), and C040 (trace) build on top of.

## Notes / gaps
- **Gap:** `execute_transitions` always applies `GapConstraint::unbounded()` for every `ApplyConstraint` op in a batch and `GapTensorNode::NIL` for every `Terminal` op — it cannot express "apply *this specific* constraint at step N" through the batch API. Real constraint/terminal-node application must go through the single-op methods directly; the batch convenience method is effectively decorative for those two operators.
- `transition_apply_constraint` on failure marks the cursor position invalid AND sets the state contradictory as a side effect — a caller inspecting only the returned `TransitionResult.success` won't see that two other pieces of mutable state changed.
- `transition_backtrack` relies on `state.pop_state()` (from C031's path stack), not on `DepthManager`'s own backtrack-point stack (C032) — two backtracking mechanisms exist in the pipeline and this crate uses only one of them; C037 is where the other one (`BacktrackManager`) lives, so the two are not yet unified.
- 6 unit tests.
