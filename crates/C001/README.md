# `gap_tensor_core` (C001)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

Core GapTensorNode struct and fundamental operations on tensor nodes.
This is the root primitive of the Tier 0 subsystem.

## Dependencies

None.

## Public API

| Item | Description |
|---|---|
| `const SIGMA_GAP_MAX: u32 = 8` | The maximum permitted prime gap. |
| `const CANDIDATE_PRIMES: [u32` | The permitted prime eigenvalues. |
| `struct GapTensorNode` | Core tensor node: represents a single element in the gap tensor. |
| `const GapTensorNode::NIL: Self = Self` | The Nil (contradiction) node: all fields are zero. |
| `const GapTensorNode::RESONANCE_MIN: f32 = 1.0` | Minimum resonance weight required for a node to participate. |
| `fn GapTensorNode::resonance(&self) -> f32` | Compute the resonance (energy) of this node. |
| `fn GapTensorNode::is_nil(&self) -> bool` | Is this node in the Nil (contradiction) state? |
| `fn GapTensorNode::is_prime(&self) -> bool` | Is this node a valid prime (non-nil)? |
| `fn GapTensorNode::new(prime_val: u32, multiplicity: u32, spectral_weight: f32) -> Self` | Create a new GapTensorNode with the given parameters. |
| `fn GapTensorNode::axis_index(&self) -> Option<usize>` | Axis index: used for canonical indexing within tensors. |
| `fn GapTensorNode::prime_opt(&self) -> Option<u32>` | Get the prime value, or None if Nil. |

## Tests

`cargo test -p gap_tensor_core` runs 4 unit tests.
