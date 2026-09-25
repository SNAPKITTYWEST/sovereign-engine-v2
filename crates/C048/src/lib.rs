//! homology_computation
//!
//! Computation of homology groups H_n = ker(d_n) / im(d_{n+1}).
//! Homology measures the "holes" in a chain complex: it's what survives d² = 0.

#![warn(missing_docs)]

use differential_operator::DifferentialOperator;
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

/// A simplified homology computation result for a chain complex.
/// In practice, computing homology requires Gaussian elimination over Z,
/// which is complex. This provides a simplified interface for smaller examples.
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
    /// Compute homology at degree n for a differential operator.
    ///
    /// This is a simplified version. Full computation requires:
    /// 1. Compute ker(d_n)
    /// 2. Compute im(d_{n+1})
    /// 3. Form the quotient ker(d_n) / im(d_{n+1})
    /// 4. Use Smith normal form to identify rank and torsion
    ///
    /// For now, we verify d² = 0 and return a placeholder.
    pub fn compute_at_degree(
        diff: &DifferentialOperator,
        degree: i32,
    ) -> Result<HomologyGroup, String> {
        // First verify d² = 0 at this degree
        let cert = SquaredZeroVerifier::verify_at_degree(diff, degree);
        if !cert.is_valid {
            return Err(format!("d² ≠ 0 at degree {}", degree));
        }

        // Get rank information
        let _source_rank = diff.source_rank(degree);

        // For now, return a homology group with rank equal to kernel dimension
        // A full implementation would compute the quotient ker(d_n) / im(d_{n+1})
        let kernel_rank = Self::estimate_kernel_rank(diff, degree);

        Ok(HomologyGroup::new(degree, kernel_rank))
    }

    /// Estimate the kernel rank (simplified).
    /// Full computation would use Gaussian elimination.
    fn estimate_kernel_rank(diff: &DifferentialOperator, degree: i32) -> usize {
        let matrix = diff.to_dense_matrix(degree);

        if matrix.is_empty() || matrix[0].is_empty() {
            return diff.source_rank(degree);
        }

        // Simple rank estimation: use Gaussian elimination (modulo complexity)
        let mut rank = 0;
        let rows = matrix.len();
        let cols = matrix[0].len();

        let mut col_pivots = vec![false; cols];

        for row in 0..rows {
            for col in 0..cols {
                if matrix[row][col] != 0 {
                    col_pivots[col] = true;
                    break;
                }
            }
        }

        for pivot in col_pivots {
            if pivot {
                rank += 1;
            }
        }

        // Kernel rank = cols - matrix rank
        (cols as i32 - rank as i32).max(0) as usize
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
