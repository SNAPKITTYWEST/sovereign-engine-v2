# `recursion_backtracking` (C037)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Backtracking mechanisms for recursive solver. Manages backtrack stacks,
checkpoint saving, and state restoration during constraint satisfaction failures.

## Dependencies

- [C031 `recursive_solver_state`](../C031/README.md)
- [C032 `recursion_depth_management`](../C032/README.md)
- [C035 `recursive_solver_transition`](../C035/README.md)

## Public API

| Item | Description |
|---|---|
| `struct Checkpoint` | A checkpoint that can be restored. |
| `fn Checkpoint::new(state: RecursiveSolverState, depth: u32, id: u64) -> Self` | Create a new checkpoint. |
| `enum BacktrackStrategy` | Backtrack strategy for recovery. |
| `struct BacktrackManager` | Manages backtracking during recursive solving. |
| `fn BacktrackManager::new() -> Self` | Create a new backtrack manager. |
| `fn BacktrackManager::save_checkpoint(&mut self, state: RecursiveSolverState, depth: u32) -> u64` | Save a checkpoint. |
| `fn BacktrackManager::last_checkpoint(&self) -> Option<&Checkpoint>` | Get the most recent checkpoint. |
| `fn BacktrackManager::pop_checkpoint(&mut self) -> Option<Checkpoint>` | Pop and return the most recent checkpoint. |
| `fn BacktrackManager::checkpoint_by_id(&self, id: u64) -> Option<&Checkpoint>` | Get a checkpoint by ID. |
| `fn BacktrackManager::checkpoint_count(&self) -> usize` | Get the number of checkpoints. |
| `fn BacktrackManager::record_failed_branch(&mut self, checkpoint_id: u64, reason: String)` | Record a failed branch. |
| `fn BacktrackManager::failed_branches(&self) -> &[(usize, String)]` | Get failed branch records. |
| `fn BacktrackManager::backtrack(&mut self, strategy: BacktrackStrategy) -> Option<Checkpoint>` | Backtrack using a specific strategy. |
| `fn BacktrackManager::reset(&mut self)` | Clear all checkpoints and failed branches. |
| `fn BacktrackManager::stack_depth(&self) -> usize` | Get checkpoint stack depth. |
| `fn BacktrackManager::can_backtrack(&self) -> bool` | Check if there are saved checkpoints to backtrack to. |
| `struct BacktrackContext` | Combines backtracking with depth management. |
| `fn BacktrackContext::new(backtrack: BacktrackManager, depth_mgr: DepthManager) -> Self` | Create a new backtrack context. |
| `fn BacktrackContext::save(&mut self, state: RecursiveSolverState) -> u64` | Save the current state. |
| `fn BacktrackContext::backtrack(&mut self, strategy: BacktrackStrategy) -> Option<Checkpoint>` | Perform a backtrack operation. |
| `fn BacktrackContext::total_backtracks(&self) -> usize` | Get total backtrack operations. |
| `fn BacktrackContext::backtrack_manager(&self) -> &BacktrackManager` | Get the backtrack manager. |
| `fn BacktrackContext::depth_manager(&self) -> &DepthManager` | Get the depth manager. |

## Tests

`cargo test -p recursion_backtracking` runs 9 unit tests.
