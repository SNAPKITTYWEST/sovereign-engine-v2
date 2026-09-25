# dimension_upper_bounds

Named upper bounds on Krull dimension from different algebraic arguments,
with a collection type to track and refine several at once.

## What it does

`DimensionUpperBound(usize)` with constructors mirroring standard
commutative-algebra facts: `from_generators` (dim of `k[x1..xn]` is `n`),
`from_relations` (generators minus relations, floored at 0),
`from_ideal_saturation` (height ≤ number of generators, i.e. Krull's
Hauptidealsatz-style bound), `from_transcendence_degree`,
`krull_pit_bound` (principal ideal theorem), and
`integral_extension_bound` (Cohen–Seidenberg: integral extensions preserve
dimension, so this just copies the other ring's `KrullDim`).
`satisfies(actual_dim)` checks `actual <= bound`; `refine` takes the min
with another bound. `BoundCollection` accumulates named bounds and exposes
`tightest()` and `all_satisfied(actual_dim)`.

## Public API

- `DimensionUpperBound(pub usize)` and its constructors (above),
  `bound()`, `satisfies`, `refine`, `tightest(&[Self])`
- `BoundCollection::new`, `add_generator_bound`, `add_relation_bound`,
  `add_saturation_bound`, `add_krull_pit_bound`, `tightest`, `all`,
  `all_satisfied`
- `BoundStrategy` enum (`AllBounds`/`GeneratorsOnly`/`KrullPITOnly`/
  `Conservative`) — defined but not consumed anywhere in this crate

## Pipeline role

Depends only on `krull_dimension_definition` (C067) for the `KrullDim` type
to compare against. Consumed by `krull_certification` (C069) and
`krull_spectrum_tests_integration` (C070) to sanity-check a computed
dimension against independent bounds.

## Gaps / weak spots

- Several constructors (`from_generators`, `from_ideal_saturation`,
  `krull_pit_bound`) are literally identical (`Self(n)`) — they exist to
  document *which theorem* justifies the bound, not to compute anything
  different. That's a reasonable API-as-documentation choice, but a reader
  should not expect different numeric behavior between them.
- `BoundStrategy` is declared but never used by `BoundCollection` or any
  function in this file — looks like a planned dispatch mechanism that
  wasn't wired up (dead code, no `#[allow(dead_code)]`, would warn under
  strict lint settings if exported unused).
