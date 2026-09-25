# tor_zero_structure (C055)

## What it does
Analyzes `Tor_0(M, N)`, which is mathematically just `M ⊗_R N` (the base case with no derived/higher contribution). Provides a `Tor0Properties` summary and a few free-rank-based computations.

## Public API
- Re-exports `TorGroup`/`TorIndex` (C051), `TensorProductModule` (C052), `verify_tor_computation` (C054).
- `Tor0Properties { is_free, rank }` — `new(rank, has_torsion)`, `is_trivial()`.
- `analyze_tor_zero(&TensorProductModule) -> TorGroup` — rank = `module.free_rank()`, no torsion (per the doc comment, "torsion comes from higher Tor groups," which is standard for `Tor_0` — mathematically correct that `Tor_0` itself has no torsion contribution *from the resolution*, though see the caveat below about `free_rank` vs true tensor rank).
- `verify_tor_zero_universal_property(rank_m, rank_n) -> bool` — checks `rank_m * rank_n > 0 || rank_m == 0 || rank_n == 0`, which is a tautology (always `true` for any `usize` inputs, since if the product isn't `>0` then one of the factors must be `0`) — see gap.
- `compute_tor_zero_from_ranks(rank_m, rank_n) -> TorGroup` — same as `analyze_tor_zero` but from raw ranks instead of a module.

## Pipeline position
Depends on `tor_functor_definition` (C051), `tensor_product_module` (C052), `derived_homology` (C054, only for the re-exported `verify_tor_computation`, which this crate doesn't call itself — a re-export-only dependency). Consumed by `tor_tests_integration` (C060).

## Notes / gaps
- **Gap — `verify_tor_zero_universal_property` is a tautology:** for `usize` (unsigned) inputs, `rank_m * rank_n > 0` is false only when `rank_m == 0 || rank_n == 0` — which is exactly the second disjunct. The function is logically `P || !P`, always `true`, regardless of input. It cannot detect any actual violation of the universal property; it's a placeholder that always passes. Its own doc comment's intent ("Tor_0(M,N) should have rank = rank(M)*rank(N) for free modules") isn't actually checked against anything — there's no comparison to a real computed rank, just a self-referential tautology over the inputs used to construct the expected value.
- **Inherited gap (from C052):** `analyze_tor_zero`'s rank comes from `TensorProductModule::free_rank()`, which — per C052's README — doesn't account for bilinearity relations. So `Tor_0` here is really "rank of the free module on generator pairs," an upper bound on the true `M ⊗ N` rank whenever nontrivial relations exist.
- 5 unit tests; none would fail if `verify_tor_zero_universal_property`'s logic were deleted and replaced with `true` outright, which is a useful smell test confirming the tautology above.
