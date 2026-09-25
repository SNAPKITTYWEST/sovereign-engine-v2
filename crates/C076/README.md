# homological_lemmas_library

Same template, targeted at chain-complex/exactness/differential properties,
tagged with a free-text `lemma_type: String` (mirrors C074's `category`
pattern rather than C073/C075's `Option<usize>` pattern).

## What it does

`HomologyLemma { name, statement, status, proof, lemma_type }`, `prove`,
`is_proven`. `HomologyLemmasLibrary` — add/get/count plus
`lemmas_by_type(lemma_type)`.

## Public API

- `LemmaStatus`, `HomologyLemma::new(name, statement, lemma_type)`, `prove`,
  `is_proven`
- `HomologyLemmasLibrary::new`, `add_lemma`, `get_lemma[_mut]`,
  `count_proven`, `count_open`, `lemmas_by_type`

## Pipeline role

Depends on `type_checking_interface` (C071) and five Tier-4 homological
crates (`differential_operator` C043, `differential_squared_zero` C044,
`exactness_predicate` C047, `homology_computation` C048,
`resolution_certification` C049), unused in the file body. Feeds
`cross_layer_lemmas_library` (C079) and `lean_obligation_aggregator` (C080).

## Gaps / weak spots

- Same core gap as its siblings: no homological algebra lemmas (e.g. "d² =
  0", exactness at a given spot) are actually stated or proven here — the
  crate is registry infrastructure only. The `differential_squared_zero`
  dependency (C044) is a strong hint this crate is *meant* to hold exactly
  that lemma, which makes its absence conspicuous.
