# chain_complex_shape (C041)

## What it does
Defines the graded "shape" of a chain complex: which integer degrees have nonzero free modules and their ranks, independent of any actual differential or element data.

## Public API
- `MAX_CHAIN_RANK: usize = 1024`.
- `ChainDegreeShape { degree, rank, generators }` — `new(degree, rank)` (panics if `rank > MAX_CHAIN_RANK`, auto-names generators `gen_0..gen_{rank-1}`), `with_generators()`, `is_empty()`, `len()`.
- `ChainComplexShape { min_degree, max_degree, degrees, total_rank (private) }` — `new()`, `add_degree()` (upsert by degree, keeps `degrees` sorted, maintains running `total_rank`), `rank_at()`, `degree_shape()`, `is_empty()`, `len()`, `total_rank()`, `free_module(degree)` (rank-1 convenience), `from_ranks(Vec<(i32, usize)>)`.

## Pipeline position
Depends on `gap_tensor_core` (C001, unused in code) and `gap_tensor_shape` (C004, unused in code) — both dead dependencies; the crate is entirely self-contained arithmetic on degree/rank pairs with no actual reference to gap-tensor types. This is the foundational shape type for the entire homological-algebra layer: C042 (types), C043 (differential), C045 (projective modules), and everything downstream in C041–C060 that carries a `ChainComplexShape` field.

## Notes / gaps
- **Gap:** both declared dependencies are unused; this crate has zero coupling to the gap-tensor/prime layer despite Cargo.toml implying otherwise.
- `ChainComplexShape::new()` initializes `max_degree = -1` as an "empty" sentinel while `min_degree = 0` — asymmetric sentinel values. Fine as implemented (both get overwritten on first `add_degree`), but a caller reading `min_degree`/`max_degree` before adding any degree would see `(0, -1)`, an inverted range that could look like a bug if not documented — which this README now does.
- `add_degree`'s upsert logic recomputes `total_rank` by subtracting old rank then adding new — correct but does a linear `find` scan each call; fine at `MAX_CHAIN_RANK` scale (1024) but O(n) per insert rather than O(1) with a map.
- 5 unit tests.
