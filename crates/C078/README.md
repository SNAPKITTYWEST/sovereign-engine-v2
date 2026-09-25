# krull_lemmas_library

Same template, targeted at Krull-dimension inequalities/chain properties,
tagged with `dimension_bound: Option<usize>`.

## What it does

`KrullLemma { name, statement, status, proof, dimension_bound }`, builder
`with_dimension_bound(bound)`, `prove`, `is_proven`. `KrullLemmasLibrary` —
add/get/count plus `lemmas_with_bound(bound)`.

## Public API

- `LemmaStatus`, `KrullLemma::new`, `with_dimension_bound`, `prove`,
  `is_proven`
- `KrullLemmasLibrary::new`, `add_lemma`, `get_lemma[_mut]`, `count_proven`,
  `count_open`, `lemmas_with_bound`

## Pipeline role

Unlike its siblings (C073-C077), this one depends directly on the *Rust*
Krull-dimension crates from Tier 6 (`spectrum_definition` C064,
`krull_dimension_definition` C067, `dimension_upper_bounds` C068,
`krull_certification` C069) rather than earlier gap/tensor tiers —
appropriate, since it's the Lean-side counterpart to that Rust layer. None
of these are actually referenced in the file body, same pattern as its
siblings. Feeds `cross_layer_lemmas_library` (C079) and
`lean_obligation_aggregator` (C080).

## Gaps / weak spots

- Same core gap: no dimension-theoretic lemmas (Krull's principal ideal
  theorem, Cohen-Seidenberg, etc.) are actually populated. This is the
  crate best positioned to formalize the bounds already implemented
  numerically in `dimension_upper_bounds` (C068) — closing that gap would
  connect the two halves of the Krull layer (Rust computation + Lean proof)
  that C093-C096 (cross-layer correspondence, unimplemented) are meant to
  bridge at runtime.
