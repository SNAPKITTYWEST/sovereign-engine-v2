# tor_tests_integration (C060)

## What it does
Integration-test crate for the entire Tor-functor sub-layer (C051–C059), mirroring C050's role for the homological-algebra layer and C040's for the recursive-solver layer. Provides a single `tier5_integration_test()` scenario chaining tensor product, tensored complex, Tor computation, `Tor_0` analysis, functoriality, and Betti numbers, plus individual unit tests per component.

## Public API
- Re-exports `TorComputation` (C051), `TensorProductModule` (C052), `TensoredComplex` (C053), `compute_tor_from_resolution` (C054), `analyze_tor_zero` (C055), `is_short_exact_sequence` (C056), `ModuleMap` (C057), `compute_betti_numbers` (C058), `TorChainComplexData` (C059).
- `tier5_integration_test() -> bool` — six-step boolean check chaining the above; returns `false` on the first failed step (no diagnostic message, unlike `homological_tests_integration`'s `TestResult`-based reporting in C050).

## Pipeline position
Depends on all nine other Tor-sub-layer crates (C051–C059). Terminal validation point of the Tor sub-layer — nothing in this range consumes it, consistent with it being a pure test/integration crate like C040 and C050.

## Notes / gaps
- **Design inconsistency vs. sibling integration crates:** C050 (`homological_tests_integration`) uses a structured `TestResult`/`TestSummary` reporting model with named, individually-failable scenarios and a formatted report. This crate instead uses one monolithic `bool`-returning function (`tier5_integration_test`) with six inline checks — if step 3 fails, the caller learns only `false`, not which of the six checks failed or why. Given C050 already establishes a better pattern in the same repository, this crate is a regression in diagnosability relative to its sibling; worth aligning the two if the Tor layer's integration testing is revisited.
- Because this crate's individual `#[cfg(test)]` tests each construct their `TorComputation`s and `TensorProductModule`s directly rather than through `compute_tor_from_resolution` fed by a real `ProjectiveResolution`, the suite — like the crates it wraps — never exercises the actual "resolution → Tor" data path end-to-end. All the gaps identified in C053/C054/C059 (the disconnected wiring between resolution, tensored complex, and Tor) are consequently invisible to this integration suite as well; it validates that each piece works in isolation, not that they compose correctly together.
- 6 unit tests plus the one integration-scenario test (called from its own `#[test]` wrapper) — reasonable breadth for smoke-testing each re-exported API surface, but see the wiring caveat above for what's *not* covered.
