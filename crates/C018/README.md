# `multiplicity_arena_failure_handling` (C018)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

Fail-closed arena management. Allocation is checked against a node
budget before any memory is requested, and a  that hits
a fault (out-of-bounds access or a capacity request it cannot satisfy)
poisons itself: it records a snapshot of its contents in a tamper-evident
trace, scrubs and frees its memory, and refuses every later operation.

Allocator failure inside the system allocator is not recoverable here:
`MultiplicityArena::build_spine` panics on a null allocation. The budget
check keeps requests well-formed and bounded so that path is reserved for
genuine system out-of-memory.

## Dependencies

- [C010 `gap_tensor_trace`](../C010/README.md)
- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)

## Public API

| Item | Description |
|---|---|
| `struct ArenaBudget` | Upper bound on arena size, in nodes. |
| `enum ArenaFailure` | Failures of a fail-closed arena. |
| `fn try_allocate(layout: &ArenaLayout, budget: &ArenaBudget) -> Result<MultiplicityArena, ArenaFailure>` | Allocate an arena for `layout` if it fits `budget`. |
| `struct FailClosedArena` | An arena that shuts down permanently on its first fault. |
| `fn FailClosedArena::open(layout: ArenaLayout, budget: &ArenaBudget) -> Result<Self, ArenaFailure>` | Allocate within `budget`. |
| `fn FailClosedArena::layout(&self) -> &ArenaLayout` | The layout. |
| `fn FailClosedArena::is_poisoned(&self) -> bool` | Has a fault occurred? |
| `fn FailClosedArena::poison_reason(&self) -> Option<&str>` | Reason for the first fault, if any. |
| `fn FailClosedArena::failure_log(&self) -> &TensorTrace` | Snapshots recorded at faults. |
| `fn FailClosedArena::read(&mut self, index: usize) -> Result<GapTensorNode, ArenaFailure>` | Read node `index`. |
| `fn FailClosedArena::write(&mut self, index: usize, node: GapTensorNode) -> Result<(), ArenaFailure>` | Write node `index`. |
| `fn FailClosedArena::require_capacity(&mut self, needed: usize) -> Result<(), ArenaFailure>` | Declare that the next piece of work needs `needed` nodes. |
| `fn FailClosedArena::poison(&mut self, reason: impl Into<String>)` | Poison the arena: snapshot it into the failure log, scrub it to Nil and free it. |
| `fn FailClosedArena::into_arena(mut self) -> Result<MultiplicityArena, ArenaFailure>` | Take the arena back out, if no fault occurred. |

## Tests

`cargo test -p multiplicity_arena_failure_handling` runs 5 unit tests.
