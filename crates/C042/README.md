# chain_complex_types (C042)

## What it does
Element-level data types for chain complexes: `ChainElement` (a sparse formal Z-linear combination of generators at one fixed degree) and `Chain` (a formal sum of `ChainElement`s across multiple degrees), with the usual module operations (add, scalar multiply, negate, normalize by GCD).

## Public API
- `ChainElement::new(degree)`, `from_generator(degree, gen_idx, coeff)`, `coeff()`, `set_coeff()` (zero removes the key), `add_coeff()`, `is_zero()`, `support_size()`, `support()` (sorted indices), `add(&other)` (panics on degree mismatch), `scalar_mul()`, `neg()`, `plus(a, &b)` (owned-lhs functional variant), `sorted_coefficients()`, `coeff_gcd()`, `normalize()`.
- `Chain::new()`, `add_element()` (merges into existing degree, drops zero elements), `element_at(degree)`, `support_degrees()` (sorted), `is_zero()`, `support_size()`, `scalar_mul()`, `add(&other)`, `neg()`.
- Private `gcd(i64, i64)` helper (standard Euclidean, `abs()`-normalized).

## Pipeline position
Depends only on `gap_tensor_core` (C001, unused — dead dependency) and `chain_complex_shape` (C041, used only as a doc-adjacent concept — not actually referenced in `lib.rs`, so also effectively unused at the type level, though the degree-graded design mirrors C041's shape model). Consumed directly by `differential_operator` (C043) for `ChainElement`/`Chain`, and by `projective_module_definition` (C045).

## Notes / gaps
- **Gap:** both declared dependencies (C001, C041) go unreferenced in code — `ChainElement`/`Chain` don't hold or validate against a `ChainComplexShape`, so nothing here enforces that a chain's generator indices stay within the rank bounds a `ChainComplexShape` would define. That validation, if it exists, lives elsewhere (e.g. differential operator's `to_dense_matrix` truncates out-of-range target gens silently — see C043).
- `coeff_gcd()` returns `1` for an all-zero/empty element (correct identity for "no normalization needed") rather than `0`, avoiding a divide-by-zero in `normalize()`.
- Sparse `HashMap<usize, i64>` representation is a reasonable choice for chain complexes with mostly-zero differentials/elements at scale; `support()`/`sorted_coefficients()` pay an O(n log n) sort on every call rather than maintaining sorted order — fine unless called in a hot loop.
- 9 unit tests.
