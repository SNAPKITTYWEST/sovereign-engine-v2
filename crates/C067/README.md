# krull_dimension_definition

Defines `KrullDim` and computes it from a spectrum via maximal chains, plus
a pluggable-strategy calculator.

## What it does

`KrullDim(usize)`: `from_spectrum` finds all maximal chains
(`spectrum_chains::MaximalChains`) and sets `dim = longest_chain_len - 1`
(0 for an empty spectrum, following the "a chain of n+1 primes has dimension
n" convention). Also provides `is_zero_dimensional`/`is_one_dimensional`,
`is_catenary` (all maximal chains have equal length — recomputes chains
independently of `from_spectrum`), `maximal_chains` (returns the raw
`Vec<Vec<u64>>` achieving the longest length), and two
static "textbook fact" helpers: `height_bound_from_generators` (Krull's
height bound is at most the generator count) and
`localization_respects_dimension` (dimension is non-increasing after
localization, i.e. `dim_after <= dim_before`).

`DimensionCalculator` wraps three `DimensionStrategy` variants:
`ChainEnumeration` (exact, via `from_spectrum`), `GeneratorBound` (returns
`spec.len()` as a crude stand-in), and `SaturationBound`
(`sqrt(spec.len()).ceil()` — a placeholder, not a real saturation
argument).

## Public API

- `KrullDim(pub usize)`, `dim()`, `is_zero_dimensional`, `is_one_dimensional`
- `KrullDim::from_spectrum`, `is_catenary`, `maximal_chains`,
  `height_bound_from_generators`, `localization_respects_dimension`
- `DimensionStrategy` enum, `DimensionCalculator::new/compute`

## Pipeline role

Depends on `spectrum_definition`, `spectrum_order`, `spectrum_chains`
(C064-C066). Consumed by `dimension_upper_bounds` (C068, checks bounds
against a computed `KrullDim`) and `krull_certification` (C069, verifies the
computation is internally consistent).

## Gaps / weak spots

- `GeneratorBound` and `SaturationBound` strategies are not actual
  mathematical bounds on this data model — `SaturationBound`'s
  `sqrt(n).ceil()` in particular has no stated justification and looks like
  a placeholder rather than a derived formula; tests only assert the result
  is `<= spec.len()`, which both trivially satisfy.
- No test checks an exact nonzero dimension value end-to-end (e.g. a
  spectrum engineered to have dimension exactly 2); coverage is
  boundary-only (0, ≤1, ≤3).
