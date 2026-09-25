# recursive_solver_state (C031)

## What it does
Core state machine for the recursive gap-sequence solver. Tracks cursor position, recursion depth, a path stack for backtracking, accumulated `GapConstraint`s, an optional terminal node, and a contradiction flag.

## Public API
- `RecursiveSolverState` — the state struct. `new()`/`Default`.
- Cursor: `cursor()`, `set_cursor()`, `advance_cursor()`.
- Depth: `depth()`, `increase_depth()`, `decrease_depth()`, `exceeds_max_depth()` (against `MAX_RECURSION_DEPTH = 100`).
- Path stack: `push_state(GapTensorNode)`, `pop_state()`, `peek_state()`, `path_depth()`.
- Constraints: `GapConstraint { position, min_prime, max_prime, gap_size, is_satisfied }`, `add_constraint()`, `constraints()`, `mark_constraint_satisfied(idx)`, `unsatisfied_constraint_count()`.
- Terminal/contradiction: `set_terminal_node()`, `terminal_node()`, `set_contradictory()`, `is_contradictory()`, `clear_contradiction()`.
- `snapshot() -> SolverStateSnapshot` — cheap inspection struct for logging without cloning the full state.

## Pipeline position
Depends on `gap_tensor_core` (C001) for `GapTensorNode` and `gap_tensor_trace` (C010, declared but currently unused directly). It is the foundational state type consumed by nearly every other crate in the recursive-solver layer (C032–C040): depth management, cursor, transition, backtracking, contradiction detection, and trace all hold or mutate a `RecursiveSolverState`.

## Notes
- `GapConstraint` here is a local, simpler struct distinct from `gap_constraint_satisfaction::GapConstraint` (C027) used downstream in C035/C038 — same name, different shape (bounds vs. modulus). Don't conflate them when reading transition code.
- `MAX_RECURSION_DEPTH` is a crate-level constant reused by C032's `DepthManager` default.
- No stubs; all methods are implemented and covered by 8 unit tests.
