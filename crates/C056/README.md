# tor_higher_degrees (C056)

## What it does
Analyzes higher Tor groups `Tor_i(M,N)` for `i > 0`: short-exactness detection (all higher Tor vanish), vanishing-degree enumeration, and a Tor-rank "growth rate" metric across degrees.

## Public API
- Re-exports `TorGroup`/`TorIndex` (C051), `compute_tor_from_resolution` (C054).
- `HigherTorProperties { degree, ranks: Vec<usize> }` — `new()`, `all_trivial()`, `total_rank()`.
- `is_short_exact_sequence(&[Option<TorGroup>]) -> bool` — skips index 0, treats `None` as trivial (`unwrap_or(true)`), true iff every `Tor_i` for `i >= 1` present is trivial or absent.
- `vanishing_indices(&[Option<TorGroup>]) -> Vec<usize>` — indices (including 0) where the group is trivial or `None`.
- `tor_growth_rate(&[Option<TorGroup>]) -> Vec<f64>` — ratio `num_generators(i) / num_generators(i-1)` for consecutive degrees, skipping ratios where the denominator is 0.

## Pipeline position
Depends on `tor_functor_definition` (C051) and `derived_homology` (C054, again only for a re-export, `compute_tor_from_resolution`, not actually called in this crate's own code). Consumed by `tor_tests_integration` (C060).

## Notes / gaps
- **Note:** `is_short_exact_sequence`'s name is potentially misleading in a homological-algebra sense — "short exact sequence" traditionally refers to a 3-term exact sequence `0 -> A -> B -> C -> 0`, not to the vanishing of higher Tor. What this function actually checks (all `Tor_i = 0` for `i > 0`) is closer to the condition "the corresponding short exact sequence of modules is exact in a way that doesn't propagate extension classes" (related to `N` being flat, or the sequence being pure/split) — the function is doing something real and standard in homological algebra (checking a vanishing condition), but the name borrows a term with a more specific meaning elsewhere; worth a doc clarification for anyone approaching this fresh.
- `vanishing_indices` treats `None` (not-yet-computed) the same as `Some(trivial group)` — a degree that simply hasn't been computed yet is indistinguishable from one that's genuinely known to vanish. Any caller distinguishing "provably zero" from "unknown" needs to check the original slice separately.
- `tor_growth_rate` silently drops ratios where `ranks[i-1] == 0` rather than reporting them as `0.0`, `NaN`, or `infinity` — the returned vector can therefore have fewer entries than `ranks.len() - 1`, and the index correspondence between a growth-rate entry and its degree pair is not preserved in the return type (a caller can't tell from the `Vec<f64>` alone which degree transition a given rate corresponds to if any were skipped).
- 4 unit tests, reasonably exercising the vanishing/short-exact logic with mixed `Some`/`None` entries.
