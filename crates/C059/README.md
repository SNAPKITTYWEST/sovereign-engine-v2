# tor_chain_complex_interface (C059)

## What it does
Packages a `ProjectiveResolution` together with its `TorComputation` and derived `BettiNumbers` into one bundle (`TorChainComplexData`), and exposes a simplified `ChainComplexInterface` (degree count, total rank, regularity) for consumers outside the Tor sub-layer that don't need the full Tor detail — likely the runtime-binding/certification layer beyond C060.

## Public API
- Re-exports `ProjectiveResolution` (C046), `TorComputation` (C051), `compute_tor_from_resolution` (C054, unused in this crate's own code — re-export only), `BettiNumbers`/`compute_betti_numbers` (C058).
- `TorChainComplexData { resolution, tor, betti }` — `from_resolution(ProjectiveResolution)` (initializes with an **empty** `TorComputation` — does not actually compute Tor from the resolution despite taking one; see gap), `update_tor(TorComputation)` (recomputes `betti` as a side effect), `as_complex_data() -> ChainComplexInterface`.
- `ChainComplexInterface { num_degrees, total_rank, regularity }` — `is_bounded()` (both `num_degrees > 0` and `regularity.is_some()`), `is_acyclic()` (`regularity == Some(0)` — i.e., only `Tor_0` is present/nontrivial; see naming caveat under C058's `regularity()`).
- `tor_to_complex_data(&TorComputation, resolution_length) -> ChainComplexInterface` — free-function equivalent of `as_complex_data()` for when you have a `TorComputation` but not a full `TorChainComplexData`.

## Pipeline position
Depends on `projective_resolution` (C046), `tor_functor_definition` (C051), `derived_homology` (C054, re-export only), `tor_invariants_computation` (C058). This is the terminal packaging crate of the Tor sub-layer before `tor_tests_integration` (C060) — it's the type most likely to be consumed by the runtime-binding/Lean-correspondence layer (outside C031–C060) since it flattens Tor + resolution + Betti data into one interface struct.

## Notes / gaps
- **Gap — `from_resolution` doesn't compute anything from the resolution:** despite the name and taking a `ProjectiveResolution` by value, the constructor discards any relationship between the resolution and Tor — it just calls `TorComputation::new()` (empty) and computes Betti numbers from that empty computation (always zero). The resolution is stored (`self.resolution = resolution`) but nothing derives `tor` from it. A caller must separately compute a `TorComputation` (via C054's `compute_tor_from_resolution`, itself limited per its own README) and call `update_tor()` afterward to get a populated, consistent `TorChainComplexData`. This mirrors the same "wiring gap" documented in C053/C054 — the Tor sub-layer's types are all present and individually testable, but the actual data flow from resolution → tensored complex → homology → Tor → this bundle is not automatically connected anywhere in the crate graph.
- `is_acyclic()` inherits C058's `regularity()` naming caveat: "acyclic" here means "top computed Tor degree is 0," not the standard meaning (all reduced homology vanishes) unless `regularity()`'s definition happens to coincide in the caller's specific case.
- 3 unit tests, all constructing `ChainComplexInterface` directly or from an empty `TorComputation` — none exercise `TorChainComplexData::from_resolution` combined with `update_tor` together, so the intended two-step wiring pattern isn't demonstrated or tested end-to-end.
