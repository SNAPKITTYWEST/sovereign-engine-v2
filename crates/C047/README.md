# exactness_predicate (C047)

## What it does
Checks exactness of a `DifferentialOperator`-based chain complex at a degree (`ker(d_n) = im(d_{n+1})`, i.e., `H_n = 0`) and globally, via rank-based kernel/image dimension estimation over dense matrices.

## Public API
- `ExactnessCertificate { degree, is_exact, kernel_dim, image_dim }` — `new()` computes `is_exact = kernel_dim == image_dim`; `summary()`.
- `ExactnessPredicateChecker` (unit struct):
  - `check_at_degree(&DifferentialOperator, degree) -> ExactnessCertificate` — first requires `d²=0` at that degree (via C044's `SquaredZeroVerifier`), then compares `compute_kernel_dimension` vs `compute_image_dimension`.
  - `check_global_exactness(&DifferentialOperator) -> GlobalExactnessProof` — requires global `d²=0` first, then checks every shape-declared degree.
  - `check_from_homology(&HomologyComputationResult) -> bool` — exact iff no nontrivial homology groups.
  - `compute_kernel_dimension`/`compute_image_dimension` (private) — both do ad hoc Gaussian-elimination-style rank estimation over `i64` dense matrices from `to_dense_matrix`.
- `GlobalExactnessProof { is_exact, certificates, reason }` — `cert_at()`, `exact_count()`, `non_exact_count()`, `summary()`.

## Pipeline position
Depends on `chain_complex_shape` (C041, unused — dead dependency), `differential_operator` (C043), `differential_squared_zero` (C044), and — notably — `homology_computation` (C048), creating a **dependency cycle risk**: C048's own Cargo.toml does not depend back on C047, so there's no actual cycle, but conceptually the two crates compute overlapping things (kernel/image dimension estimation) independently rather than sharing one implementation.

## Notes / gaps
- **Novelty/duplication:** `compute_kernel_dimension` and `compute_image_dimension` reimplement essentially the same ad hoc integer-matrix-rank algorithm that already exists in `ProjectiveModuleHomomorphism::rank()` (C045) and `HomologyComputer::estimate_kernel_rank` (C048) — three independent, slightly different rank-estimation routines exist across C045/C047/C048. None share code. A future refactor consolidating these into one audited rank routine would reduce triple-maintenance risk (and triple-bug-surface).
- **Bug-shaped observation:** `compute_kernel_dimension`'s pivot-finding loop increments `current_col` in the `else` branch (no pivot found) but does *not* fall through to try the same row against the next column — it advances both row and column together each iteration even on a skipped column, unlike a textbook echelon-form reduction which would only advance `current_row` on a successful pivot. This can undercount rank for matrices with zero columns interleaved with nonzero ones — worth a targeted test with such a matrix.
- `get_target_rank` is `#[allow(dead_code)]` — an explicit acknowledgment that it's unused; a real stub, self-flagged in code, not just missing.
- 4 unit tests — coverage is thin on the actual degree-checking logic (only a zero-rank edge case is exercised against a real `DifferentialOperator`); the other two tests build `ExactnessCertificate`/`GlobalExactnessProof` directly rather than through the checker.
