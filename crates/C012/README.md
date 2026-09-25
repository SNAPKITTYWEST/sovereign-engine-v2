# `multiplicity_arena_layout` (C012)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

Partition of a multiplicity arena into four contiguous regions laid out
in order — TEXT, DATA, STACK, HEAP — plus region-level reads and writes
that are bounds-checked against the layout.

A sealed arena (one that has passed certification) is treated as
immutable: every write path here refuses it.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C004 `gap_tensor_shape`](../C004/README.md)
- [C011 `multiplicity_arena_core`](../C011/README.md)

## Re-exports

- `gap_tensor_core::GapTensorNode`
- `multiplicity_arena_core::MultiplicityArena`

## Public API

| Item | Description |
|---|---|
| `enum Region` | One of the four arena regions. |
| `const Region::ALL: [Region` | All regions in layout order. |
| `struct RegionSpan` | A half-open span `[start, start + len)` of arena node indices. |
| `fn RegionSpan::end(&self) -> usize` | One past the last node index. |
| `fn RegionSpan::contains(&self, index: usize) -> bool` | Does the span contain `index`? |
| `fn RegionSpan::is_empty(&self) -> bool` | Is the span zero-length? |
| `enum LayoutError` | Errors from layout construction and region access. |
| `struct ArenaLayout` | Region partition of an arena. |
| `fn ArenaLayout::new(text: usize, data: usize, stack: usize, heap: usize) -> Result<Self, LayoutError>` | Lay out the four regions contiguously. |
| `fn ArenaLayout::for_tensor(shape: &TensorShape, text: usize, stack: usize, heap: usize) -> Result<Self, LayoutError>` | A layout whose DATA region holds exactly one tensor of `shape`. |
| `fn ArenaLayout::span(&self, region: Region) -> RegionSpan` | The span of `region`. |
| `fn ArenaLayout::total(&self) -> usize` | Total nodes across all regions. |
| `fn ArenaLayout::region_of(&self, index: usize) -> Option<Region>` | The region containing node `index`, if any. |
| `fn ArenaLayout::allocate(&self) -> MultiplicityArena` | Allocate a Nil-filled arena sized for this layout. |
| `fn ArenaLayout::check_arena(&self, arena: &MultiplicityArena) -> Result<(), LayoutError>` | Check that `arena` was allocated for this layout. |
| `fn ArenaLayout::check_writable(&self, arena: &MultiplicityArena) -> Result<(), LayoutError>` | Check that `arena` matches this layout and is not sealed. |
| `fn ArenaLayout::read_region(&self, arena: &MultiplicityArena, region: Region) -> Result<Vec<GapTensorNode>, LayoutError>` | Copy out every node of `region`. |
| `fn ArenaLayout::write_region(&self, arena: &mut MultiplicityArena, region: Region, nodes: &[GapTensorNode]) -> Result<(), LayoutError>` | Write `nodes` to the start of `region`; the rest of the region is left unchanged. |
| `fn ArenaLayout::fill_region(&self, arena: &mut MultiplicityArena, region: Region, node: GapTensorNode) -> Result<(), LayoutError>` | Set every node of `region` to `node`. |

## Tests

`cargo test -p multiplicity_arena_layout` runs 5 unit tests.
