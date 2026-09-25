# tor_resolution_lemmas_library

Same template, targeted at Tor-functor/resolution/functoriality properties,
tagged with `tor_degree: Option<usize>` (mirrors C073/C075's numeric-tag
pattern).

## What it does

`TorLemma { name, statement, status, proof, tor_degree }`, builder
`with_tor_degree(degree)`, `prove`, `is_proven`. `TorLemmasLibrary` —
add/get/count plus `lemmas_at_degree(degree)`.

## Public API

- `LemmaStatus`, `TorLemma::new`, `with_tor_degree`, `prove`, `is_proven`
- `TorLemmasLibrary::new`, `add_lemma`, `get_lemma[_mut]`, `count_proven`,
  `count_open`, `lemmas_at_degree`

## Pipeline role

Depends on `type_checking_interface` (C071) and five Tier-4/5 Tor crates
(`tor_functor_definition` C051, `derived_homology` C054,
`tor_zero_structure` C055, `tor_higher_degrees` C056,
`functoriality_of_tor` C057), unused in the file body. Feeds
`cross_layer_lemmas_library` (C079) and `lean_obligation_aggregator` (C080).

## Gaps / weak spots

- Same core gap: no Tor-functor lemmas (e.g. Tor_0 = tensor product,
  functoriality in each argument) are actually populated — registry only.
