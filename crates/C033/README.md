# `recursive_solver_cursor` (C033)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Cursor management for gap sequence position tracking during recursive solving.
Validates positions against candidate gaps, tracks visited positions, and manages
forward/backward movement through the gap sequence.

## Dependencies

- [C023 `gap_candidate_set`](../C023/README.md)
- [C024 `gap_ordering`](../C024/README.md)
- [C031 `recursive_solver_state`](../C031/README.md)

## Public API

| Item | Description |
|---|---|
| `struct CursorPosition` | Represents a position in a gap sequence with validity information. |
| `fn CursorPosition::new(index: usize, visited: bool, is_valid: bool) -> Self` | Create a new cursor position. |
| `struct RecursiveSolverCursor` | Cursor for navigating through a gap sequence during recursive solving. |
| `fn RecursiveSolverCursor::new(gap_set: GapCandidateSet) -> Self` | A cursor over every consecutive-prime gap of the set (every gap is at least 1). |
| `fn RecursiveSolverCursor::with_min_gap(gap_set: GapCandidateSet, min_gap: u64) -> Self` | A cursor over the consecutive-prime gaps of size at least `min_gap`. |
| `fn RecursiveSolverCursor::from_gaps(gaps: Vec<(u64, u64, u64)>) -> Self` | Create a cursor from a pre-computed list of gaps. |
| `fn RecursiveSolverCursor::position(&self) -> usize` | Get the current position. |
| `fn RecursiveSolverCursor::set_position(&mut self, index: usize) -> bool` | Set the position to an absolute index. |
| `fn RecursiveSolverCursor::advance(&mut self) -> bool` | Advance cursor by one position (if possible). |
| `fn RecursiveSolverCursor::retreat(&mut self) -> bool` | Retreat cursor by one position (if possible). |
| `fn RecursiveSolverCursor::jump_to_end(&mut self)` | Jump to the end of the sequence. |
| `fn RecursiveSolverCursor::jump_to_start(&mut self)` | Jump to the beginning of the sequence. |
| `fn RecursiveSolverCursor::is_at_end(&self) -> bool` | Check if at the end of the sequence. |
| `fn RecursiveSolverCursor::is_at_start(&self) -> bool` | Check if at the start of the sequence. |
| `fn RecursiveSolverCursor::current_gap(&self) -> Option<(u64, u64, u64)>` | Get the current gap (prime1, prime2, gap_size). |
| `fn RecursiveSolverCursor::gap_at(&self, index: usize) -> Option<(u64, u64, u64)>` | Get the gap at a specific position. |
| `fn RecursiveSolverCursor::all_gaps(&self) -> &[(u64, u64, u64)]` | Get all gaps in the sequence. |
| `fn RecursiveSolverCursor::total_gaps(&self) -> usize` | Get the total number of gaps. |
| `fn RecursiveSolverCursor::mark_visited(&mut self, index: usize)` | Mark a position as visited. |
| `fn RecursiveSolverCursor::is_visited(&self, index: usize) -> bool` | Check if a position has been visited. |
| `fn RecursiveSolverCursor::visited_count(&self) -> usize` | Get the number of visited positions. |
| `fn RecursiveSolverCursor::unvisited_positions(&self) -> Vec<usize>` | Get unvisited positions. |
| `fn RecursiveSolverCursor::is_position_valid(&self, index: usize) -> bool` | Check if a position is valid. |
| `fn RecursiveSolverCursor::mark_invalid(&mut self, index: usize)` | Mark a position as invalid. |
| `fn RecursiveSolverCursor::valid_count(&self) -> usize` | Get the number of valid positions. |
| `fn RecursiveSolverCursor::current_position_info(&self) -> CursorPosition` | Get the current cursor position info. |
| `fn RecursiveSolverCursor::reset(&mut self)` | Reset cursor to start and clear visited/valid states. |
| `fn RecursiveSolverCursor::next_unvisited(&self) -> Option<usize>` | Get the closest unvisited position going forward. |
| `fn RecursiveSolverCursor::prev_unvisited(&self) -> Option<usize>` | Get the closest unvisited position going backward. |

## Tests

`cargo test -p recursive_solver_cursor` runs 12 unit tests.
