//! tor_chain_complex_interface
//!
//! Interface between Tor computation and chain complex objects.

#![warn(missing_docs)]

pub use projective_resolution::ProjectiveResolution;
pub use tor_functor_definition::TorComputation;
pub use derived_homology::compute_tor_from_resolution;
use derived_homology::tor_of;
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
    /// `Tor_*(M, Z)` for the module `M` resolved by `resolution`
    /// (`Tor_0 = M`, higher groups vanish).
    pub fn from_resolution(resolution: ProjectiveResolution) -> Result<Self, String> {
        Self::from_resolutions(resolution, &ProjectiveResolution::free_of_rank_one())
    }

    /// `Tor_*(M, N)` for `M` resolved by `resolution` and `N` resolved by
    /// `coefficients`.
    pub fn from_resolutions(
        resolution: ProjectiveResolution,
        coefficients: &ProjectiveResolution,
    ) -> Result<Self, String> {
        let tor = tor_of(&resolution, coefficients)?;
        let betti = compute_betti_numbers(&tor);
        Ok(Self {
            resolution,
            tor,
            betti,
        })
    }

    /// Update Tor computation
    pub fn update_tor(&mut self, tor: TorComputation) {
        self.betti = compute_betti_numbers(&tor);
        self.tor = tor;
    }

    /// Summary: number of resolution modules, total Betti rank, and the
    /// highest degree with free rank.
    pub fn as_complex_data(&self) -> ChainComplexInterface {
        ChainComplexInterface {
            num_degrees: self.resolution.len(),
            total_rank: self.betti.total_rank(),
            regularity: self.betti.regularity(),
        }
    }
}

/// Summary of a Tor computation attached to a resolution.
#[derive(Clone, Debug, PartialEq, Eq)]
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
    fn data_from_resolutions_computes_tor() {
        let z = ProjectiveResolution::cyclic_resolution(0);
        let data = TorChainComplexData::from_resolution(z).unwrap();
        assert_eq!(data.betti.beta(0), 1);
        assert!(data.as_complex_data().is_acyclic());

        let data = TorChainComplexData::from_resolutions(
            ProjectiveResolution::cyclic_resolution(4),
            &ProjectiveResolution::cyclic_resolution(6),
        )
        .unwrap();
        assert_eq!(data.tor.tor(1).unwrap().torsion_orders(), vec![2]);
        assert_eq!(data.as_complex_data().regularity, None);

        let mut not_exact = ProjectiveResolution::new();
        let p = tor_functor_definition::ProjectiveModule::new(1, 0);
        let p1 = tor_functor_definition::ProjectiveModule::new(1, 1);
        not_exact.add_module(p.clone());
        not_exact.add_module(p1.clone());
        not_exact.add_differential(tor_functor_definition::ProjectiveModuleHomomorphism::new(p1, p, vec![vec![0]]));
        assert!(TorChainComplexData::from_resolution(not_exact).is_err());
    }

    #[test]
    fn test_tor_to_complex_data() {
        let tor = TorComputation::new();
        let iface = tor_to_complex_data(&tor, 3);
        assert_eq!(iface.num_degrees, 3);
    }
}
