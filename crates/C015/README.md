# `multiplicity_arena_pointers` (C015)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

Region-relative pointers into a multiplicity arena. An  is a
`(region, offset)` pair that can only be created in bounds; arithmetic is
checked and never leaves its region. Every read and write re-validates the
pointer against the layout and arena it is used with, so a pointer made
for one layout cannot silently index past another arena.

## Dependencies

- [C008 `gap_tensor_ordering`](../C008/README.md)
- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)

## Re-exports

- `multiplicity_arena_core::{GapTensorNode, MultiplicityArena}`
- `multiplicity_arena_layout::{ArenaLayout, LayoutError, Region, RegionSpan}`

## Public API

| Item | Description |
|---|---|
| `enum PtrError` | Errors from pointer arithmetic and pointer-based access. |
| `struct ArenaPtr` | An in-bounds pointer to one node of a region. |
| `fn ArenaPtr::new(layout: &ArenaLayout, region: Region, offset: usize) -> Result<Self, PtrError>` | Pointer to `offset` within `region`. |
| `fn ArenaPtr::from_absolute(layout: &ArenaLayout, index: usize) -> Result<Self, PtrError>` | Pointer to the node at absolute arena index `index`. |
| `fn ArenaPtr::region(&self) -> Region` | The region pointed into. |
| `fn ArenaPtr::offset(&self) -> usize` | Offset within the region. |
| `fn ArenaPtr::add(&self, layout: &ArenaLayout, n: usize) -> Result<Self, PtrError>` | Advance by `n` nodes, staying within the region. |
| `fn ArenaPtr::sub(&self, layout: &ArenaLayout, n: usize) -> Result<Self, PtrError>` | Step back by `n` nodes, staying within the region. |
| `fn ArenaPtr::offset_from(&self, origin: ArenaPtr) -> Result<isize, PtrError>` | Signed distance from `origin` to `self`; both must share a region. |
| `fn ArenaPtr::absolute(&self, layout: &ArenaLayout) -> Result<usize, PtrError>` | Absolute arena index, re-validated against `layout`. |
| `struct NodeRange` | A non-empty run of consecutive nodes within one region. |
| `fn NodeRange::new(layout: &ArenaLayout, region: Region, offset: usize, len: usize) -> Result<Self, PtrError>` | `len` nodes starting at `offset` in `region`. |
| `fn NodeRange::whole_region(layout: &ArenaLayout, region: Region) -> Result<Self, PtrError>` | The whole of `region`. |
| `fn NodeRange::start(&self) -> ArenaPtr` | First node. |
| `fn NodeRange::region(&self) -> Region` | Region of the range. |
| `fn NodeRange::len(&self) -> usize` | Number of nodes. |
| `fn NodeRange::is_empty(&self) -> bool` | Always false: ranges are non-empty by construction. |
| `fn NodeRange::end_offset(&self) -> usize` | Offset one past the last node. |
| `fn NodeRange::contains(&self, ptr: ArenaPtr) -> bool` | Does the range contain `ptr`? |
| `fn NodeRange::overlaps(&self, other: &NodeRange) -> bool` | Do the two ranges share at least one node? |
| `fn NodeRange::ptr_at(&self, layout: &ArenaLayout, i: usize) -> Result<ArenaPtr, PtrError>` | Pointer to the `i`-th node of the range. |
| `fn NodeRange::absolute_range(&self, layout: &ArenaLayout) -> Result<Range<usize>, PtrError>` | Absolute arena indices, re-validated against `layout`. |
| `fn read(arena: &MultiplicityArena, layout: &ArenaLayout, ptr: ArenaPtr) -> Result<GapTensorNode, PtrError>` | Bounds-checked read of one node. |
| `fn write(arena: &mut MultiplicityArena, layout: &ArenaLayout, ptr: ArenaPtr, node: GapTensorNode) -> Result<(), PtrError>` | Bounds-checked write of one node. |
| `fn read_range(arena: &MultiplicityArena, layout: &ArenaLayout, range: NodeRange) -> Result<Vec<GapTensorNode>, PtrError>` | Bounds-checked read of a range. |
| `fn write_range(arena: &mut MultiplicityArena, layout: &ArenaLayout, range: NodeRange, nodes: &[GapTensorNode]) -> Result<(), PtrError>` | Bounds-checked write of a range; `nodes.len()` must equal the range length. |
| `fn sort_range_canonical(arena: &mut MultiplicityArena, layout: &ArenaLayout, range: NodeRange) -> Result<(), PtrError>` | Sort the nodes of `range` into canonical order in place. |

## Tests

`cargo test -p multiplicity_arena_pointers` runs 5 unit tests.
