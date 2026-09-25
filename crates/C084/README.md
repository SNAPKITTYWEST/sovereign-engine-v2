# `multiplicity_state_binding` (C084)

Tier 8 — runtime bridge. *Generated from the crate source; regenerate after API changes.*

Binds a live multiplicity arena (Tier 1) to the runtime snapshot store:
the DATA region is recorded after every write and when the arena is
sealed. Claims (arena matches its layout, snapshots are faithful, a
sealed arena never changes, history intact) are re-checkable.

## Dependencies

- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)
- [C081 `runtime_state_snapshot`](../C081/README.md)

## Re-exports

- `multiplicity_arena_layout::{ArenaLayout, LayoutError, Region}`

## Public API

| Item | Description |
|---|---|
| `struct ArenaBinding` | An arena whose DATA region is recorded. |
| `fn ArenaBinding::new(name: impl Into<String>, layout: ArenaLayout) -> Result<Self, LayoutError>` | Allocate an arena for `layout` and record its (Nil) DATA region. |
| `fn ArenaBinding::data_state(&self) -> Result<GapTensor, LayoutError>` | The DATA region as a tensor. |
| `fn ArenaBinding::write_data(&mut self, nodes: &[GapTensorNode]) -> Result<(), LayoutError>` | Write the start of the DATA region and record it. |
| `fn ArenaBinding::seal(&mut self) -> Result<(), LayoutError>` | Seal the arena and record the sealed state. |
| `fn ArenaBinding::layout(&self) -> &ArenaLayout` | The layout. |
| `fn ArenaBinding::arena(&self) -> &MultiplicityArena` | The arena. |
| `fn ArenaBinding::store(&self) -> &SnapshotStore` | Recorded history. |
| `fn ArenaBinding::is_sealed(&self) -> bool` | Is the arena sealed? |
| `fn ArenaBinding::arena_mut_for_testing(&mut self) -> &mut MultiplicityArena` | Mutable arena access for fault-injection tests (bypasses recording). |

## Tests

`cargo test -p multiplicity_state_binding` runs 3 unit tests.
