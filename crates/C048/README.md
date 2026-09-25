# homology_computation (C048)

## What it does
Computes (an approximation of) homology groups `H_n = ker(d_n)/im(d_{n+1})` for a chain complex, plus derived invariants (Betti numbers, Euler characteristic). Explicitly documented as simplified: full Smith-normal-form-based computation is not implemented.

## Public API
- `HomologyGroup { degree, rank, torsion }` — `new()`, `trivial()`, `is_trivial()`, `add_torsion()` (drops coefficients `<= 1`), `betti_number()`, `to_string()` (formats as `Z^rank ⊕ Z/t1 ⊕ ...`).
- `HomologyComputationResult { groups: HashMap<i32, HomologyGroup>, verified }` — `new()`, `add_group()`, `group_at()`, `support_degrees()` (nontrivial only, sorted), `euler_characteristic()` (alternating sum of ranks), `mark_verified()`, `summary()`.
- `HomologyComputer` (unit struct):
  - `compute_at_degree(&DifferentialOperator, degree) -> Result<HomologyGroup, String>` — **returns the estimated kernel dimension as the homology rank directly, without subtracting the image dimension** (see gap).
  - `estimate_kernel_rank` (private) — yet another ad hoc rank estimator (third independent implementation in the layer — see C047's README).
  - `compute_all(&DifferentialOperator) -> Result<HomologyComputationResult, String>` — requires global `d²=0` first.
  - `compute_reduced_homology(&DifferentialOperator, degree)` — subtracts 1 from rank at degree 0 only, for augmented/reduced homology.

## Pipeline position
Depends on `chain_complex_shape` (C041, unused — dead dependency), `differential_operator` (C043), `differential_squared_zero` (C044). Consumed by `exactness_predicate` (C047, via `check_from_homology`), `resolution_certification` (C049 indirectly via the resolution layer), and the Tor sub-layer (`tor_functor_definition` C051, `derived_homology` C054).

## Notes / gaps
- **Significant gap, self-documented:** `compute_at_degree`'s doc comment admits: "For now, we verify d² = 0 and return a placeholder... A full implementation would compute the quotient ker(d_n) / im(d_{n+1})." The returned `HomologyGroup.rank` is literally `estimate_kernel_rank(diff, degree)` — the **kernel** dimension, not the quotient `ker/im`. This means every "homology group" this crate produces is actually reporting kernel rank, which overstates homology whenever the image is nonzero (i.e., whenever the differential is nontrivial one degree up). Anyone downstream trusting `HomologyGroup.rank` as true homology rank (e.g., for Betti numbers or Euler characteristic) is working with an upper bound, not the actual value.
- Torsion is never computed or populated anywhere in this crate — `HomologyGroup::torsion` always stays empty in practice; `add_torsion` exists but nothing calls it. Any module with actual Z/n torsion subgroups would be silently reported as pure free.
- `euler_characteristic()` uses `degree % 2` with Rust's `%` (which can be negative for negative `degree`) to pick the sign — for negative-degree entries this is still correct in effect (`-1 % 2 == -1` in Rust, and the `if degree % 2 == 0` branch correctly treats 0 vs nonzero either sign), but worth a double-check if cohomological (negative-degree) complexes are exercised, since the sign logic wasn't written with negative moduli explicitly in mind.
- 6 unit tests, none of which exercise a case with a genuinely nonzero image (i.e., none would catch the kernel-vs-quotient gap above).
