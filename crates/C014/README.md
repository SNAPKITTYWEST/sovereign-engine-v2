# `multiplicity_arena_initialization` (C014)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

Arena bootstrap: allocate an arena for a layout, load the initial TEXT and
DATA images, and hand out an  with safe, bounds-checked
access. TEXT is read-only after bootstrap, and a sealed arena accepts no
writes at all.

## Dependencies

- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)

## Public API

| Item | Description |
|---|---|
| `enum InitError` | Errors from bootstrap and access. |
| `struct InitializedArena` | An arena bootstrapped for a specific layout. |
| `fn InitializedArena::bootstrap(layout: ArenaLayout, text: &[GapTensorNode], data: &[GapTensorNode]) -> Result<Self, InitError>` | Allocate and load TEXT and DATA images. |
| `fn InitializedArena::empty(layout: ArenaLayout) -> Self` | A Nil-filled arena for `layout`. |
| `fn InitializedArena::layout(&self) -> &ArenaLayout` | The layout. |
| `fn InitializedArena::arena(&self) -> &MultiplicityArena` | The underlying arena. |
| `fn InitializedArena::arena_mut(&mut self) -> &mut MultiplicityArena` | Mutable access to the underlying arena, for the checked APIs of other arena crates (which re-validate layout and seal). |
| `fn InitializedArena::get(&self, index: usize) -> Result<GapTensorNode, InitError>` | Read node `index`. |
| `fn InitializedArena::set(&mut self, index: usize, node: GapTensorNode) -> Result<(), InitError>` | Write node `index`. |
| `fn InitializedArena::region(&self, region: Region) -> Result<Vec<GapTensorNode>, InitError>` | Copy out the nodes of `region`. |
| `fn InitializedArena::seal(&mut self)` | Seal the arena (no further writes through any checked API). |
| `fn InitializedArena::is_sealed(&self) -> bool` | Is the arena sealed? |
| `fn InitializedArena::into_parts(self) -> (MultiplicityArena, ArenaLayout)` | Split into the raw arena and its layout. |

## Tests

`cargo test -p multiplicity_arena_initialization` runs 4 unit tests.
