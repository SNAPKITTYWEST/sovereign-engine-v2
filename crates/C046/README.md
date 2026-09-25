# projective_resolution (C046)

## What it does
Represents a projective resolution `... -> P_2 -> P_1 -> P_0 -> M -> 0` as a sequence of `ProjectiveModule`s, connecting `ProjectiveModuleHomomorphism` differentials, and an optional augmentation `P_0 -> M`. Provides kernel/image extraction and an exactness check, plus two canned constructors and a conversion to `ChainComplexShape`.

## Public API
- `ProjectiveResolution::new()` — `add_module()`, `add_differential()`, `set_augmentation()`, `module_at()`, `differential_at()`, `differentials_len()`, `len()`, `is_empty()`, `rank_at()`.
- `kernel_at(i)` — brute-force basis-vector test: for each generator of `P_i`, checks whether `d_i(gen) == 0`; returns the zero-image basis elements (only detects kernel vectors that are *single basis generators*, not general linear combinations — see gap below).
- `image_at(i)` — images of all `P_{i+1}` basis generators under `d_{i+1}`.
- `is_exact_at(i)` / `verify_exactness()` — see gap below, this is explicitly a simplified/inclusion-style check, not true exactness.
- `mark_exact()`, `is_marked_exact()`.
- `free_of_rank_one()` — canned rank-1 resolution with identity augmentation, pre-marked exact.
- `quotient_resolution(n)` — canned `n`-term resolution modeling `Z[x]/(x^n)`; differentials are all `[[1]]` (see gap).
- `to_chain_shape() -> ChainComplexShape` — maps `P_i` to degree `-i`.
- `summary() -> String`.

## Pipeline position
Depends on `chain_complex_shape` (C041), `chain_complex_types` (C042), `differential_squared_zero` (C044, unused — dead dependency), `projective_module_definition` (C045). Feeds `resolution_certification` (C049), `homological_tests_integration` (C050), and the Tor-functor sub-layer (`tor_functor_definition` C051, `tor_chain_complex_interface` C059).

## Notes / gaps
- **Gap — `kernel_at` is not a real kernel:** it only tests whether individual basis generators map to zero, missing any kernel element that's a nontrivial linear combination of generators (e.g., `2·g0 - g1` mapping to zero while neither `g0` nor `g1` alone does). This under-approximates the true kernel.
- **Gap — `is_exact_at` is explicitly a stub**, per its own comment: "For simplicity, check that images span the expected dimension... A full check would require linear algebra over integers." The actual boolean logic (`!kernels.is_empty() && !images.is_empty() || kernels.is_empty()`) is close to vacuously true — it fails only when there's a nonempty kernel and an *empty* image, which is a weak necessary condition, not `ker = im`. Anyone relying on `verify_exactness()` to certify real exactness will get false positives.
- **Gap:** `quotient_resolution(n)`'s differentials are all literally `vec![vec![1]]` ("Multiplication by 1 (simplified)") rather than encoding multiplication by `x` as its own doc comment claims — the canned example doesn't actually model `Z[x]/(x^n)`'s resolution; it's a placeholder shape with the right module ranks but the wrong differential.
- `differential_squared_zero` (C044) is an unused dependency — exactness verification here doesn't call into the crate whose entire job is verifying `d²=0`.
- 5 unit tests — none of them exercise a case where `is_exact_at`/`kernel_at` would actually catch a real non-exact sequence, so the weak-check gap above is untested.
