# `tor_higher_degrees` (C056)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

Higher Tor groups `Tor_i(M, N)`, `i > 0`: vanishing, growth, and the
bridge from a computed  to per-degree sequences.

## Dependencies

- [C051 `tor_functor_definition`](../C051/README.md)
- [C054 `derived_homology`](../C054/README.md)

## Re-exports

- `derived_homology::compute_tor_from_resolution`
- `tor_functor_definition::{TorComputation, TorGroup, TorIndex}`

## Public API

| Item | Description |
|---|---|
| `struct HigherTorProperties` | Free ranks of `Tor_i` for one degree across several module pairs. |
| `fn HigherTorProperties::new(degree: usize, ranks: Vec<usize>) -> Self` | Create properties for Tor_i |
| `fn HigherTorProperties::all_trivial(&self) -> bool` | True iff every recorded rank is zero. |
| `fn HigherTorProperties::total_rank(&self) -> usize` | Total rank across all Tor_i for fixed i |
| `fn tor_sequence(tor: &TorComputation) -> Vec<Option<TorGroup>>` | `Tor_0, Tor_1, …` up to the highest computed degree; missing degrees are `None`. |
| `fn is_short_exact_sequence(tor_groups: &[Option<TorGroup>]) -> bool` | True iff every `Tor_i` with `i > 0` is trivial (missing degrees count as trivial) — e.g. |
| `fn vanishing_indices(tor_groups: &[Option<TorGroup>]) -> Vec<usize>` | Degrees where Tor vanishes (missing degrees count as vanishing). |
| `fn tor_growth_rate(tor_groups: &[Option<TorGroup>]) -> Vec<f64>` | Ratios of generator counts between consecutive degrees (skipping degrees that follow a zero count). |

## Tests

`cargo test -p tor_higher_degrees` runs 3 unit tests.
