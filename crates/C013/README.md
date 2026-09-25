# `multiplicity_arena_allocation` (C013)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

O(1) bump allocation of node ranges within one arena region. Allocation
only moves a cursor; `mark`/`release_to` give stack-discipline rollback
and `reset` frees the whole region in O(1).

## Dependencies

- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)
- [C015 `multiplicity_arena_pointers`](../C015/README.md)

## Re-exports

- `multiplicity_arena_core::{GapTensorNode, MultiplicityArena}`
- `multiplicity_arena_layout::{ArenaLayout, Region}`
- `multiplicity_arena_pointers::{ArenaPtr, NodeRange, PtrError}`

## Public API

| Item | Description |
|---|---|
| `enum AllocError` | Errors from allocation. |
| `struct AllocMark(usize)` | A saved cursor position for `BumpAllocator::release_to`. |
| `struct BumpAllocator` | Bump allocator over one region. |
| `fn BumpAllocator::new(layout: &ArenaLayout, region: Region) -> Self` | An empty allocator over `region` of `layout`. |
| `fn BumpAllocator::region(&self) -> Region` | Region served. |
| `fn BumpAllocator::capacity(&self) -> usize` | Region capacity in nodes. |
| `fn BumpAllocator::used(&self) -> usize` | Nodes handed out since the last reset. |
| `fn BumpAllocator::remaining(&self) -> usize` | Nodes still available. |
| `fn BumpAllocator::allocation_count(&self) -> u64` | Successful allocations over the allocator's lifetime. |
| `fn BumpAllocator::alloc(&mut self, layout: &ArenaLayout, len: usize) -> Result<NodeRange, AllocError>` | Allocate `len` nodes. |
| `fn BumpAllocator::alloc_zeroed(&mut self, arena: &mut MultiplicityArena, layout: &ArenaLayout, len: usize) -> Result<NodeRange, AllocError>` | Allocate `len` nodes and Nil-fill them. |
| `fn BumpAllocator::mark(&self) -> AllocMark` | Current cursor position. |
| `fn BumpAllocator::release_to(&mut self, mark: AllocMark) -> Result<(), AllocError>` | Free everything allocated after `mark`. |
| `fn BumpAllocator::reset(&mut self)` | Free everything. |

## Tests

`cargo test -p multiplicity_arena_allocation` runs 4 unit tests.
