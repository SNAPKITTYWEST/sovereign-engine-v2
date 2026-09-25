# multiplicity_arena_pointers (C015)

**Status: unimplemented scaffold.** The crate is currently only a stub — `src/lib.rs` is 7 lines: a module doc comment, `#![warn(missing_docs)]`, and a `// Scaffold: Add your code here.` marker. It compiles (empty lib) but exports nothing.

## Intended purpose

Safe(r) pointer wrappers around MultiplicityArena's raw *mut GapTensorNode, likely to replace the unsafe get_node/set_node call sites.

## Pipeline role

Part of the multiplicity_arena_* family rooted at `gap_tensor_core` (C001) and `multiplicity_arena_core` (C011). No `[dependencies]` are declared in `Cargo.toml` yet, so even the expected dependency on C001/C011 has not been wired up.

## Gaps / TODOs

- No implementation: this is a pure placeholder crate.
- No dependency on `gap_tensor_core`/`multiplicity_arena_core` declared, despite the name implying it operates on `GapTensorNode`/`MultiplicityArena`.
- No tests.
- `#![warn(missing_docs)]` is present but moot with no public items to document.
