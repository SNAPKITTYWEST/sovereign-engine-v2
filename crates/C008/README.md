# `gap_tensor_ordering` (C008)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

A lawful total order on gap tensor nodes and ordering utilities built on
it.

`GapTensorNode`'s own `Ord` treats incomparable spectral weights (NaN) as
equal, which is not a total order.  instead compares
weights with `f32::total_cmp`, so it is total and agrees exactly with
`EqualityMode::Exact`.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C005 `gap_tensor_equality`](../C005/README.md)

## Public API

| Item | Description |
|---|---|
| `fn canonical_cmp(a: &GapTensorNode, b: &GapTensorNode) -> Ordering` | Total order: prime, then multiplicity, then weight by IEEE total order. |
| `fn resonance_cmp(a: &GapTensorNode, b: &GapTensorNode) -> Ordering` | Order by resonance (IEEE total order), falling back to `canonical_cmp`. |
| `fn sort_canonical(nodes: &mut [GapTensorNode])` | Sort nodes into canonical order. |
| `fn is_sorted_canonical(nodes: &[GapTensorNode]) -> bool` | True iff `nodes` is in non-decreasing canonical order. |
| `fn rank_by_resonance(nodes: &[GapTensorNode]) -> Vec<usize>` | Indices of `nodes` ordered by descending resonance; ties keep canonical order. |
| `fn dedup_exact(nodes: &mut Vec<GapTensorNode>)` | Remove consecutive exact duplicates. |
| `fn merge_sorted(a: &[GapTensorNode], b: &[GapTensorNode]) -> Vec<GapTensorNode>` | Merge two canonically sorted slices into one sorted vector. |

## Tests

`cargo test -p gap_tensor_ordering` runs 4 unit tests.
