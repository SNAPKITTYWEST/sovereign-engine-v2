# `multiplicity_arena_deallocation` (C017)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

Region drain and reset with rollback. Draining Nil-fills a region and
returns a  of its previous contents;  restores
it. A region cannot be drained while any lease on it is outstanding, and
 is all-or-nothing.

## Dependencies

- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)
- [C016 `multiplicity_arena_ownership`](../C016/README.md)

## Public API

| Item | Description |
|---|---|
| `struct Checkpoint` | Saved contents of one region. |
| `fn Checkpoint::region(&self) -> Region` | The region saved. |
| `fn Checkpoint::nodes(&self) -> &[GapTensorNode]` | The saved nodes. |
| `enum DeallocError` | Errors from drain, reset and rollback. |
| `fn checkpoint(arena: &MultiplicityArena, layout: &ArenaLayout, region: Region) -> Result<Checkpoint, DeallocError>` | Save the contents of `region`. |
| `fn drain_region(arena: &mut MultiplicityArena, layout: &ArenaLayout, region: Region, tracker: &OwnershipTracker) -> Result<Checkpoint, DeallocError>` | Nil-fill `region`, returning a checkpoint of what was there. |
| `fn rollback(arena: &mut MultiplicityArena, layout: &ArenaLayout, checkpoint: &Checkpoint) -> Result<(), DeallocError>` | Restore a region from a checkpoint. |
| `fn reset_all(arena: &mut MultiplicityArena, layout: &ArenaLayout, tracker: &OwnershipTracker) -> Result<Vec<Checkpoint>, DeallocError>` | Drain every region. |
| `fn with_rollback<T, E, F>(arena: &mut MultiplicityArena, layout: &ArenaLayout, f: F) -> Result<Result<T, E>, DeallocError> where` | Run `f` on the arena. |

## Tests

`cargo test -p multiplicity_arena_deallocation` runs 4 unit tests.
