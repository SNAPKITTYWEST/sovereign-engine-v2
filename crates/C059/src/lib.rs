//! tor_chain_complex_interface
//!
//! Interface between Tor computation and chain complex objects.

#![warn(missing_docs)]

pub use projective_resolution::ProjectiveResolution;
pub use tor_functor_definition::TorComputation;
pub use derived_homology::compute_tor_from_resolution;
pub use tor_invariants_computation::{BettiNumbers, compute_betti_numbers};

/// Wrapper for a complete Tor-computed chain complex
#[derive(Clone, Debug)]
pub struct TorChainComplexData {
    /// The original projective resolution
    pub resolution: ProjectiveResolution,
    /// Tor groups computed from the resolution
    pub tor: TorComputation,
    /// Derived Betti numbers
    pub betti: BettiNumbers,
}

impl TorChainComplexData {
    /// Create from a resolution
    pub fn from_resolution(resolution: ProjectiveResolution) -> Self {
        let tor = TorComputation::new();
        let betti = compute_betti_numbers(&tor);

        Self {
            resolution,
            tor,
            betti,
        }
    }

    /// Update Tor computation
    pub fn update_tor(&mut self, tor: TorComputation) {
        self.betti = compute_betti_numbers(&tor);
        self.tor = tor;
    }

    /// Export as chain complex interface (simplified)
    pub fn as_complex_data(&self) -> ChainComplexInterface {
        ChainComplexInterface {
            num_degrees: self.resolution.len(),
            total_rank: self.betti.total_rank(),
            regularity: self.betti.regularity(),
        }
    }
}

/// Simplified chain complex interface for compatibility
#[derive(Clone, Debug)]
pub struct ChainComplexInterface {
    /// Number of chain modules
    pub num_degrees: usize,
    /// Total rank of all modules
    pub total_rank: usize,
    /// Regularity (highest degree with non-zero homology)
    pub regularity: Option<usize>,
}

impl ChainComplexInterface {
    /// Check if complex is bounded
    pub fn is_bounded(&self) -> bool {
        self.num_degrees > 0 && self.regularity.is_some()
    }

    /// Check if complex is acyclic (only Tor_0)
    pub fn is_acyclic(&self) -> bool {
        self.regularity == Some(0)
    }
}

/// Convert Tor computation to standard chain complex data
pub fn tor_to_complex_data(
    tor: &TorComputation,
    resolution_length: usize,
) -> ChainComplexInterface {
    let betti = compute_betti_numbers(tor);
    ChainComplexInterface {
        num_degrees: resolution_length,
        total_rank: betti.total_rank(),
        regularity: betti.regularity(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chain_complex_interface() {
        let iface = ChainComplexInterface {
            num_degrees: 3,
            total_rank: 10,
            regularity: Some(2),
        };
        assert!(iface.is_bounded());
        assert!(!iface.is_acyclic());
    }

    #[test]
    fn test_chain_complex_acyclic() {
        let iface = ChainComplexInterface {
            num_degrees: 1,
            total_rank: 5,
            regularity: Some(0),
        };
        assert!(iface.is_acyclic());
    }

    #[test]
    fn test_tor_to_complex_data() {
        let tor = TorComputation::new();
        let iface = tor_to_complex_data(&tor, 3);
        assert_eq!(iface.num_degrees, 3);
    }
}
