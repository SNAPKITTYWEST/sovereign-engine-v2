# gap_lemmas_library

First of six parallel "domain lemma library" crates (C073-C078), each a
near-identical template around a `BTreeMap<String, XLemma>` plus a
domain-specific tag field. This one tags lemmas with `gap_size: Option<usize>`.

## What it does

`GapLemma { name, statement: LeanType, status: LemmaStatus, proof:
Option<ProofTerm>, gap_size: Option<usize> }`, builder-style
`with_gap_size(size)`, `prove(proof)` (Open -> Closed only if
`proof.is_complete()`), `is_proven()`. `GapLemmasLibrary` wraps a
`BTreeMap<String, GapLemma>` plus its own `TypeContext`, with add/get,
`count_proven`/`count_open`, and `lemmas_for_gap(size)` filtering by tag.

## Public API

- `LemmaStatus` (Open/InProgress/Closed/Failed — same caveat as C072:
  InProgress/Failed unreachable via this API)
- `GapLemma` (+ `new`, `with_gap_size`, `prove`, `is_proven`)
- `GapLemmasLibrary` (+ `new`, `add_lemma`, `get_lemma[_mut]`,
  `count_proven`, `count_open`, `lemmas_for_gap`)

## Pipeline role

Depends on `type_checking_interface` (C071) plus five Tier-2/3 gap crates
(`prime_predicate` C021, `prime_enumeration` C022, `gap_candidate_set` C023,
`gap_verification` C028, `prime_gap_relationship` C029) — all listed as
dependencies but none actually imported/used in this file; the intent is
presumably that this library's (currently unwritten) lemma *statements*
would reference types from those crates once populated, but as shipped the
library is an empty, generic bookkeeping shell with no gap-specific lemma
content. Feeds `cross_layer_lemmas_library` (C079) and
`lean_obligation_aggregator` (C080).

## Gaps / weak spots

- No actual lemma statements about prime gaps are defined anywhere in this
  crate — it's pure infrastructure (a lemma registry), not a populated
  library. The five upstream Tier-2/3 dependencies are unused, so the
  crate's real content (what claims does it prove?) is entirely absent;
  this is the most significant gap in the layer: the "library" has no
  books.
- This is the template every other `*_lemmas_library` crate (C074-C078)
  copies; see those READMEs for their domain-specific tag field, but the
  same "no populated content" gap applies to all of them.
