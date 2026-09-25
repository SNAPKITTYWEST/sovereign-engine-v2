# projective_module_definition (C045)

## What it does
Defines projective (= free, since the pipeline works over a PID) modules and homomorphisms between them as integer matrices, plus a `FreeResolution` container for sequences of modules and connecting differentials. This is the module-theoretic foundation for the Krull-dimension/commutative-algebra layer's resolutions.

## Public API
- `ProjectiveModule { rank, degree, generators (private) }` — `new(rank, degree)` (auto-names `p_0..`), `with_generators()`, `generator_name()`, `is_free()` (always `true` — see notes), `len()`, `is_empty()`.
- `ProjectiveModuleHomomorphism { source, target, matrix (private, target_rank × source_rank) }` — `new()` (panics on dimension mismatch), `entry(i, j)`, `apply(&ChainElement) -> ChainElement`, `compose(&self, &other) -> Self` (`self` then `other`, i.e. `other ∘ self`), `is_zero()`, `is_identity()` (panics if source/target rank differ), `rank()` (Gaussian-elimination rank over the integers — see gap below).
- `FreeResolution::new()`, `add_module()`, `add_differential()` (panics if fewer than 2 modules present), `module_at()`, `differential_at()`, `len()`, `is_empty()`.

## Pipeline position
Depends on `chain_complex_shape` (C041, unused — dead dependency) and `chain_complex_types` (C042) for `ChainElement`. Feeds `projective_resolution` (C046), which builds actual resolutions, and is used throughout the Tor-functor sub-layer (C051+) since Tor is computed from projective resolutions.

## Notes / gaps
- **Correctness gap — `rank()` is not integer-matrix rank:** the Gaussian elimination in `rank()` does plain field-style elimination (`mat[r][c] = mat[r][c] * pivot - factor * mat[current_row][c]`) without ever dividing back out, which blows up coefficient magnitudes on repeated eliminations and, more importantly, computes rank over the *rationals* (treating nonzero as invertible), not the correct notion of rank for a **Z**-module homomorphism. Over `Z`, matrix rank (in the sense relevant to projective/free modules) still coincides with the rational rank as a dimension count, so the final integer `rank` count is likely fine, but intermediate arithmetic can overflow `i64` for larger matrices since it never reduces by GCD. Worth flagging for a numerically careful reviewer before this is trusted on large presentations.
- `is_free()` is hardcoded to always return `true` with the module-level comment explaining this is a working assumption specific to PIDs — correct for the stated scope but means the type cannot currently represent a genuinely non-free projective module if the pipeline ever needs one (e.g., over a non-PID base).
- `compose`'s naming (`self.compose(other)` returns `other ∘ self`, i.e., self is applied first) is mathematically standard but easy to get backwards when reading call sites — worth double-checking order at each call site rather than assuming.
- `chain_complex_shape` (C041) is an unused dependency.
- 6 unit tests, including a real composition and rank test.
