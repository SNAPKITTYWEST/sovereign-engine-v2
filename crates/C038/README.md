# recursion_contradiction_detection (C038)

## What it does
Detects four classes of solver contradictions beyond simple constraint failure: unsatisfiable/range/modular constraint violations on a single gap, conflicting constraints within a state, dead ends (no unvisited positions with unsatisfied constraints remaining), and inconsistent state (contradictory + terminal + unsatisfied simultaneously).

## Public API
- `Contradiction { contradiction_type, position, gap_value, constraint }`.
- `ContradictionType` enum: `UnsatisfiableConstraint`, `RangeViolation`, `ModularViolation`, `ConflictingConstraints`, `DeadEnd`, `InconsistentState` — implements `Display`.
- `ContradictionDetector::new()` — seeded with one `GapConstraint::unbounded()`.
- `add_constraint()`, `check_gap(position, gap) -> Option<Contradiction>` — classifies violation type.
- Associated fns (no `&self`): `check_conflicting_constraints(state)`, `check_dead_end(cursor, state)`, `check_inconsistent_state(state)`.
- `full_check(state, cursor) -> Vec<Contradiction>` — runs the three structural checks (not `check_gap`) and aggregates.
- `contradictions()`, `contradiction_count()`, `clear()`, `has_contradiction()`.
- `ContradictionStats` — tally by type name with `most_common_type`.

## Pipeline position
Depends on `gap_constraint_satisfaction` (C027, the modulus-bearing `GapConstraint` — same name collision as flagged in C031/C035), `recursive_solver_state` (C031), `recursive_solver_cursor` (C033). Complements C036 (base-case detection) as the other half of "when does the solver need to stop/retry" logic; feeds into C040's trace via `EventType::Contradiction`.

## Notes / gaps
- **Note:** `check_gap`'s classification logic is a chain of `if`/`else if` that infers *why* a constraint failed after the fact (range vs. modular vs. generic unsatisfiable) rather than having `GapConstraint::satisfies` itself report the failure reason — this reconstruction can misclassify if a gap fails both a range and modulus check simultaneously (range wins by branch order).
- `full_check` does *not* call `check_gap` — it only aggregates the three structural checks. A caller wanting single-gap constraint violations must call `check_gap` separately; this split isn't documented and could surprise someone expecting `full_check` to be exhaustive.
- 6 unit tests; `check_conflicting_constraints`'s O(n²) pairwise scan over `state.constraints()` is fine at expected scale but worth knowing if constraint counts grow large.
