//! gap_tensor_core
//!
//! Core GapTensorNode struct and fundamental operations on tensor nodes.
//! This is the root primitive of the Tier 0 subsystem.

#![warn(missing_docs)]

use std::hash::{Hash, Hasher};

/// The maximum permitted prime gap. Any larger gap is dissonance.
pub const SIGMA_GAP_MAX: u32 = 8;

/// The permitted prime eigenvalues. Nil (0) is the contradiction state.
pub const CANDIDATE_PRIMES: [u32; 6] = [2, 3, 5, 7, 11, 13];

/// Core tensor node: represents a single element in the gap tensor.
///
/// This is the fundamental building block of all multiplicity arenas.
/// Each node carries a prime value, multiplicity (occurrence count),
/// and spectral weight (energy density in the manifold).
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GapTensorNode {
    /// The prime value associated with this node. 0 means Nil (contradiction state).
    pub prime_val: u32,
    /// Multiplicity: how many times this prime appears in this position.
    pub multiplicity: u32,
    /// Spectral weight: energy/resonance contribution of this node.
    pub spectral_weight: f32,
}

impl GapTensorNode {
    /// The Nil (contradiction) node: all fields are zero.
    pub const NIL: Self = Self {
        prime_val: 0,
        multiplicity: 0,
        spectral_weight: 0.0,
    };

    /// Minimum resonance weight required for a node to participate.
    pub const RESONANCE_MIN: f32 = 1.0;

    /// Compute the resonance (energy) of this node.
    ///
    /// Resonance = multiplicity × spectral_weight.
    /// A node participates in a contraction iff resonance >= RESONANCE_MIN.
    pub fn resonance(&self) -> f32 {
        self.multiplicity as f32 * self.spectral_weight
    }

    /// Is this node in the Nil (contradiction) state?
    pub fn is_nil(&self) -> bool {
        self.prime_val == 0
    }

    /// Is this node a valid prime (non-nil)?
    pub fn is_prime(&self) -> bool {
        self.prime_val != 0
    }

    /// Create a new GapTensorNode with the given parameters.
    pub fn new(prime_val: u32, multiplicity: u32, spectral_weight: f32) -> Self {
        Self {
            prime_val,
            multiplicity,
            spectral_weight,
        }
    }

    /// Axis index: used for canonical indexing within tensors.
    /// Returns the position of this prime in CANDIDATE_PRIMES, or None if Nil.
    pub fn axis_index(&self) -> Option<usize> {
        CANDIDATE_PRIMES.iter().position(|&p| p == self.prime_val)
    }

    /// Get the prime value, or None if Nil.
    pub fn prime_opt(&self) -> Option<u32> {
        if self.is_nil() {
            None
        } else {
            Some(self.prime_val)
        }
    }
}

impl Eq for GapTensorNode {}

impl Hash for GapTensorNode {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.prime_val.hash(state);
        self.multiplicity.hash(state);
        self.spectral_weight.to_bits().hash(state);
    }
}

impl PartialOrd for GapTensorNode {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for GapTensorNode {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.prime_val
            .cmp(&other.prime_val)
            .then(self.multiplicity.cmp(&other.multiplicity))
            .then(
                self.spectral_weight
                    .partial_cmp(&other.spectral_weight)
                    .unwrap_or(std::cmp::Ordering::Equal),
            )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gap_tensor_node_nil() {
        let node = GapTensorNode::NIL;
        assert!(node.is_nil());
        assert!(!node.is_prime());
        assert_eq!(node.resonance(), 0.0);
        assert_eq!(node.prime_opt(), None);
    }

    #[test]
    fn test_gap_tensor_node_resonance() {
        let node = GapTensorNode {
            prime_val: 2,
            multiplicity: 3,
            spectral_weight: 2.0,
        };
        assert!(!node.is_nil());
        assert!(node.is_prime());
        assert_eq!(node.resonance(), 6.0);
        assert_eq!(node.prime_opt(), Some(2));
    }

    #[test]
    fn test_axis_index() {
        let node = GapTensorNode {
            prime_val: 3,
            multiplicity: 1,
            spectral_weight: 1.5,
        };
        assert_eq!(node.axis_index(), Some(1));
    }

    #[test]
    fn test_ordering() {
        let a = GapTensorNode::new(2, 1, 1.0);
        let b = GapTensorNode::new(3, 1, 1.0);
        assert!(a < b);
    }
}
