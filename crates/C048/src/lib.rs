//! homology_computation
//!
//! Computation of homology groups H_n = ker(d_n) / im(d_{n+1}).
//! Homology measures the "holes" in a chain complex: it's what survives d² = 0.

#![warn(missing_docs)]

pub use chain_complex_shape::integer_matrix;
use chain_complex_shape::integer_matrix::smith_form;
pub use chain_complex_shape::ChainComplexShape;
pub use differential_operator::DifferentialOperator;
use differential_squared_zero::SquaredZeroVerifier;
use std::collections::HashMap;

/// A homology group H_n at degree n.
/// Represented as a torsion-free abelian group: Z^rank plus torsion.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HomologyGroup {
    /// The degree n of this homology group.
    pub degree: i32,
    /// The rank (number of free Z generators).
    pub rank: usize,
    /// Torsion coefficients (ideally empty for free modules).
    pub torsion: Vec<u64>,
}

impl HomologyGroup {
    /// Create a new homology group.
    pub fn new(degree: i32, rank: usize) -> Self {
        Self {
            degree,
            rank,
            torsion: Vec::new(),
        }
    }

    /// Create the trivial (zero) homology group.
    pub fn trivial(degree: i32) -> Self {
        Self {
            degree,
            rank: 0,
            torsion: Vec::new(),
        }
    }

    /// Check if this homology group is trivial.
    pub fn is_trivial(&self) -> bool {
        self.rank == 0 && self.torsion.is_empty()
    }

    /// Add torsion coefficient.
    pub fn add_torsion(&mut self, coeff: u64) {
        if coeff > 1 {
            self.torsion.push(coeff);
        }
    }

    /// Compute Betti number (rank of free part).
    pub fn betti_number(&self) -> usize {
        self.rank
    }

    /// Pretty-print the homology group.
    pub fn to_string(&self) -> String {
        if self.is_trivial() {
            format!("H_{}(C) = 0", self.degree)
        } else if self.torsion.is_empty() {
            format!("H_{}(C) = Z^{}", self.degree, self.rank)
        } else {
            format!(
                "H_{}(C) = Z^{} ⊕ {}",
                self.degree,
                self.rank,
                self.torsion
                    .iter()
                    .map(|t| format!("Z/{}", t))
                    .collect::<Vec<_>>()
                    .join(" ⊕ ")
            )
        }
    }
}

/// Homology groups of a chain complex, one per degree of its shape.
#[derive(Debug, Clone)]
pub struct HomologyComputationResult {
    /// Homology groups H_n for each degree n.
    pub groups: HashMap<i32, HomologyGroup>,
    /// Whether the computation was verified.
    pub verified: bool,
}

impl HomologyComputationResult {
    /// Create a new result.
    pub fn new() -> Self {
        Self {
            groups: HashMap::new(),
            verified: false,
        }
    }

    /// Add a homology group.
    pub fn add_group(&mut self, group: HomologyGroup) {
        self.groups.insert(group.degree, group);
    }

    /// Get the homology group at degree n.
    pub fn group_at(&self, degree: i32) -> Option<&HomologyGroup> {
        self.groups.get(&degree)
    }

    /// Get all degrees with nonzero homology.
    pub fn support_degrees(&self) -> Vec<i32> {
        let mut degrees: Vec<_> = self
            .groups
            .iter()
            .filter(|(_, g)| !g.is_trivial())
            .map(|(d, _)| *d)
            .collect();
        degrees.sort_unstable();
        degrees
    }

    /// Compute the Euler characteristic: sum of (-1)^n * rank(H_n).
    pub fn euler_characteristic(&self) -> i64 {
        let mut chi = 0i64;
        for (degree, group) in &self.groups {
            let sign = if degree % 2 == 0 { 1 } else { -1 };
            chi += sign * (group.rank as i64);
        }
        chi
    }

    /// Mark as verified.
    pub fn mark_verified(&mut self) {
        self.verified = true;
    }

