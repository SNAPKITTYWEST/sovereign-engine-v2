# lean_obligation_aggregator

Rolls up `ObligationManager` (C072) state into tier-grouped statistics —
the reporting layer for Tier 7's proof-obligation bookkeeping.

## What it does

`AggregatedObligationReport::from_manager` computes `total`/`closed`/`open`/
`failed` counts (`failed = total - closed - open`, derived rather than
tracked directly — note this silently folds any obligations whose status is
neither Open nor Closed into "failed", including the unreachable
`InProgress` state from C072) and `completion_percent` (100.0 for an empty
manager — vacuous truth again). It also groups obligations `by_tier` via
`extract_tier_from_id`, a naive string-split parser expecting IDs of the
form `"tier_<N>_..."` — any ID not matching that shape is bucketed under
tier `0` by default (via `unwrap_or(0)`), which conflates "explicitly tier
0" with "couldn't parse a tier at all." `FullObligationContext` bundles a
live `ObligationManager` with its `AggregatedObligationReport` snapshot,
refreshing the report on every `add_obligation` call (recomputes from
scratch, not incrementally) and via explicit `refresh_report`.

## Public API

- `AggregatedObligationReport::from_manager(&ObligationManager)`,
  `all_closed`, `status_string`
- `ObligationStats { tier, count, closed }`
- `FullObligationContext::new`, `add_obligation`, `refresh_report`,
  `is_complete`, `statistics`

## Pipeline role

Depends on `type_checking_interface` (C071), `obligation_management`
(C072), and all six domain lemma libraries (C073-C078) — the latter six are
declared but unused in this file, same recurring pattern as C079. This is
the top of the Lean lemma-library stack (Tier 7): where all the individual
libraries' obligations would ultimately be gathered for a single
completion report, feeding into `final_certification_report` (C100,
currently unimplemented).

## Gaps / weak spots

- `extract_tier_from_id`'s `unwrap_or(0)` means malformed or missing tier
  prefixes silently land in the "tier 0" bucket alongside genuinely
  tier-0 obligations — this would understate/overstate per-tier completion
  if any obligation IDs don't follow the `tier_N_...` convention exactly
  (nothing enforces that convention at obligation-creation time in C072).
- `statistics()` hardcodes the label `"Tier 7 Obligations"` regardless of
  which tiers are actually present in `by_tier` — misleading if this
  aggregator is ever reused for a different tier's obligations.
- Because the six lemma-library dependencies are unused, this aggregator
  currently only aggregates the generic `ObligationManager` from C072, not
  actual obligations sourced from the (currently empty) domain lemma
  libraries — consistent with those libraries having no populated content
  yet.
