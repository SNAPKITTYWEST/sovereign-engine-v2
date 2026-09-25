# functoriality_of_tor (C057)

## What it does
Models functoriality of Tor: a module homomorphism `f: M -> M'` should induce a map on `Tor_i(M,N) -> Tor_i(M',N)`. Provides `ModuleMap` (dense integer matrix) and functions to induce/compose such maps — though the induced-map construction is explicitly a placeholder, not a real functorial construction.

## Public API
- Re-exports `TorGroup`/`TorComputation` (C051), `verify_tor_computation` (C054, unused in this crate's own code — re-export only).
- `ModuleMap { source_rank, target_rank, matrix: Vec<i32> }` (row-major, flattened) — `new()`, `set(i,j,val)`/`get(i,j)` (bounds-checked, silently no-op/return-0 out of range), `is_injective()` (see gap — not a real injectivity check), `is_surjective()` (see gap).
- `induced_tor_map(&TorGroup, &TorGroup, &ModuleMap) -> ModuleMap` — see gap, does not actually compose with the Tor functor.
- `compose_tor_maps(&ModuleMap, &ModuleMap) -> Option<ModuleMap>` — real matrix multiplication, `None` on dimension mismatch (`f.target_rank != g.source_rank`).

## Pipeline position
Depends on `tor_functor_definition` (C051) and `derived_homology` (C054, re-export only). Consumed by `tor_tests_integration` (C060).

## Notes / gaps
- **Gap — `is_injective`/`is_surjective` are not real linear-algebra checks:** `is_injective()` returns `true` if *any* matrix entry is nonzero (`self.matrix.iter().any(|&e| e != 0)`) — this is true for almost any nontrivial map regardless of actual injectivity (e.g., a map with a huge kernel but one stray nonzero entry would report "injective"). `is_surjective()` compounds this by additionally requiring `source_rank >= target_rank`, a necessary-but-far-from-sufficient dimension condition. Both are explicitly labeled "Simplified" in their own comments.
- **Gap — `induced_tor_map` does not implement functoriality:** per its own comment, "In a real implementation, this would compose the resolution map with Tor functor. For now, create a compatible map." The actual body: if `f.is_injective()` (using the weak check above), it sets a partial identity matrix (`induced.set(i, i, 1)` for `i` up to `min(source_gens, target_gens)`) and otherwise returns the zero map. This is a placeholder shape-compatible stand-in, not a computation derived from `f`'s actual entries or from the resolution structure — the *values* of `f`'s matrix beyond "any nonzero entry present" play no role in the result.
- `compose_tor_maps` is the one genuinely complete piece of math in this crate: real triple-loop matrix multiplication with correct dimension-mismatch handling via `Option`.
- 5 unit tests — `test_module_map_injective` only checks the (weak) "any nonzero entry" condition and would pass under the current implementation even for a rank-deficient map, so it doesn't catch the gap above (nor is it expected to, since it's testing the code as written).
