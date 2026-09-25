//! tor_functor_definition
//!
//! Definition and properties of the Tor functor (derived tensor product).
//! Core homological algebra: Tor^i_R(M, N) for modules M, N over ring R.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use chain_complex_shape::integer_matrix;
pub use homology_computation::{HomologyComputer, HomologyGroup};
pub use projective_resolution::{
    ProjectiveModule, ProjectiveModuleHomomorphism, ProjectiveResolution, ResolutionHomology,
};

/// Tor functor computation index
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct TorIndex {
    /// Degree i in Tor_i
    pub degree: usize,
}

impl TorIndex {
    /// Create a Tor index for degree i
    pub fn new(degree: usize) -> Self {
        Self { degree }
    }

    /// Tor_0 is the base case (tensor product)
    pub fn is_zero(&self) -> bool {
        self.degree == 0
    }

    /// Tor_i for i > 0 measures higher-order torsion
    pub fn is_higher(&self) -> bool {
        self.degree > 0
    }
}

/// A Tor group: Tor_i(M, N) ≅ Z^rank ⊕ ⊕ (Z/order)^multiplicity.
///
/// Generators are ordered torsion first (by ascending order), then free.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TorGroup {
    /// Index i (which Tor we're computing)
    pub index: TorIndex,
    /// Rank of the module (dimension)
    pub rank: usize,
    /// Torsion elements indexed by their order
    pub torsion: BTreeMap<u64, usize>,
}

impl TorGroup {
    /// Create a new Tor group for index i with given rank
    pub fn new(index: TorIndex, rank: usize) -> Self {
        Self {
            index,
            rank,
            torsion: BTreeMap::new(),
        }
    }

    /// Build from free rank and a list of torsion orders (orders ≤ 1 are
    /// trivial and skipped).
    pub fn from_invariants(index: TorIndex, rank: usize, torsion: &[u64]) -> Self {
        let mut group = Self::new(index, rank);
        for &order in torsion {
            group.add_torsion(order, 1);
        }
        group
    }

    /// Build from a homology group.
    pub fn from_homology(index: TorIndex, homology: &HomologyGroup) -> Self {
        Self::from_invariants(index, homology.rank, &homology.torsion)
    }

    /// Add `multiplicity` torsion summands of order `order`. Orders ≤ 1 are
    /// trivial and ignored.
    pub fn add_torsion(&mut self, order: u64, multiplicity: usize) {
        if order > 1 && multiplicity > 0 {
            *self.torsion.entry(order).or_insert(0) += multiplicity;
        }
    }

    /// Order of each torsion generator, in generator order.
    pub fn torsion_orders(&self) -> Vec<u64> {
        self.torsion
            .iter()
            .flat_map(|(&order, &count)| std::iter::repeat(order).take(count))
            .collect()
    }

    /// Is this Tor group trivial?
    pub fn is_trivial(&self) -> bool {
        self.rank == 0 && self.torsion.is_empty()
    }

    /// Total number of generators (free + torsion)
    pub fn num_generators(&self) -> usize {
        self.rank + self.torsion.values().sum::<usize>()
    }

    /// Exponent of torsion (LCM of all torsion orders), saturating at
    /// `u64::MAX`.
    pub fn torsion_exponent(&self) -> u64 {
        fn gcd(a: u64, b: u64) -> u64 {
            if b == 0 { a } else { gcd(b, a % b) }
        }
        fn lcm(a: u64, b: u64) -> u64 {
            (a / gcd(a, b)).saturating_mul(b)
        }

        self.torsion
            .keys()
            .copied()
            .fold(1u64, |acc, order| lcm(acc, order))
    }
}

/// Tor computation result for a pair of modules
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TorComputation {
    /// Tor groups indexed by degree
    pub groups: BTreeMap<usize, TorGroup>,
}

impl TorComputation {
    /// Create an empty Tor computation
    pub fn new() -> Self {
        Self {
            groups: BTreeMap::new(),
        }
    }

    /// Insert a Tor group at a given degree
    pub fn insert_tor(&mut self, degree: usize, group: TorGroup) {
        self.groups.insert(degree, group);
    }

    /// Get Tor_i (returns None if not computed)
    pub fn tor(&self, degree: usize) -> Option<&TorGroup> {
        self.groups.get(&degree)
    }

    /// Get mutable Tor_i
    pub fn tor_mut(&mut self, degree: usize) -> Option<&mut TorGroup> {
        self.groups.get_mut(&degree)
    }

    /// Highest degree computed
    pub fn max_degree(&self) -> Option<usize> {
        self.groups.keys().max().copied()
    }

    /// Check if all Tor_i for i > 0 are trivial (exact sequence)
    pub fn is_split_exact(&self) -> bool {
        self.groups
            .iter()
            .filter(|&(i, _)| *i > 0)
            .all(|(_, g)| g.is_trivial())
    }
}

impl Default for TorComputation {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tor_index() {
        let idx0 = TorIndex::new(0);
        assert!(idx0.is_zero());
        assert!(!idx0.is_higher());

        let idx1 = TorIndex::new(1);
        assert!(!idx1.is_zero());
        assert!(idx1.is_higher());
    }

    #[test]
    fn test_tor_group_creation() {
        let mut group = TorGroup::new(TorIndex::new(0), 3);
        assert_eq!(group.rank, 3);
        assert_eq!(group.num_generators(), 3);
        assert!(group.is_trivial() == false);

        group.add_torsion(2, 1);
        assert_eq!(group.num_generators(), 4);
    }

    #[test]
    fn test_tor_group_torsion_exponent() {
        let mut group = TorGroup::new(TorIndex::new(1), 0);
        group.add_torsion(2, 1);
        group.add_torsion(3, 1);
        assert_eq!(group.torsion_exponent(), 6);

        let mut group2 = TorGroup::new(TorIndex::new(1), 0);
        group2.add_torsion(4, 1);
        group2.add_torsion(6, 1);
        assert_eq!(group2.torsion_exponent(), 12);
    }

    #[test]
    fn invariants_and_generator_order() {
        let g = TorGroup::from_invariants(TorIndex::new(1), 2, &[1, 6, 2, 6]);
        assert_eq!(g.rank, 2);
        assert_eq!(g.torsion_orders(), vec![2, 6, 6]);
        assert_eq!(g.num_generators(), 5);
        let h = HomologyGroup { degree: 0, rank: 0, torsion: vec![3] };
        assert_eq!(TorGroup::from_homology(TorIndex::new(0), &h).torsion_orders(), vec![3]);
        let mut trivial = TorGroup::new(TorIndex::new(0), 0);
        trivial.add_torsion(1, 3);
        assert!(trivial.is_trivial());
    }

    #[test]
    fn test_tor_computation() {
        let mut comp = TorComputation::new();
        let group0 = TorGroup::new(TorIndex::new(0), 5);
        comp.insert_tor(0, group0);

        assert!(comp.tor(0).is_some());
        assert!(comp.tor(1).is_none());
        assert_eq!(comp.max_degree(), Some(0));
    }

    #[test]
    fn test_tor_split_exact() {
        let mut comp = TorComputation::new();
        let group0 = TorGroup::new(TorIndex::new(0), 3);
        comp.insert_tor(0, group0);

        // Only Tor_0 is non-trivial, so it's split exact
        assert!(comp.is_split_exact());
    }
}
