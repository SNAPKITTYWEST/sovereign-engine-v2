# recursion_backtracking (C037)

## What it does
A second, independent backtracking mechanism (distinct from `RecursiveSolverState`'s path stack in C031): explicit checkpoint save/restore over full `RecursiveSolverState` snapshots, with four strategies (`LastCheckpoint`, `ToDepth`, `NSteps`, `ToRoot`) and a failed-branch log.

## Public API
- `Checkpoint { state, depth, id }`.
- `BacktrackStrategy` enum (4 variants).
- `BacktrackManager::new()`; `save_checkpoint(state, depth) -> id`, `last_checkpoint()`, `pop_checkpoint()`, `checkpoint_by_id(id)`, `checkpoint_count()`.
- `record_failed_branch(checkpoint_id, reason)`, `failed_branches()`.
- `backtrack(strategy) -> Option<Checkpoint>` — dispatches on strategy.
- `reset()`, `stack_depth()`, `can_backtrack()`.
- `BacktrackContext` — pairs a `BacktrackManager` with a `DepthManager` (C032) and counts total backtracks performed; `save()`, `backtrack()`, `total_backtracks()`, accessors.

## Pipeline position
Depends on `recursive_solver_state` (C031) and `recursion_depth_management` (C032). This is the second of two backtracking mechanisms in the layer — see C035's note about `transition_backtrack` using the state's own path stack instead of this crate. Nothing in C031–C060 currently imports `recursion_backtracking`, so it appears to be an alternate/unused strategy relative to the one actually wired into the transition engine.

## Notes / gaps
- **Gap — architectural duplication:** this crate and C031's `path_stack`/`pop_state()` are two separate, non-interoperating backtracking implementations. `BacktrackManager` stores full-state clones per checkpoint (heavier) vs. C031's `(cursor, depth, node)` tuples (lighter). Worth deciding which is canonical, or documenting why both exist.
- `BacktrackStrategy::ToDepth` pops checkpoints one at a time in a `while let` loop with an early return inside — correct but slightly awkward control flow; the loop body's `self.checkpoints.pop()` on the non-matching branch discards checkpoints without returning them, which is intentional (skipping past them) but easy to misread as a bug at a glance.
- `BacktrackStrategy::ToRoot` clones `checkpoints.first()` before clearing — necessary since `clear()` would otherwise invalidate the reference; fine, just note it's an O(state size) clone.
- 8 unit tests, no dead dependencies.
