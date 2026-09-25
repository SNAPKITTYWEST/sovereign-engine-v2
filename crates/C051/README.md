# tor_functor_definition (C051)

## What it does
Defines the core data types for the Tor functor `Tor^i_R(M, N)`: a degree index, a single Tor group (rank + torsion, keyed by torsion order), and a `TorComputation` collecting Tor groups across degrees, independent of *how* they were computed.

## Public API
- `TorIndex { degree }` — `new()`, `is_zero()`, `is_higher()`.
- `TorGroup { index, rank, torsion: BTreeMap<u64, usize> }` — `new()`, `add_torsion(order, multiplicity)` (accumulates), `is_trivial()`, `num_generators()` (rank + sum of torsion multiplicities), `torsion_exponent()` (LCM of all distinct torsion orders present, via a local recursive `gcd`/`lcm`).
- `TorComputation { groups: BTreeMap<usize, TorGroup> }` — `new()`, `insert_tor()`, `tor(degree)`, `tor_mut(degree)`, `max_degree()`, `is_split_exact()` (true iff every `Tor_i` for `i > 0` present is trivial — vacuously true if none are present).

## Pipeline position
No crate dependencies at all — this is the foundational, dependency-free vocabulary type for the entire Tor sub-layer (C051–C060), analogous to what C031 is for the recursive-solver layer and C041 is for chain complexes. It depends on `chain_complex_shape` (C041), `differential_squared_zero` (C044), `projective_resolution` (C046), and `homology_computation` (C048) per Cargo.toml, but **none of these are referenced in `lib.rs`** — all four are dead dependencies; the crate is pure `BTreeMap`/arithmetic with zero coupling to the rest of the homological layer at the type level.

## Notes / gaps
- **Gap:** `TorGroup`'s `torsion: BTreeMap<u64, usize>` stores order-to-multiplicity, but C048's `HomologyGroup.torsion` is a flat `Vec<u64>` of orders (no multiplicity tracking) — the two crates' torsion representations don't line up 1:1. C054 (`derived_homology`) bridges this by counting duplicate orders in the `Vec` into a multiplicity map before calling `add_torsion`, so the conversion is handled, but it's worth knowing these are structurally different torsion representations at the two ends.
- Four declared dependencies unused — significant dead weight for a foundational, otherwise-clean crate.
- 4 unit tests, including a genuinely useful LCM-based torsion-exponent test with two different order sets.
