# `dimension_upper_bounds` (C068)

Tier 6 — Krull dimension. *Generated from the crate source; regenerate after API changes.*

Upper bounds on Krull dimension via various algebraic properties.
Key bounds: generator count, saturation, integral extensions.

## Dependencies

- [C067 `krull_dimension_definition`](../C067/README.md)

## Re-exports

- `krull_dimension_definition::{KrullDim, Spectrum}`

## Public API

| Item | Description |
|---|---|
| `struct DimensionUpperBound(pub usize)` | Upper bound on Krull dimension |
| `fn DimensionUpperBound::from_generators(num_generators: usize) -> Self` | Bound from number of generators For polynomial rings: dim(k[x₁,...,xₙ]) = n |
| `fn DimensionUpperBound::from_relations(num_generators: usize, num_relations: usize) -> Self` | Bound from number of relations In a quotient, dimension typically decreases |
| `fn DimensionUpperBound::from_ideal_saturation(num_generators: usize) -> Self` | Bound from saturation property If I is an ideal, ht(I) ≤ μ(I) (number of generators) |
| `fn DimensionUpperBound::from_transcendence_degree(trans_deg: usize) -> Self` | Bound from integral extension If R ⊆ S integral, then dim(R) ≤ dim(S) But we can also bound via transcendence degree |
| `fn DimensionUpperBound::krull_pit_bound(num_generators: usize) -> Self` | Krull's principal ideal theorem: ht(p) ≤ μ(I) where p is minimal over I |
| `fn DimensionUpperBound::integral_extension_bound(other_dim: KrullDim) -> Self` | Cohen-Seidenberg: for R ⊆ S integral, same dimension |
| `fn DimensionUpperBound::bound(&self) -> usize` | Get numeric bound |
| `fn DimensionUpperBound::satisfies(&self, actual_dim: KrullDim) -> bool` | Check if actual dimension satisfies bound |
| `fn DimensionUpperBound::refine(&mut self, other: Self)` | Refine bound by taking minimum |
| `fn DimensionUpperBound::tightest(bounds: &[Self]) -> Self` | Get tightest bound from multiple sources |
| `struct BoundCollection` | Collection of bounds with refinement |
| `fn BoundCollection::new() -> Self` | Create empty collection |
| `fn BoundCollection::add_generator_bound(&mut self, num_generators: usize)` | Add a bound from generators |
| `fn BoundCollection::add_relation_bound(&mut self, num_gen: usize, num_rel: usize)` | Add a bound from relations |
| `fn BoundCollection::add_saturation_bound(&mut self, num_generators: usize)` | Add a bound from ideal saturation |
| `fn BoundCollection::add_krull_pit_bound(&mut self, num_generators: usize)` | Add Krull PIT bound |
| `fn BoundCollection::tightest(&self) -> Option<DimensionUpperBound>` | Get tightest bound |
| `fn BoundCollection::all(&self) -> &[(String, DimensionUpperBound)]` | Get all bounds |
| `fn BoundCollection::all_satisfied(&self, actual_dim: KrullDim) -> bool` | Check all bounds are satisfied |
| `fn BoundCollection::combined(&self, strategy: BoundStrategy) -> Option<DimensionUpperBound>` | Combine the bounds according to `strategy`: the minimum of all bounds, only generator bounds, only Krull PIT bounds, or (conservatively) the maximum. |
| `enum BoundStrategy` | Strategy for computing bounds |

## Tests

`cargo test -p dimension_upper_bounds` runs 9 unit tests.
