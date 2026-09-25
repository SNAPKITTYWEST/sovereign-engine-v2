# memory_lemmas_library

Same template as `gap_lemmas_library` (C073), retargeted at memory-arena
correctness (allocation/deallocation safety), tagged with a free-text
`category: String` instead of a numeric size.

## What it does

`MemoryLemma { name, statement, status, proof, category }` — `category` is
a free-form string (constructor requires it directly, no builder pattern
like C073's `with_gap_size`). `MemoryLemmasLibrary` mirrors
`GapLemmasLibrary`'s `BTreeMap` + add/get/count API, with
`lemmas_by_category(category)` in place of `lemmas_for_gap`.

## Public API

- `LemmaStatus`, `MemoryLemma::new(name, statement, category)`, `prove`,
  `is_proven`
- `MemoryLemmasLibrary::new`, `add_lemma`, `get_lemma[_mut]`,
  `count_proven`, `count_open`, `lemmas_by_category`

## Pipeline role

Depends on `type_checking_interface` (C071) and three Tier-2 arena crates
(`multiplicity_arena_core` C011, `multiplicity_arena_layout` C012,
`multiplicity_arena_allocation` C013), none of which are actually referenced
in the file body — same pattern as C073. Feeds `cross_layer_lemmas_library`
(C079) and `lean_obligation_aggregator` (C080).

## Gaps / weak spots

- Same core gap as C073: no memory-safety lemma statements are actually
  populated; this is a generic registry, and the three upstream arena
  crates it depends on are unused here.
- Unlike C073's `Option<usize>` tag (absent by default), `category` is a
  required constructor argument with no default/`Option`, so every
  `MemoryLemma` must be tagged at creation — a minor API inconsistency
  across the six sibling crates worth normalizing if this pattern is kept.
