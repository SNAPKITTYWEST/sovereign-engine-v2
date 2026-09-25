# krull_certification

Produces and verifies a `DimensionProof`: a structured witness that a
computed Krull dimension is self-consistent, plus a multi-check
`CertificationChecker`.

## What it does

`DimensionProof::from_spectrum` recomputes the dimension, the preorder, and
all maximal chains, and records whether the longest chain's length equals
`dimension + 1` (`chain_length_ok`). `verify()` requires `chain_length_ok`,
`bounds_satisfied` (defaults to `true` until `check_bounds` is called), and
`verify_chain_ordering()` (every maximal chain has the expected length).
`CertificationChecker` wraps a `Spectrum` + its `DimensionProof` and runs
five named checks (`chain_ordering`, `non_negative`, `catenary_property`,
`longest_chain_ok`, `bounded_by_spectrum_size`) into a `CertificationResult`
map of pass/fail, and can separately verify a `BoundCollection` from C068.

## Public API

- `DimensionProof { dimension, bounds_satisfied, longest_chain,
  maximal_chains, chain_length_ok }`, `from_spectrum`, `verify`,
  `check_bounds(&BoundCollection)`
- `CertificationChecker::new(Spectrum)`, `check_all`, `verify_bounds`, `proof()`
- `CertificationResult`: `add_check`, `all_passed`, `check(name)`, `checks()`,
  `passed_count`, `total_count`, `failed_checks`

## Pipeline role

Depends on `gap_tensor_trace` (C010, wiring only — not used in this file),
`spectrum_definition`, `spectrum_order`, `spectrum_chains`,
`krull_dimension_definition`, `dimension_upper_bounds` (C064-C068). This is
the terminal correctness gate for the Krull layer before
`krull_spectrum_tests_integration` (C070) runs its integration suite, and
before the runtime/certification layer (C091-C100, currently unimplemented)
would consume it.

## Gaps / weak spots

- `bounds_satisfied` defaults to `true` in `from_spectrum` and is only set
  correctly if the caller explicitly calls `check_bounds` afterward — so
  `verify()` can silently report success on the bounds dimension without
  any bounds ever having been checked. This is an easy-to-misuse API: a
  caller who forgets `check_bounds` gets a false "certified".
- `test_certification_checker`'s assertion
  `assert!(!result.failed_checks().is_empty() || result.all_passed())` is a
  tautology (always true for any `CertificationResult`) and verifies
  nothing about the actual check outcomes.
- The `gap_tensor_trace` dependency is unused in this file.
