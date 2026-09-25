# `multiplicity_arena_statistics` (C019)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

Usage tracking for arenas and bump allocators: occupancy of an arena,
utilization of an allocator, and a tracker that records peak usage and
allocation successes and failures over time.

## Dependencies

- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C013 `multiplicity_arena_allocation`](../C013/README.md)

## Public API

| Item | Description |
|---|---|
| `struct ArenaStats` | Contents of an arena. |
| `fn ArenaStats::occupancy(&self) -> f64` | Fraction of nodes that are live. |
| `fn arena_stats(arena: &MultiplicityArena) -> ArenaStats` | Scan an arena. |
| `struct AllocatorStats` | State of a bump allocator. |
| `fn AllocatorStats::utilization(&self) -> f64` | Fraction of capacity in use. |
| `fn allocator_stats(allocator: &BumpAllocator) -> AllocatorStats` | Snapshot an allocator. |
| `struct UsageTracker` | Records allocation outcomes and peak usage. |
| `fn UsageTracker::new() -> Self` | Nothing recorded. |
| `fn UsageTracker::alloc(&mut self, allocator: &mut BumpAllocator, layout: &ArenaLayout, len: usize) -> Result<NodeRange, AllocError>` | Allocate through `allocator`, recording the outcome. |
| `fn UsageTracker::observe(&mut self, allocator: &BumpAllocator)` | Update peak usage from the allocator's current state. |
| `fn UsageTracker::peak_used(&self) -> usize` | Highest `used` value observed. |
| `fn UsageTracker::successes(&self) -> u64` | Successful allocations recorded. |
| `fn UsageTracker::failures(&self) -> u64` | Failed allocations recorded. |
| `fn UsageTracker::nodes_allocated(&self) -> u64` | Nodes handed out by recorded allocations. |

## Tests

`cargo test -p multiplicity_arena_statistics` runs 2 unit tests.
