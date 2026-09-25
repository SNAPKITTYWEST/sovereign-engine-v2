# resolution_certification (C049)

## What it does
A staged certification pipeline for `ProjectiveResolution`s: `Basic -> SquaredZeroVerified -> ExactnessVerified -> FullyCertified`, each stage gated on the previous one, producing a `ResolutionCertificate` with a human-readable trail. **Most of the actual verification logic in this crate is a stub** — see gaps.

## Public API
- `CertificationLevel` enum (5 levels, ordered informally by the builder chain) — `is_fully_certified()`, `to_string()`.
- `ResolutionCertificate { resolution_len, level, modules_checked, differentials_checked, squared_zero_verified, exactness_verified, augmentation_valid, message }` — `new()`, and chained builder methods `mark_basic()`, `mark_squared_zero_verified()`, `mark_exactness_verified()`, `mark_augmentation_valid()` (each only advances `level` if the prior level matches exactly — a state machine encoded as guarded field mutation), `summary()`.
- `ResolutionCertifier` (unit struct), staged checks each calling the previous stage internally:
  - `check_basic()` — verifies non-empty and that `differential_at(0)` exists if `len() > 1`.
  - `verify_squared_zero()` — **does not actually verify d²=0** (see gap).
  - `verify_exactness()` — **does not actually verify exactness** (see gap).
  - `verify_augmentation()` — the one stage that does a real check: `resolution.augmentation.is_some()`.
  - `certify_fully()`, `certify_batch()`, `batch_summary()`.

## Pipeline position
Depends only on `projective_resolution` (C046). Notably does **not** depend on `differential_squared_zero` (C044) or `exactness_predicate` (C047) despite its stated job being exactly what those crates already implement — this crate reinvents (and stubs out) checks that real implementations already exist for elsewhere in the same layer.

## Notes / gaps
- **Major gap — `verify_squared_zero` is a no-op wearing a verification's clothes:** the loop `for i in 0..resolution.differentials_len().saturating_sub(1)` fetches `d_i` and `d_{i+1}` but the body is entirely comments: `// Check: d_i ∘ d_{i+1} = 0 ... For now, we assume it's valid if the structure is right`. `all_squared_zero` is a `let` binding hardcoded to `true` that's never reassigned. This stage **always** reports success regardless of the actual resolution content, provided `check_basic` passed.
- **Major gap — `verify_exactness` is likewise unconditional:** its comment says "For now, mark as verified if d² = 0 and we have the right structure" and it always calls `mark_exactness_verified()` once the (already-fake) squared-zero stage passed. There is no actual kernel/image computation here at all — contrast with C046's `is_exact_at`, which is at least a weak real check, or C047's `ExactnessPredicateChecker`, which does real (if approximate) rank-based checking. This crate's exactness stage is strictly weaker than both.
- **Consequence:** `certify_fully()` will report `FullyCertified` for essentially any resolution that has an augmentation set and passes the cheap structural `check_basic` — it is not currently a meaningful correctness gate despite its name and staged-level design suggesting otherwise. This is the most consequential gap found in the C031-C060 range for anyone trusting "FullyCertified" as a real guarantee.
- **Recommendation:** wire `verify_squared_zero`/`verify_exactness` to actually call `differential_squared_zero::SquaredZeroVerifier` and `exactness_predicate::ExactnessPredicateChecker` (both already exist and do real work) via a `DifferentialOperator` view of the resolution, e.g. through `ProjectiveResolution::to_chain_shape()` (C046) plus a differential built from its `ProjectiveModuleHomomorphism`s.
- 7 unit tests — all pass trivially given the stub logic above; none would fail even against a deliberately non-exact or non-d²=0 resolution, since no test constructs one.
