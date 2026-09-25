//! tor_invariants_computation
//!
//! Compute invariants from Tor: Betti numbers, torsion complexity, etc.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use tor_functor_definition::{TorGroup, TorComputation};
pub use derived_homology::verify_tor_computation;

/// Betti numbers extracted from Tor computation
#[derive(Clone, Debug)]
pub struct BettiNumbers {
    /// β_i = rank of Tor_i
    pub ranks: BTreeMap<usize, usize>,
}

impl BettiNumbers {
    /// Create empty Betti numbers
    pub fn new() -> Self {
        Self {
            ranks: BTreeMap::new(),
        }
    }

    /// Add a Betti number
    pub fn add(&mut self, degree: usize, rank: usize) {
        self.ranks.insert(degree, rank);
    }

    /// Get Betti number at degree
    pub fn beta(&self, degree: usize) -> usize {
        self.ranks.get(&degree).copied().unwrap_or(0)
    }

    /// Total rank (sum of all Betti numbers)
    pub fn total_rank(&self) -> usize {
        self.ranks.values().sum()
    }

    /// Regularity (highest non-zero degree)
    pub fn regularity(&self) -> Option<usize> {
        self.ranks.keys().max().copied()
    }
}

impl Default for BettiNumbers {
    fn default() -> Self {
        Self::new()
    }
}

/// Compute Betti numbers from Tor computation
pub fn compute_betti_numbers(tor: &TorComputation) -> BettiNumbers {
    let mut betti = BettiNumbers::new();
    for (degree, group) in &tor.groups {
        betti.add(*degree, group.rank);
    }
    betti
}

/// Compute torsion complexity (sum of torsion exponents across all Tor groups)
pub fn torsion_complexity(tor: &TorComputation) -> u64 {
    tor.groups
        .values()
        .map(|g| g.torsion_exponent())
        .product()
}

/// Check if the Tor computation represents a free resolution (all torsion vanishes)
pub fn is_free_resolution(tor: &TorComputation) -> bool {
    tor.groups
        .values()
        .all(|g| g.torsion.is_empty())
}

/// Global dimension estimate from Tor groups
pub fn global_dimension(tor: &TorComputation) -> Option<usize> {
    if tor.groups.is_empty() {
        return None;
    }
    tor.groups.keys().max().copied()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_betti_numbers() {
        let mut betti = BettiNumbers::new();
        betti.add(0, 3);
        betti.add(1, 2);
        betti.add(2, 1);
        assert_eq!(betti.beta(0), 3);
        assert_eq!(betti.beta(1), 2);
        assert_eq!(betti.total_rank(), 6);
        assert_eq!(betti.regularity(), Some(2));
    }

    #[test]
    fn test_compute_betti_numbers() {
        let mut tor = TorComputation::new();
        tor.insert_tor(0, TorGroup::new(tor_functor_definition::TorIndex::new(0), 2));
        tor.insert_tor(1, TorGroup::new(tor_functor_definition::TorIndex::new(1), 1));

        let betti = compute_betti_numbers(&tor);
        assert_eq!(betti.beta(0), 2);
        assert_eq!(betti.beta(1), 1);
    }

    #[test]
    fn test_is_free_resolution() {
        let mut tor = TorComputation::new();
        let group = TorGroup::new(tor_functor_definition::TorIndex::new(0), 3);
        tor.insert_tor(0, group);
        assert!(is_free_resolution(&tor));
    }

    #[test]
    fn test_global_dimension() {
        let mut tor = TorComputation::new();
        tor.insert_tor(0, TorGroup::new(tor_functor_definition::TorIndex::new(0), 1));
        tor.insert_tor(2, TorGroup::new(tor_functor_definition::TorIndex::new(2), 1));

        assert_eq!(global_dimension(&tor), Some(2));
    }
}
