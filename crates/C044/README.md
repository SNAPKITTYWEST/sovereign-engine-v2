# differential_squared_zero (C044)

## What it does
Verifies the defining chain-complex identity `d² = 0`: for every generator `g` at a degree, computes `d(d(g))` and checks it's zero, producing per-degree `SquaredZeroCertificate`s and an aggregate `GlobalSquaredZeroProof`.

## Public API
- `SquaredZeroCertificate { degree, is_valid, generators_checked, test_cases_passed }` — `new(degree)`, `mark_valid(generators_checked, test_cases_passed)` (builder).
- `SquaredZeroVerifier` (unit struct, all associated functions):
  - `verify_at_degree(&DifferentialOperator, degree) -> SquaredZeroCertificate` — iterates all source generators, applies `d` twice, breaks early on first nonzero `d(d(g))`.
  - `verify_all(&DifferentialOperator) -> Vec<SquaredZeroCertificate>` — one cert per degree with a set differential, plus vacuous certs for shape-declared degrees `> 0` that have no differential matrix at all.
  - `verify_global(&DifferentialOperator) -> GlobalSquaredZeroProof` — aggregates all certs, ANDs `is_valid`, sums generator/test counts.
- `GlobalSquaredZeroProof { is_valid, certificates, total_generators_checked, total_test_cases_passed }` — `cert_at(degree)`, `summary() -> String`.

## Pipeline position
Depends on `chain_complex_shape` (C041) and `differential_operator` (C043). This is the crate that discharges the "chain complex" identity that C043 explicitly defers. Consumed by `projective_resolution` (C046), `exactness_predicate` (C047), `homology_computation` (C048), and `resolution_certification` (C049) — it's a load-bearing correctness gate for the whole homological layer.

## Notes / gaps
- **Note — early exit changes semantics subtly:** `verify_at_degree` breaks out of the generator loop on the *first* failure, so `test_cases_passed` on a failed certificate undercounts — it reports how many generators passed *before* the first failure, not a full survey. `generators_checked`, however, is incremented before the check and so also stops early. A caller wanting "how many of N generators fail" cannot get that from this API; they only learn "it failed, and it failed at or before generator k."
- **Gap:** the vacuous-degree loop in `verify_all` only covers degrees `> 0` (`if diff.matrix_at(degree).is_none() && degree > 0`) — degree 0 and negative degrees with no differential set are silently skipped rather than certified, meaning `verify_all`'s coverage is not actually "all degrees in the shape," just "degree > 0 without an explicit matrix, plus all degrees with an explicit matrix." Worth checking whether cohomological complexes (negative degrees, mentioned as supported in C041's `ChainDegreeShape` doc) are meant to be covered here.
- 5 unit tests, including a genuinely useful "nontrivial but still verifies" case (`test_verify_at_degree_nontrivial`) that exercises a real 2-step composition rather than only trivial zero differentials.
