# `gap_tensor_primes` (C002)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

Prime-level operations over the candidate prime set used by the gap
tensor: candidate lookup, neighbouring candidates, gaps between
candidates, and validated node construction.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)

## Public API

| Item | Description |
|---|---|
| `const NUM_CANDIDATES: usize = CANDIDATE_PRIMES.len()` | Number of candidate primes (tensor axes). |
| `enum PrimeError` | Errors from prime-level node operations. |
| `fn is_candidate_prime(p: u32) -> bool` | Is `p` one of the candidate primes? |
| `fn candidate_index(p: u32) -> Option<usize>` | Position of `p` in `CANDIDATE_PRIMES`, if it is a candidate. |
| `fn candidate_at(index: usize) -> Option<u32>` | The candidate prime at `index`, if in range. |
| `fn next_candidate(p: u32) -> Option<u32>` | The next larger candidate prime after `p`. |
| `fn prev_candidate(p: u32) -> Option<u32>` | The next smaller candidate prime before `p`. |
| `fn candidate_gaps() -> [u32` | Gaps between consecutive candidate primes, in order. |
| `fn is_consonant_gap(gap: u32) -> bool` | A gap is consonant iff it does not exceed `SIGMA_GAP_MAX`. |
| `fn node_gap(a: &GapTensorNode, b: &GapTensorNode) -> Result<u32, PrimeError>` | Absolute difference between the primes of two nodes. |
| `fn candidate_node(prime: u32, multiplicity: u32, spectral_weight: f32) -> Result<GapTensorNode, PrimeError>` | Build a node whose prime is checked against `CANDIDATE_PRIMES`. |
| `fn validate_node(node: &GapTensorNode) -> Result<(), PrimeError>` | A node is well-formed at the prime level iff it is Nil or carries a candidate prime. |
| `fn is_prime(n: u32) -> bool` | Deterministic primality test by trial division. |

## Tests

`cargo test -p gap_tensor_primes` runs 6 unit tests.
