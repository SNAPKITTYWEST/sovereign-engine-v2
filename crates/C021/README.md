# prime_predicate (C021)

Foundation of the Tier 2 prime/gap engine: basic primality testing and the bridge from a raw `u64` prime to a `GapTensorNode`.

## Public API

- `is_prime(n: u64) -> bool` — trial division up to `sqrt(n)`, stepping by 2 after handling 0/1/2/even specially. Straightforward, not optimized for large `n`.
- `is_prime_candidate(n: u64) -> bool` — 6k±1 wheel-filtered primality check. Functionally a second, independent primality test (not a "fast prefilter" that then defers to `is_prime` — despite the doc comment saying "fast heuristic," it is actually a complete, correct primality test itself).
- `prime_to_tensor_node(prime: u64) -> GapTensorNode` — wraps a prime as a tensor node with `multiplicity = 1`, `spectral_weight = 1.0`.

## Pipeline role

Depends on `gap_tensor_core` (C001) for `GapTensorNode`. It is the entry point of Tier 2 (prime/gap logic): `prime_enumeration` (C022) re-exports `is_prime`/`is_prime_candidate` and builds sieve-based enumeration on top.

## Invariants / design notes

- `prime_to_tensor_node` silently narrows `prime: u64` to `prime_val: u32` (`prime as u32`) with no overflow check — any prime above `u32::MAX` truncates silently. Given `GapTensorNode::prime_val` is `u32`, this is a real width mismatch baked into the API boundary between Tier 1 (`u32`-based tensor) and Tier 2 (`u64`-based prime math).

## Gaps / TODOs

- **Doc/behavior mismatch:** the module comment calls `is_prime_candidate` a "fast heuristic that catches obvious composites," but it's actually a full deterministic primality test (6k±1 trial division) — functionally redundant with `is_prime`, just implemented differently. A newcomer reading only the doc comment would assume it can produce false positives; it cannot.
- No overflow check/error on `prime_to_tensor_node` when `prime > u32::MAX`.
- `is_prime` uses naive trial division — fine for the small values seen in tests (up to ~30) but not something to rely on for large-scale enumeration; `prime_enumeration`'s sieve is the actual scalable path.
