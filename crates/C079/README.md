# cross_layer_lemmas_library

Structurally different from the six domain lemma libraries (C073-C078):
instead of tagging lemmas by a domain-specific property, it tags them by a
`(source_tier, target_tier)` pair, modeling relationships *between* layers
of the pipeline rather than within one.

## What it does

`CrossLayerLemma { id, source_tier: usize, target_tier: usize, statement:
LeanType, proof: Option<ProofTerm> }` — note: no `LemmaStatus` field at all;
"proven" is just `proof.is_some()`. `direction_name()` renders e.g.
`"Tier 2 -> Tier 3"`. `CrossLayerLemmaLibrary` wraps a
`BTreeMap<String, CrossLayerLemma>` keyed by id, with
`lemmas_for_transition(from, to)` (direction-sensitive),
`are_tiers_related(t1, t2)` (checks *either* direction), and
`proof_coverage()` — fraction proven, defined as `1.0` for an empty library
(vacuous-truth convention).

## Public API

- `CrossLayerLemma::new(id, source_tier, target_tier, statement)`, `prove`,
  `is_proven`, `direction_name`
- `CrossLayerLemmaLibrary::new`, `add_lemma`, `get_lemma`, `count_proven`,
  `lemmas_for_transition`, `are_tiers_related`, `proof_coverage`

## Pipeline role

Depends on `type_checking_interface` (C071) and all six domain lemma
libraries (C073-C078) — but, as with those crates, none are actually
referenced in this file's body; this crate is meant to hold lemmas whose
*statements* cross tiers (e.g. relating a gap-tensor invariant to a
homological one), but as shipped it's an empty tier-tagged registry.
Consumed by `lean_obligation_aggregator` (C080), and conceptually parallel
to `cross_layer_types`/`cross_layer_invariants`/`rust_lean_correspondence`
(C091-C093), which are currently unimplemented stubs.

## Gaps / weak spots

- No cross-layer lemma content is populated — same registry-only pattern as
  C073-C078, but here the gap is arguably more central: this is supposed to
  be the crate that ties the whole four-stage pipeline together formally,
  and it currently holds zero statements.
- `tier` here is a bare `usize` with no validation against the actual
  four-layer/ten-tier taxonomy described in the workspace's design docs —
  nothing stops constructing a `CrossLayerLemma` with `source_tier: 99`.
