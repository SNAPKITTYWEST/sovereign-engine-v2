# `recursive_solver_transition` (C035)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

State transitions during recursive solving. Handles operator application,
constraint satisfaction checks, and state mutations.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C027 `gap_constraint_satisfaction`](../C027/README.md)
- [C031 `recursive_solver_state`](../C031/README.md)
- [C032 `recursion_depth_management`](../C032/README.md)
- [C033 `recursive_solver_cursor`](../C033/README.md)

## Public API

| Item | Description |
|---|---|
| `enum TransitionOperator` | Represents a transition operation between solver states. |
| `enum TransitionStep` | A transition together with the data it needs. |
| `struct TransitionResult` | Result of a transition operation. |
| `fn TransitionResult::success(operator: TransitionOperator, message: String, new_pos: Option<usize>) -> Self` | Create a successful transition result. |
| `fn TransitionResult::failure(operator: TransitionOperator, message: String) -> Self` | Create a failed transition result. |
| `struct SolverTransitionEngine` | Manages state transitions during recursive solving. |
| `fn SolverTransitionEngine::new(state: RecursiveSolverState, depth_manager: DepthManager, cursor: RecursiveSolverCursor) -> Self` | Create a new transition engine. |
| `fn SolverTransitionEngine::transition_advance(&mut self) -> TransitionResult` | Apply an advance transition. |
| `fn SolverTransitionEngine::transition_retreat(&mut self) -> TransitionResult` | Apply a retreat transition. |
| `fn SolverTransitionEngine::transition_apply_constraint(&mut self, constraint: &GapConstraint) -> TransitionResult` | Apply a constraint at the current position. |
| `fn SolverTransitionEngine::transition_backtrack(&mut self) -> TransitionResult` | Apply a backtrack transition. |
| `fn SolverTransitionEngine::transition_terminal(&mut self, node: GapTensorNode) -> TransitionResult` | Mark current position as terminal. |
| `fn SolverTransitionEngine::execute_step(&mut self, step: &TransitionStep) -> TransitionResult` | Execute one step. |
| `fn SolverTransitionEngine::execute_steps(&mut self, steps: &[TransitionStep]) -> Vec<TransitionResult>` | Execute a sequence of steps, each carrying its own data. |
| `fn SolverTransitionEngine::execute_transitions(&mut self, ops: &[TransitionOperator]) -> Vec<TransitionResult>` | Execute bare operators. |
| `fn SolverTransitionEngine::state(&self) -> &RecursiveSolverState` | Get the current state. |
| `fn SolverTransitionEngine::cursor(&self) -> &RecursiveSolverCursor` | Get the current cursor. |
| `fn SolverTransitionEngine::cursor_mut(&mut self) -> &mut RecursiveSolverCursor` | Get a mutable reference to the cursor. |
| `fn SolverTransitionEngine::transitions(&self) -> &[TransitionResult]` | Get transition history. |
| `fn SolverTransitionEngine::depth_manager(&self) -> &DepthManager` | Get the depth manager. |

## Tests

`cargo test -p recursive_solver_transition` runs 9 unit tests.