    /// Generate a summary report.
    pub fn summary(&self) -> String {
        let mut report = format!("Homology Computation Result (verified: {})\n", self.verified);
        let degrees = self.support_degrees();
        if degrees.is_empty() {
            report.push_str("  All homology groups are trivial.\n");
        } else {
            for degree in degrees {
                if let Some(group) = self.group_at(degree) {
                    report.push_str(&format!("  {}\n", group.to_string()));
                }
            }
        }
        report.push_str(&format!("  Euler characteristic: {}\n", self.euler_characteristic()));
        report
    }
}

impl Default for HomologyComputationResult {
    fn default() -> Self {
        Self::new()
    }
}

/// Homology computation engine.
pub struct HomologyComputer;

impl HomologyComputer {
    /// Compute `H_n = ker(d_n) / im(d_{n+1})` exactly over Z.
    ///
    /// `ker d_n` is a direct summand of `C_n` (its quotient embeds in the
    /// free module `C_{n-1}`), so `H_n ≅ Z^r ⊕ ⊕ Z/e_j` with
    /// `r = rank C_n − rank d_n − rank d_{n+1}` and `e_j` the invariant
    /// factors of `d_{n+1}` greater than 1 (Smith normal form).
    pub fn compute_at_degree(
        diff: &DifferentialOperator,
        degree: i32,
    ) -> Result<HomologyGroup, String> {
        if !SquaredZeroVerifier::verify_at_degree(diff, degree + 1).is_valid {
            return Err(format!("d² ≠ 0: d_{} ∘ d_{} is non-zero", degree, degree + 1));
        }
        let rank_n = diff.source_rank(degree);
        let outgoing = smith_form(&diff.to_dense_matrix(degree), rank_n).map_err(|e| e.to_string())?;
        let incoming = smith_form(&diff.to_dense_matrix(degree + 1), diff.source_rank(degree + 1))
            .map_err(|e| e.to_string())?;
        let free_rank = rank_n
            .checked_sub(outgoing.rank() + incoming.rank())
            .ok_or_else(|| format!("rank d_{} + rank d_{} exceeds rank C_{}", degree, degree + 1, degree))?;
        let mut group = HomologyGroup::new(degree, free_rank);
        for t in incoming.torsion() {
            group.add_torsion(t);
        }
        Ok(group)
    }

    /// Compute homology for all degrees in the chain complex.
    pub fn compute_all(diff: &DifferentialOperator) -> Result<HomologyComputationResult, String> {
        let mut result = HomologyComputationResult::new();

        // First verify d² = 0 globally
        let proof = SquaredZeroVerifier::verify_global(diff);
        if !proof.is_valid {
            return Err("d² ≠ 0: not a chain complex".to_string());
        }

        // Compute homology at each degree
        for degree in diff.shape.degrees.iter().map(|d| d.degree) {
            match Self::compute_at_degree(diff, degree) {
                Ok(group) => {
                    result.add_group(group);
                }
                Err(e) => {
                    return Err(format!("Error computing H_{}(C): {}", degree, e));
                }
            }
        }

        result.mark_verified();
        Ok(result)
    }

