# `gap_tensor_spectral` (C003)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

Spectral decomposition of a set of gap tensor nodes: resonance per
candidate-prime axis, dominant prime, normalized spectrum and spectral
entropy.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C002 `gap_tensor_primes`](../C002/README.md)

## Public API

| Item | Description |
|---|---|
| `type Spectrum = [f32` | Resonance per candidate-prime axis, indexed like `CANDIDATE_PRIMES`. |
| `struct SpectralDecomposition` | Resonance of a node set, split by candidate-prime axis. |
| `fn decompose(nodes: &[GapTensorNode]) -> SpectralDecomposition` | Decompose the resonance of `nodes` onto the candidate-prime axes. |
| `fn SpectralDecomposition::total(&self) -> f32` | Total resonance, on-axis plus off-axis. |
| `fn SpectralDecomposition::on_axis_total(&self) -> f32` | Resonance carried by the candidate axes only. |
| `fn SpectralDecomposition::dominant_prime(&self) -> Option<u32>` | The candidate prime with the largest positive, finite resonance. |
| `fn SpectralDecomposition::normalized(&self) -> Option<Spectrum>` | The on-axis spectrum scaled to sum to 1. |
| `fn SpectralDecomposition::entropy(&self) -> Option<f32>` | Shannon entropy (bits) of the normalized spectrum. |
| `fn participating(nodes: &[GapTensorNode]) -> Vec<GapTensorNode>` | Nodes whose resonance reaches `GapTensorNode::RESONANCE_MIN`. |

## Tests

`cargo test -p gap_tensor_spectral` runs 5 unit tests.
