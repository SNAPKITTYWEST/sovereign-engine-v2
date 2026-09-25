# derived_homology (C054)

## What it does
Bridges pre-computed `HomologyGroup`s (from C048, supplied externally per degree) into `TorGroup`/`TorComputation` (C051) values — i.e., this is where "Tor = homology of the tensored resolution" is expressed, but the homology itself must already be computed elsewhere and handed in; this crate does no homology computation of its own.

## Public API
- Re-exports `TorComputation`/`TorGroup`/`TorIndex` (C051), `TensorProductModule` (C052), `TensoredComplex` (C053), `HomologyGroup` (C048).
- `compute_tor_from_resolution(&TensoredComplex, &[Option<HomologyGroup>]) -> TorComputation` — for each `Some(hom)` at index `degree`, builds a `TorGroup` with `hom.rank` and torsion converted from `hom.torsion: Vec<u64>` (a flat list of orders) into `TorGroup`'s `BTreeMap<order, multiplicity>` by counting duplicates. Note: the `complex: &TensoredComplex` parameter is **accepted but never read** in the function body — Tor is derived purely from the `homology_groups` slice.
- `verify_tor_computation(&TensoredComplex, &TorComputation) -> bool` — checks `Tor_0` isn't trivial (if present) and that `tor.max_degree() <= complex.num_degrees()`.
- `compute_reduced_tor(&TensoredComplex, vanishing_degree, &[Option<HomologyGroup>]) -> TorComputation` — same conversion as above but only for `degree < vanishing_degree`; also doesn't read `complex`.

## Pipeline position
Depends on `homology_computation` (C048), `tor_functor_definition` (C051), `tensor_product_module` (C052), `resolution_tensored` (C053). Consumed by `tor_zero_structure` (C055), `tor_higher_degrees` (C056), `functoriality_of_tor` (C057), `tor_invariants_computation` (C058), and `tor_chain_complex_interface` (C059) — this is the hub crate of the Tor sub-layer that almost everything downstream re-exports from.

## Notes / gaps
- **Gap:** `compute_tor_from_resolution` and `compute_reduced_tor` both take `&TensoredComplex` but never use it — the actual Tor values come entirely from the caller-supplied `homology_groups` slice. Since C053's `TensoredComplex` doesn't itself compute homology (see C053's own gaps), and this crate doesn't compute homology from the complex either, **there is currently no code path anywhere in C051–C060 that derives `Tor_i(M,N)` from first principles** (an actual differential/resolution) — every test and consumer constructs `TorGroup`s or homology groups by hand. The "derived" in `derived_homology` describes the intended architecture (Tor derived from homology of the tensored complex) rather than what's implemented (Tor copied from externally-supplied homology).
- `verify_tor_computation`'s trivial-Tor_0 check only fires `if let Some(tor_0) = tor.tor(0)` — if degree 0 was never inserted at all, the function skips that check entirely and can return `true` for a `TorComputation` with no `Tor_0` present, which is a different (weaker) notion of "verified" than the name implies.
- 3 unit tests, all using `homology_groups: vec![None; 3]` (i.e., no actual homology data) — none exercise the real conversion-with-torsion path (`Some(hom)` with nonempty `torsion`), so the order→multiplicity counting logic is currently untested.
