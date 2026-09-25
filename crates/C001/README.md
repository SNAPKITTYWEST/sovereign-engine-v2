# gap_tensor_core (C001)

Core primitive of the Tier 0 subsystem: `GapTensorNode`, a fixed-size record representing one element of the "gap tensor" — a prime value paired with a multiplicity (occurrence count) and a spectral weight (energy/resonance contribution).

## Public API

- `SIGMA_GAP_MAX: u32 = 8` — the maximum permitted prime gap; anything larger is treated as "dissonance" downstream.
- `CANDIDATE_PRIMES: [u32; 6] = [2, 3, 5, 7, 11, 13]` — the fixed axis of primes the tensor indexes over.
- `GapTensorNode { prime_val, multiplicity, spectral_weight }` — `#[repr(C)]`, `Copy`, `Ord`/`Hash`-able.
  - `GapTensorNode::NIL` — the contradiction/zero state (`prime_val == 0`).
  - `RESONANCE_MIN: f32 = 1.0` — threshold a node's `resonance()` must clear to "participate in a contraction."
  - `new(prime_val, multiplicity, spectral_weight)`, `resonance()` (= `multiplicity * spectral_weight`), `is_nil()`, `is_prime()`, `axis_index()` (position in `CANDIDATE_PRIMES`, or `None` if nil), `prime_opt()`.

## Pipeline role

This is the root type of the whole engine — every other crate in the `gap_tensor_*` and `multiplicity_arena_*` families (C002-C020) is a stub that will eventually build on `GapTensorNode`, and `multiplicity_arena_core` (C011) directly allocates arrays of it. Nothing feeds into C001; it has zero crate dependencies.

## Invariants / design notes

- `prime_val == 0` is the sentinel "Nil" / contradiction state — not a valid prime. Callers must not assume `0` is a legitimate tensor value.
- `Ord`/`PartialOrd` are hand-implemented (not `derive`d) with a fixed field order: prime_val, then multiplicity, then spectral_weight (with NaN treated as `Equal` via `unwrap_or`). This total order is what `multiplicity_arena` iteration/sorting will rely on.
- `Hash` is manually implemented over `spectral_weight.to_bits()` (not the float directly), since `f32` isn't `Hash`/`Eq` by default — this is why `Eq` is also manually asserted (`impl Eq for GapTensorNode {}`) despite the float field.
- `axis_index` gives an implicit encoding from prime value to array position, used to map a node onto a 6-wide tensor axis without a lookup table at each call site (it's a linear scan of a 6-element array — fine at this size, would not scale if `CANDIDATE_PRIMES` grew significantly).
