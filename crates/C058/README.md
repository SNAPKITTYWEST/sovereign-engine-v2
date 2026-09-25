# tor_invariants_computation (C058)

## What it does
Derives numeric invariants from a `TorComputation`: Betti numbers (rank per degree), a "torsion complexity" scalar, a free-resolution predicate, and a crude global-dimension estimate.

## Public API
- Re-exports `TorGroup`/`TorComputation` (C051), `verify_tor_computation` (C054, unused re-export).
- `BettiNumbers { ranks: BTreeMap<usize, usize> }` — `new()`, `add()`, `beta(degree)`, `total_rank()`, `regularity()` (= highest degree key present, **not** the standard commutative-algebra notion of Castelnuovo–Mumford regularity, which is typically `max_i(degree_i - i)` over a graded resolution — see gap).
- `compute_betti_numbers(&TorComputation) -> BettiNumbers`.
- `torsion_complexity(&TorComputation) -> u64` — **product** (not sum, despite the doc comment saying "sum of torsion exponents") of `torsion_exponent()` across all groups.
- `is_free_resolution(&TorComputation) -> bool` — true iff every group's torsion map is empty.
- `global_dimension(&TorComputation) -> Option<usize>` — just the max degree key present; not an actual computed projective/global dimension in the ring-theoretic sense, just "how far did we compute."

## Pipeline position
Depends on `tor_functor_definition` (C051) and `derived_homology` (C054, re-export only, unused in this crate's own logic). Consumed by `tor_chain_complex_interface` (C059) for `BettiNumbers`/`compute_betti_numbers`, and by `tor_tests_integration` (C060).

## Notes / gaps
- **Naming mismatch — `regularity()`:** in commutative algebra, "regularity" (Castelnuovo–Mumford regularity) is a specific invariant computed as `max_i (t_i - i)` where `t_i` is the top nonzero degree of the `i`-th syzygy module in a graded free resolution — it is *not* simply "the highest Tor degree present," which is what this method actually returns. As written, `regularity()` is really "top computed Tor degree." Anyone using this value as true Castelnuovo–Mumford regularity in the Krull-dimension layer (C061+, outside this range) would get a different, generally larger or differently-shifted number than the textbook definition. Worth flagging clearly since "regularity" is a loaded term in this exact mathematical domain (the pipeline explicitly targets Krull dimension / commutative algebra per the assignment brief).
- **Doc/code mismatch — `torsion_complexity`:** the doc comment says "sum of torsion exponents across all Tor groups" but the implementation is `.product()`, not `.sum()`. This is either a doc bug or a code bug; either way the two disagree, and "complexity" as a product of exponents (which can grow multiplicatively very fast, e.g., three groups with exponents 2,3,5 give 30 rather than 10) is a meaningfully different metric than a sum. Flagging for whoever owns this crate to reconcile intent vs. implementation.
- `global_dimension` doesn't validate that intermediate Tor groups are actually nontrivial — a `TorComputation` with only `Tor_0` and `Tor_5` populated (nothing in between) would report global dimension 5, which conflates "highest index we happened to compute" with "highest index where Tor is genuinely nonzero."
- 4 unit tests; none test `torsion_complexity` or `regularity` against a case that would reveal either mismatch above (no test uses nonempty torsion, and no test compares `regularity()`'s output against the textbook formula).
