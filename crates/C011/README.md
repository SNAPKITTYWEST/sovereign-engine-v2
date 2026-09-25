# multiplicity_arena_core (C011)

The primary memory-management primitive for the engine: `MultiplicityArena`, a single contiguous, manually-managed heap allocation of `GapTensorNode`s, plus a bump/spine-style allocator and an iterator over it.

## Public API

- `MultiplicityArena { nodes: *mut GapTensorNode, num_nodes: usize, sealed: bool (private) }`
  - `unsafe fn build_spine(num_nodes) -> Self` — allocates `num_nodes` contiguous, zero-initialized (`GapTensorNode::NIL`) slots via the raw global allocator (`std::alloc::alloc`). Panics on `num_nodes == 0`, layout overflow, or allocation failure (`SIGMA-E-*` panic messages).
  - `unsafe fn get_node(&self, index) -> GapTensorNode` / `unsafe fn set_node(&mut self, index, node)` — raw indexed read/write, bounds-checked only via `debug_assert!` (no bounds check in release).
  - `iter() -> ArenaIter` — safe, safe-to-use forward iterator over all nodes.
  - `is_sealed()` / `mark_sealed()` — tracks whether the arena has passed "G4 certification" (a gate defined elsewhere in the pipeline, not in this crate).
  - `len()`, `is_empty()`.
  - `destroy(self)` — explicit dealloc-and-forget. Frees memory then calls `std::mem::forget(self)` to skip `Drop` (since `Drop` would otherwise double-free).
- `impl Drop for MultiplicityArena` — deallocates if not already destroyed; nulls the pointer afterward as a defensive measure (though this is moot post-drop).
- `ArenaIter<'a>` — yields owned `GapTensorNode` copies (cheap since it's `Copy`), not references.

## Pipeline role

Depends directly on `gap_tensor_core` (C001) for `GapTensorNode`. It is the memory backbone that the (currently unimplemented) `multiplicity_arena_layout/allocation/initialization/pointers/ownership/deallocation/failure_handling/statistics` crates (C012-C019) are scaffolded to extend — presumably to add typed layout policies, safer pointer wrappers, allocation-failure recovery, and usage statistics on top of this raw core.

## Invariants / design notes

- **Manual unsafe allocation, not `Vec`.** The crate deliberately bypasses `Vec<GapTensorNode>` in favor of raw `alloc`/`dealloc` with a hand-rolled `Layout`. This is presumably for FFI/`#[repr(C)]` interop or precise control needed by the "spine" allocation model referenced elsewhere (`build_spine` naming suggests a backbone structure other crates attach to).
- **Double-free trap avoided via `mem::forget`.** `destroy()` frees the buffer explicitly and then `mem::forget`s `self` so `Drop::drop` doesn't run and free it again. Any future refactor of `destroy()` must preserve this pairing — removing the `forget` call (or adding early returns before it) would double-free.
- **`sealed` is a certification flag, not an enforcement mechanism.** Nothing in this crate actually prevents mutation once `sealed == true` — `mark_sealed()` just sets a bool that callers are trusted to check. This is a gap: no `set_node` guard rejects writes to a sealed arena.
- **No bounds checking in release builds.** `get_node`/`set_node` only `debug_assert!`; in a release build, an out-of-range index is UB. Every caller across the workspace must uphold `index < num_nodes` itself.
- **`num_nodes == 0` is explicitly disallowed** (`build_spine` panics), unlike a typical allocator which would permit zero-sized allocations — this reflects a domain invariant that an empty arena is nonsensical for this pipeline.
