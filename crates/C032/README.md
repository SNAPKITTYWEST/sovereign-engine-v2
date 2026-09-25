# recursion_depth_management (C032)

## What it does
Manages recursion depth as an explicit stack (not just a counter) plus a separate stack of backtrack points `(depth, cursor)`. Also provides an RAII-flavored `RecursionContext`/`RecursionDepthGuard` pair for scoped depth tracking.

## Public API
- `DepthManager::new()` / `with_max_depth(u32)`.
- `current_depth()`, `max_allowed_depth()`, `can_increase_depth()`, `increase_depth() -> Option<u32>`, `decrease_depth() -> Option<u32>`.
- Backtrack points: `mark_backtrack_point(cursor)`, `last_backtrack_point()`, `pop_backtrack_point()`, `backtrack_points_at_depth(depth)`, `clear_backtrack_points_at_depth(depth)`.
- Stack introspection: `depth_stack()`, `depth_stack_len()`, `is_top_level()`, `depth_path()`, `has_visited_depth(depth)`, `reset()`.
- `RecursionContext` wraps a `DepthManager`; `enter() -> Option<RecursionDepthGuard>` increases depth and returns a guard exposing `depth()`. Note: the guard does **not** auto-decrement on `Drop` — it's guard-shaped but not actually RAII (no `Drop` impl).
- `DepthMarker { depth, stack_index }` is defined but not currently wired into any method — appears to be a planned but unused type.

## Pipeline position
Depends only on `recursive_solver_state` (C031) for the `MAX_RECURSION_DEPTH` constant. Used by C035 (transition engine), C037 (backtracking context), C039/C040 indirectly.

## Notes / gaps
- **Gap:** `RecursionDepthGuard` has the shape of an RAII guard (`enter()`/guard) but lacks a `Drop` impl, so depth is never automatically decreased when a guard goes out of scope — callers must call `manager_mut().decrease_depth()` manually. This is a latent correctness trap for anyone assuming RAII semantics from the name.
- `DepthMarker` is dead code (unused struct) — either finish wiring it in or remove it.
- 9 unit tests, no stubs otherwise.
