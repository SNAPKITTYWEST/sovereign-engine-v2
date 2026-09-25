# `recursion_depth_management` (C032)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Manage recursion depth stack, backtrack points, and depth limits.
Provides a stack of depth markers and allows efficient depth-based backtracking.

## Dependencies

- [C031 `recursive_solver_state`](../C031/README.md)

## Public API

| Item | Description |
|---|---|
| `struct DepthMarker` | A marker for a backtrack point at a specific depth. |
| `struct DepthManager` | Manages recursion depth and backtrack points. |
| `fn DepthManager::new() -> Self` | Create a new depth manager. |
| `fn DepthManager::with_max_depth(max_depth: u32) -> Self` | Create with a custom maximum depth. |
| `fn DepthManager::current_depth(&self) -> u32` | Get the current depth. |
| `fn DepthManager::max_allowed_depth(&self) -> u32` | Get the maximum allowed depth. |
| `fn DepthManager::can_increase_depth(&self) -> bool` | Check if we can increase depth. |
| `fn DepthManager::increase_depth(&mut self) -> Option<u32>` | Increase depth and return the new depth. |
| `fn DepthManager::decrease_depth(&mut self) -> Option<u32>` | Decrease depth and return the previous depth. |
| `fn DepthManager::mark_backtrack_point(&mut self, cursor: usize)` | Mark a backtrack point at the current depth. |
| `fn DepthManager::last_backtrack_point(&self) -> Option<(u32, usize)>` | Get the most recent backtrack point. |
| `fn DepthManager::pop_backtrack_point(&mut self) -> Option<(u32, usize)>` | Pop and return the most recent backtrack point. |
| `fn DepthManager::backtrack_points_at_depth(&self, depth: u32) -> Vec<(u32, usize)>` | Get all backtrack points at or above a given depth. |
| `fn DepthManager::clear_backtrack_points_at_depth(&mut self, depth: u32)` | Clear all backtrack points at or above a given depth. |
| `fn DepthManager::depth_stack(&self) -> &[u32]` | Get the full depth stack. |
| `fn DepthManager::depth_stack_len(&self) -> usize` | Get the depth stack length. |
| `fn DepthManager::is_top_level(&self) -> bool` | Check if we're at depth 0 (top level). |
| `fn DepthManager::reset(&mut self)` | Reset to depth 0 and clear backtrack points. |
| `fn DepthManager::depth_path(&self) -> Vec<u32>` | Get the path from top-level to current depth. |
| `fn DepthManager::has_visited_depth(&self, depth: u32) -> bool` | Check if a specific depth has been visited. |
| `struct RecursionContext` | Utility to manage nested recursion with automatic depth tracking. |
| `fn RecursionContext::new() -> Self` | Create a new recursion context. |
| `fn RecursionContext::enter(&mut self) -> Option<RecursionDepthGuard<'_>>` | Enter a new recursion level. |
| `fn RecursionContext::context_id(&self) -> u64` | Identifier of this context. |
| `fn RecursionContext::manager(&self) -> &DepthManager` | Get the current manager. |
| `fn RecursionContext::manager_mut(&mut self) -> &mut DepthManager` | Get a mutable reference to the manager. |
| `struct RecursionDepthGuard<'a>` | RAII guard for one recursion level: dropping it restores the depth the context had before `RecursionContext::enter`. |
| `fn RecursionDepthGuard::depth(&self) -> u32` | Depth of this level. |
| `fn RecursionDepthGuard::enter(&mut self) -> Option<RecursionDepthGuard<'_>>` | Enter a nested level. |
| `fn RecursionDepthGuard::manager(&self) -> &DepthManager` | The depth manager (read-only while the guard is alive). |

## Tests

`cargo test -p recursion_depth_management` runs 12 unit tests.
