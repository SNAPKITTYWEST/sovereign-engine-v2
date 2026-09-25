# spectrum_order

The specialization preorder on `Spec(R)` and the Zariski topology derived
from it.

## What it does

`SpecializationPreorder::from_spectrum` materializes the full preorder as a
`BTreeSet<(u64, u64)>` of pairs `p ≤ q` (i.e. `spec.specializes(p, q)`),
computed by brute-force over all pairs in the spectrum (O(n^2)). Exposes
`le`, `upper_set`, `lower_set`, and `minimal_elements`/`maximal_elements` of
an arbitrary subset. `ZariskiTopology` builds on the preorder to define
closed sets (down-sets under specialization), open sets (complements of
closed), `neighborhood`, `closure` (iterative fixed-point over the down-set
closure), and `interior`.

## Public API

- `SpecializationPreorder::from_spectrum(&Spectrum)`, `le`, `upper_set`,
  `lower_set`, `minimal_elements`, `maximal_elements`
- `ZariskiTopology::from_spectrum(&Spectrum)`, `is_closed`, `is_open`,
  `neighborhood`, `closure`, `interior`, `preorder()`

## Pipeline role

Depends on `spectrum_definition` (C064) and, oddly, `gap_tensor_ordering`
(C008) — a Tier-1 gap-combinatorics crate — though nothing in this file
visibly uses it; likely dead/aspirational wiring for a future ordering
compatibility check. Consumed by `spectrum_chains` (C066), which needs `le`
to test whether a candidate chain is totally ordered.

## Gaps / weak spots

- `from_spectrum` is quadratic in spectrum size with no caching; fine at toy
  scale, a bottleneck if `Spectrum` ever grows large.
- `closure`'s fixed-point loop is O(n^2) per iteration and re-scans the
  whole spectrum each pass — correct but not efficient.
- Several tests assert `cond || !cond` (`test_specialization_preorder`,
  `test_zariski_topology`) — they check the call doesn't panic, not that the
  topology/order is actually correct on that input.
- The `gap_tensor_ordering` dependency (C008) appears unused in this file;
  worth confirming intent or removing.
