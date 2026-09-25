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

    /// Highest degree with a non-zero Betti number. (Over Z there is no
    /// grading, so this is the top non-vanishing degree of the free part, not
    /// Castelnuovo–Mumford regularity.)
    pub fn regularity(&self) -> Option<usize> {
        self.ranks
            .iter()
            .filter(|(_, &rank)| rank > 0)
            .map(|(&degree, _)| degree)
            .max()
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

/// Torsion complexity: sum of the torsion exponents of every Tor group that
/// has torsion (saturating).
pub fn torsion_complexity(tor: &TorComputation) -> u64 {
    tor.groups
        .values()
        .filter(|g| !g.torsion.is_empty())
        .map(|g| g.torsion_exponent())
        .fold(0u64, u64::saturating_add)
}

/// True iff every computed Tor group is torsion-free.
pub fn is_free_resolution(tor: &TorComputation) -> bool {
    tor.groups
        .values()
        .all(|g| g.torsion.is_empty())
}

/// Tor dimension of the pair: the highest degree with a non-trivial Tor
/// group (`None` if every group is trivial). Over Z this is at most 1.
pub fn global_dimension(tor: &TorComputation) -> Option<usize> {
    tor.groups
        .iter()
        .filter(|(_, g)| !g.is_trivial())
        .map(|(&degree, _)| degree)
        .max()
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
    fn invariants_of_a_real_tor_computation() {
        let tor = derived_homology::tor_of(
            &tor_functor_definition::ProjectiveResolution::cyclic_resolution(4),
            &tor_functor_definition::ProjectiveResolution::cyclic_resolution(6),
        )
        .unwrap();
        let betti = compute_betti_numbers(&tor);
        assert_eq!(betti.total_rank(), 0);
        assert_eq!(betti.regularity(), None);
        assert_eq!(torsion_complexity(&tor), 4);
        assert!(!is_free_resolution(&tor));
        assert_eq!(global_dimension(&tor), Some(1));
    }

    #[test]
    fn test_global_dimension() {
        let mut tor = TorComputation::new();
        tor.insert_tor(0, TorGroup::new(tor_functor_definition::TorIndex::new(0), 1));
        tor.insert_tor(2, TorGroup::new(tor_functor_definition::TorIndex::new(2), 1));

        assert_eq!(global_dimension(&tor), Some(2));
    }
}
