# differential_operator (C043)

## What it does
Represents the differential `d: C_n -> C_{n-1}` of a chain complex as a sparse matrix per source degree, and applies it to generators, `ChainElement`s, and full `Chain`s. Does **not** itself verify `d² = 0` — that's delegated to C044 by design (see its own doc comment: "verified separately").

## Public API
- `DifferentialOperator::new(ChainComplexShape)`.
- `set_generator_image(source_degree, source_gen, target_degree, target_image: Vec<(usize, i64)>)` — panics unless `source_degree - 1 == target_degree`; silently drops zero-coefficient entries.
- `apply_to_generator(degree, gen_idx) -> ChainElement`, `apply_to_element(&ChainElement) -> ChainElement`, `apply(&Chain) -> Chain`.
- `matrix_at(degree)`, `source_rank(degree)`, `target_rank(degree)` (= `source_rank(degree - 1)`).
- `is_consistent()` — necessary-but-not-sufficient sanity check that all stored images land at the expected target degree (a bookkeeping check, not an algebraic one).
- `to_dense_matrix(degree) -> Vec<Vec<i64>>` — dense `target_rank × source_rank` matrix.
- `support_degrees()` — sorted list of degrees with a nonzero matrix set.

## Pipeline position
Depends on `chain_complex_shape` (C041) and `chain_complex_types` (C042). Central to the homological layer: consumed by `differential_squared_zero` (C044), `homology_computation` (C048), `exactness_predicate` (C047), and `resolution_tensored` (C053) in the Tor sub-layer.

## Notes / gaps
- **Gap — silent truncation:** `to_dense_matrix` skips any `target_gen >= target_rank` (`if target_gen < target_rank`) rather than panicking or returning an error — an out-of-range image set via `set_generator_image` (which does *not* validate against `shape.rank_at`) will silently vanish from the dense matrix. `set_generator_image` has no bounds check against the shape's declared rank at all, so it's possible to define a differential inconsistent with its own `ChainComplexShape` and only discover it (partially) when converting to dense form.
- `is_consistent()` only checks recorded target degrees match `source_degree - 1`; since `set_generator_image` already asserts this at insertion time, `is_consistent()` is currently unreachable-false in normal use — it would only catch a bug if the internal `matrices` map were mutated some other way (it can't be, being private). Essentially a defensive check against future internal changes rather than something a caller needs today.
- 5 unit tests covering construction, application, consistency, and dense-matrix conversion.
