# gap_constraint_satisfaction (C027)

Defines constraints (range + optional modular residue) on gap sizes and evaluates candidate tuples against them.

## Public API

- Re-exports `gap_deviations` from `gap_absolute_difference` (unused internally, same pattern as C025/C026).
- `GapConstraint { min: u64, max: u64, modulus: Option<(u64, u64)> }`.
  - `unbounded()` — `[0, u64::MAX]`, no modulus.
  - `range(min, max)`.
  - `with_modulus(self, modulus, residue) -> Self` — builder-style, consumes and returns `self`.
  - `satisfies(&self, gap: u64) -> bool` — range check, then `gap % modulus == residue` if a modulus is set.
- `verify_gaps(candidates, constraint) -> Vec<bool>` — per-candidate pass/fail.
- `filter_by_constraint(candidates, constraint) -> Vec<(u64,u64,u64)>` — keep only satisfying candidates.
- `count_satisfying(candidates, constraint) -> usize`.
- `golden_gap_constraint(target_gap, tolerance) -> GapConstraint` — `[target - tolerance, target + tolerance]` using saturating arithmetic (no underflow panic near 0).

## Pipeline role

Depends on `gap_absolute_difference` (C026). This is the constraint vocabulary that `gap_verification` (C028) builds its pass/fail reporting on top of (`verify_gaps`, `filter_by_constraint`, `GapConstraint` are all re-exported there).

## Invariants / design notes

- `golden_gap_constraint`'s use of `saturating_sub`/`saturating_add` is a deliberate, correct guard against `u64` underflow when `tolerance > target_gap` (would otherwise panic in debug or wrap in release) — a small but real correctness detail worth preserving in any refactor.
- `GapConstraint` fields are all `pub`, so a caller can construct or mutate one directly instead of using the builder methods — the builder pattern (`with_modulus`) is a convenience, not an enforced invariant boundary.
- `satisfies` checks range first, then modulus — order doesn't affect correctness here since both are independent AND'd conditions, but it does mean range failures short-circuit before a (cheaper) modulus check would run, which is a minor and probably immaterial performance note.

## Gaps / TODOs

- No test for `count_satisfying`, despite it being public API.
- The unused `gap_deviations` re-export (dead import, same recurring pattern seen in C025/C026) suggests this crate family may have been scaffolded from a template that always re-exports a "primary" symbol from its dependency without checking whether it's actually used.
