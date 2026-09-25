# `multiplicity_arena_core` (C011)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

The MultiplicityArena data structure and bump allocator state management.
This is the primary memory management primitive for the entire system.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C004 `gap_tensor_shape`](../C004/README.md)

## Re-exports

- `gap_tensor_core::GapTensorNode`

## Public API

| Item | Description |
|---|---|
| `struct MultiplicityArena` | The multiplicity arena: a single contiguous block of allocated GapTensorNodes. |
| `unsafe MultiplicityArena::fn build_spine(num_nodes: usize) -> Self` | Build a new arena spine. |
| `unsafe MultiplicityArena::fn get_node(&self, index: usize) -> GapTensorNode` | Access a node at the given index (0-based). |
| `unsafe MultiplicityArena::fn set_node(&mut self, index: usize, node: GapTensorNode)` | Set a node at the given index. |
| `fn MultiplicityArena::iter(&self) -> ArenaIter<'_>` | Immutably iterate over all nodes in the arena. |
| `fn MultiplicityArena::is_sealed(&self) -> bool` | Is this arena sealed? |
| `fn MultiplicityArena::mark_sealed(&mut self)` | Mark this arena as sealed (passed G4 certification). |
| `fn MultiplicityArena::len(&self) -> usize` | Get the number of nodes. |
| `fn MultiplicityArena::is_empty(&self) -> bool` | Is the arena empty? |
| `fn MultiplicityArena::destroy(self)` | Destroy the arena and free all memory. |
| `struct ArenaIter<'a>` | Iterator over arena nodes. |

## Tests

`cargo test -p multiplicity_arena_core` runs 3 unit tests.
