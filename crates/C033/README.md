# recursive_solver_cursor (C033)

## What it does
A cursor over a flattened sequence of candidate gaps `(prime1, prime2, gap_size)`, with per-position `visited`/`valid` bitmaps. Supports forward/backward navigation, jump-to-start/end, and nearest-unvisited-position search in both directions.

## Public API
- `CursorPosition { index, visited, is_valid }`.
- `RecursiveSolverCursor::new(GapCandidateSet)` (pulls `candidates_with_gap(1)` — see gap below) or `from_gaps(Vec<(u64,u64,u64)>)` for direct construction.
- Navigation: `position()`, `set_position()`, `advance()`, `retreat()`, `jump_to_end()`, `jump_to_start()`, `is_at_end()`, `is_at_start()`.
- Access: `current_gap()`, `gap_at(index)`, `all_gaps()`, `total_gaps()`.
- Visited tracking: `mark_visited()`, `is_visited()`, `visited_count()`, `unvisited_positions()`.
- Validity tracking: `is_position_valid()`, `mark_invalid()`, `valid_count()`.
- `current_position_info() -> CursorPosition`, `reset()`, `next_unvisited()`, `prev_unvisited()`.

## Pipeline position
Depends on `gap_candidate_set` (C023) and `gap_ordering` (C024, declared but unused in code — dead dependency) and `recursive_solver_state` (C031, declared but also unused directly in this file). Feeds selection (C034), transition (C035), contradiction detection (C038), and the transition engine's execution loop.

## Notes / gaps
- **Suspicious:** `new()` always calls `gap_set.candidates_with_gap(1)`, hard-coding gap size 1 regardless of what candidate set is passed in. This looks like either a placeholder or a bug — any caller using `new()` with a non-trivial `GapCandidateSet` only ever sees gap-1 candidates. `from_gaps()` is the escape hatch used by all tests, which may be masking this.
- `gap_ordering` and `recursive_solver_state` are declared as dependencies in Cargo.toml but not referenced in `lib.rs` — dead dependency weight.
- 12 unit tests, well covered for navigation edge cases (start/end, unvisited search).
