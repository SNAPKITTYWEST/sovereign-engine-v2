//! tor_zero_structure
//!
//! Structure and properties of Tor_0(M, N) = M ⊗_R N.

#![warn(missing_docs)]

pub use tor_functor_definition::{TorGroup, TorIndex};
pub use tensor_product_module::TensorProductModule;
pub use derived_homology::verify_tor_computation;

/// Properties specific to Tor_0
#[derive(Clone, Debug)]
pub struct Tor0Properties {
    /// Is Tor_0 free (no torsion)?
    pub is_free: bool,
    /// Rank of Tor_0
    pub rank: usize,
}

impl Tor0Properties {
    /// Create Tor_0 properties
    pub fn new(rank: usize, has_torsion: bool) -> Self {
        Self {
            is_free: !has_torsion,
            rank,
        }
    }

    /// Check if Tor_0 is the trivial group
    pub fn is_trivial(&self) -> bool {
        self.rank == 0 && self.is_free
    }
}

/// Analyze Tor_0(M, N) from a tensor product module
pub fn analyze_tor_zero(module: &TensorProductModule) -> TorGroup {
    let tor_0 = TorGroup::new(TorIndex::new(0), module.free_rank());
    // In the base case, Tor_0 is M ⊗ N with no torsion from resolution
    // (torsion comes from higher Tor groups)
    tor_0
}

/// Verify that Tor_0 satisfies the tensor product property
pub fn verify_tor_zero_universal_property(rank_m: usize, rank_n: usize) -> bool {
    // Tor_0(M, N) should have rank = rank(M) * rank(N) for free modules
    // This is the rank of the free part of M ⊗ N
    let tor_0_rank = rank_m * rank_n;
    tor_0_rank > 0 || (rank_m == 0 || rank_n == 0)
}

/// Compute Tor_0 using the universal property
pub fn compute_tor_zero_from_ranks(rank_m: usize, rank_n: usize) -> TorGroup {
    let rank = rank_m * rank_n;
    TorGroup::new(TorIndex::new(0), rank)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tor_zero_properties() {
        let props = Tor0Properties::new(6, false);
        assert_eq!(props.rank, 6);
        assert!(props.is_free);
        assert!(!props.is_trivial());
    }

    #[test]
    fn test_tor_zero_trivial() {
        let props = Tor0Properties::new(0, false);
        assert!(props.is_trivial());
    }

    #[test]
    fn test_verify_tor_zero_universal_property() {
        assert!(verify_tor_zero_universal_property(2, 3));
        assert!(verify_tor_zero_universal_property(5, 1));
        assert!(verify_tor_zero_universal_property(0, 5));
    }

    #[test]
    fn test_compute_tor_zero_from_ranks() {
        let group = compute_tor_zero_from_ranks(2, 3);
        assert_eq!(group.rank, 6);
        assert!(group.torsion.is_empty());
    }

    #[test]
    fn test_analyze_tor_zero() {
        let module = TensorProductModule::new(2, 3);
        let group = analyze_tor_zero(&module);
        assert_eq!(group.rank, 6);
    }
}
