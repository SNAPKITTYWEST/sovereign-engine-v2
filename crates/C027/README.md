# `gap_constraint_satisfaction` (C027)

Tier 2 — prime/gap engine. *Generated from the crate source; regenerate after API changes.*

Constraint satisfaction for prime gap verification.

## Dependencies

- [C026 `gap_absolute_difference`](../C026/README.md)

## Re-exports

- `gap_absolute_difference::gap_deviations`

## Public API

| Item | Description |
|---|---|
| `struct GapConstraint` | A constraint on a gap. |
| `fn GapConstraint::unbounded() -> Self` | Create an unbounded constraint. |
| `fn GapConstraint::range(min: u64, max: u64) -> Self` | Create a range constraint. |
| `fn GapConstraint::with_modulus(mut self, modulus: u64, residue: u64) -> Self` | Add modular constraint. |
| `fn GapConstraint::satisfies(&self, gap: u64) -> bool` | Check if a gap satisfies this constraint. |
| `fn verify_gaps(candidates: &[(u64, u64, u64)], constraint: &GapConstraint) -> Vec<bool>` | Verify gaps against a constraint. |
| `fn filter_by_constraint(candidates: Vec<(u64, u64, u64)>, constraint: &GapConstraint) -> Vec<(u64, u64, u64)>` | Filter candidates that satisfy a constraint. |
| `fn count_satisfying(candidates: &[(u64, u64, u64)], constraint: &GapConstraint) -> usize` | Count how many gaps satisfy the constraint. |
| `fn golden_gap_constraint(target_gap: u64, tolerance: u64) -> GapConstraint` | Create a "golden gap" constraint for primes following a specific pattern. |

## Tests

`cargo test -p gap_constraint_satisfaction` runs 6 unit tests.