    /// Compute reduced homology (homology of the augmented complex).
    /// This is used in simplicial homology and other contexts.
    pub fn compute_reduced_homology(
        diff: &DifferentialOperator,
        degree: i32,
    ) -> Result<HomologyGroup, String> {
        let mut group = Self::compute_at_degree(diff, degree)?;
        // For degree 0, subtract 1 from rank (due to augmentation)
        if degree == 0 && group.rank > 0 {
            group.rank -= 1;
        }
        Ok(group)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_homology_group_new() {
        let h = HomologyGroup::new(0, 2);
        assert_eq!(h.degree, 0);
        assert_eq!(h.rank, 2);
        assert!(!h.is_trivial());
    }

    #[test]
    fn test_homology_group_trivial() {
        let h = HomologyGroup::trivial(5);
        assert!(h.is_trivial());
    }

    #[test]
    fn test_homology_group_string() {
        let h = HomologyGroup::new(1, 3);
        let s = h.to_string();
        assert!(s.contains("Z^3"));
    }

    #[test]
    fn test_homology_computation_result_new() {
        let result = HomologyComputationResult::new();
        assert!(!result.verified);
        assert!(result.groups.is_empty());
    }

    #[test]
    fn test_homology_computation_result_add_group() {
        let mut result = HomologyComputationResult::new();
        result.add_group(HomologyGroup::new(0, 1));
        result.add_group(HomologyGroup::new(1, 2));
        assert_eq!(result.groups.len(), 2);
    }

    #[test]
    fn test_homology_computation_result_euler() {
        let mut result = HomologyComputationResult::new();
        result.add_group(HomologyGroup::new(0, 2)); // +2
        result.add_group(HomologyGroup::new(1, 1)); // -1
        assert_eq!(result.euler_characteristic(), 1);
    }

    use chain_complex_shape::ChainComplexShape;

    fn complex(ranks: Vec<(i32, usize)>, maps: &[(i32, usize, Vec<(usize, i64)>)]) -> DifferentialOperator {
        let mut diff = DifferentialOperator::new(ChainComplexShape::from_ranks(ranks));
        for (degree, gen, image) in maps {
            diff.set_generator_image(*degree, *gen, degree - 1, image.clone());
        }
        diff
    }

    #[test]
    fn multiplication_by_two_has_z2_homology() {
        let diff = complex(vec![(0, 1), (1, 1)], &[(1, 0, vec![(0, 2)])]);
        let h = HomologyComputer::compute_all(&diff).unwrap();
        let h0 = h.group_at(0).unwrap();
        assert_eq!((h0.rank, h0.torsion.clone()), (0, vec![2]));
        assert!(h.group_at(1).unwrap().is_trivial());
    }

    #[test]
    fn circle_as_triangle_boundary() {
        let diff = complex(
            vec![(0, 3), (1, 3)],
            &[
                (1, 0, vec![(0, -1), (1, 1)]),
                (1, 1, vec![(1, -1), (2, 1)]),
                (1, 2, vec![(2, -1), (0, 1)]),
            ],
        );
        let h = HomologyComputer::compute_all(&diff).unwrap();
        assert_eq!(h.group_at(0).unwrap(), &HomologyGroup::new(0, 1));
        assert_eq!(h.group_at(1).unwrap(), &HomologyGroup::new(1, 1));
        assert_eq!(h.euler_characteristic(), 0);
    }

    #[test]
    fn identity_and_zero_differentials() {
        let identity = complex(vec![(0, 2), (1, 2)], &[(1, 0, vec![(0, 1)]), (1, 1, vec![(1, 1)])]);
        let h = HomologyComputer::compute_all(&identity).unwrap();
        assert!(h.support_degrees().is_empty());

        let zero = complex(vec![(0, 1), (1, 1)], &[(1, 0, vec![])]);
        let h = HomologyComputer::compute_all(&zero).unwrap();
        assert_eq!(h.support_degrees(), vec![0, 1]);
        assert_eq!(h.group_at(1).unwrap().rank, 1);
    }

    #[test]
    fn non_complex_is_rejected() {
        let diff = complex(
            vec![(0, 1), (1, 1), (2, 1)],
            &[(1, 0, vec![(0, 1)]), (2, 0, vec![(0, 1)])],
        );
        assert!(HomologyComputer::compute_at_degree(&diff, 1).is_err());
        assert!(HomologyComputer::compute_all(&diff).is_err());
    }

    #[test]
    fn test_homology_computation_result_support() {
        let mut result = HomologyComputationResult::new();
        result.add_group(HomologyGroup::new(0, 1));
        result.add_group(HomologyGroup::trivial(1));
        result.add_group(HomologyGroup::new(2, 2));
        let support = result.support_degrees();
        assert_eq!(support, vec![0, 2]);
    }
}
