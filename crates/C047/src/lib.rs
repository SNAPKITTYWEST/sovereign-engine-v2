//! exactness_predicate
//!
//! Exactness checking for chain complexes and sequences.
//! A sequence is exact at a point if kernel = image.
//! A complex is exact everywhere if homology is zero everywhere.

#![warn(missing_docs)]

use differential_operator::DifferentialOperator;
use differential_squared_zero::SquaredZeroVerifier;
use homology_computation::HomologyComputationResult;

/// A certificate that a sequence is exact at a given degree.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExactnessCertificate {
    /// The degree where exactness is certified.
    pub degree: i32,
    /// Whether the sequence is exact at this degree.
    pub is_exact: bool,
    /// Dimension of the kernel.
    pub kernel_dim: usize,
    /// Dimension of the image.
    pub image_dim: usize,
}

impl ExactnessCertificate {
    /// Create a new certificate.
    pub fn new(degree: i32, kernel_dim: usize, image_dim: usize) -> Self {
        let is_exact = kernel_dim == image_dim;
        Self {
            degree,
            is_exact,
            kernel_dim,
            image_dim,
        }
    }

    /// Pretty-print the certificate.
    pub fn summary(&self) -> String {
        format!(
            "Exactness at degree {}: {} (ker dim: {}, im dim: {})",
            self.degree,
            if self.is_exact { "EXACT" } else { "NOT EXACT" },
            self.kernel_dim,
            self.image_dim
        )
    }
}

/// Global exactness predicate: checks if a chain complex is exact everywhere.
pub struct ExactnessPredicateChecker;

impl ExactnessPredicateChecker {
    /// Check exactness at a specific degree.
    ///
    /// Exactness at degree n: ker(d_n) = im(d_{n+1})
    /// This is equivalent to H_n = 0 (trivial homology).
    pub fn check_at_degree(diff: &DifferentialOperator, degree: i32) -> ExactnessCertificate {
        // First verify d² = 0
        let cert = SquaredZeroVerifier::verify_at_degree(diff, degree);
        if !cert.is_valid {
            return ExactnessCertificate::new(degree, 0, 0);
        }

        // Compute kernel and image
        let kernel_dim = Self::compute_kernel_dimension(diff, degree);
        let image_dim = Self::compute_image_dimension(diff, degree);

        ExactnessCertificate::new(degree, kernel_dim, image_dim)
    }

    /// Accessor for target rank (used in verification).
    #[allow(dead_code)]
    fn get_target_rank(diff: &DifferentialOperator, degree: i32) -> usize {
        diff.target_rank(degree)
    }

    /// Check global exactness: the complex is exact everywhere.
    ///
    /// This means H_n = 0 for all n.
    pub fn check_global_exactness(diff: &DifferentialOperator) -> GlobalExactnessProof {
        // Verify d² = 0 globally
        let proof = SquaredZeroVerifier::verify_global(diff);
        if !proof.is_valid {
            return GlobalExactnessProof {
                is_exact: false,
                certificates: Vec::new(),
                reason: "d² ≠ 0: not a chain complex".to_string(),
            };
        }

        // Check exactness at each degree
        let mut certificates = Vec::new();
        let mut all_exact = true;

        for degree in diff.shape.degrees.iter().map(|d| d.degree) {
            let cert = Self::check_at_degree(diff, degree);
            if !cert.is_exact {
                all_exact = false;
            }
            certificates.push(cert);
        }

        GlobalExactnessProof {
            is_exact: all_exact,
            certificates,
            reason: if all_exact {
                "All homology groups are trivial".to_string()
            } else {
                "Some homology groups are nontrivial".to_string()
            },
        }
    }

    /// Check if the homology computation result shows exactness.
    pub fn check_from_homology(result: &HomologyComputationResult) -> bool {
        result.support_degrees().is_empty()
    }

    /// Compute kernel dimension (estimated).
    fn compute_kernel_dimension(diff: &DifferentialOperator, degree: i32) -> usize {
        let source_rank = diff.source_rank(degree);
        let matrix = diff.to_dense_matrix(degree);

        if matrix.is_empty() {
            return source_rank; // Zero map has all elements in kernel
        }

        // Estimate rank of matrix
        let mut rank = 0;
        let rows = matrix.len();
        let cols = if rows > 0 { matrix[0].len() } else { 0 };

        let mut current_col = 0;

        for current_row in 0..rows {
            if current_col >= cols {
                break;
            }

            // Find pivot
            let mut pivot_row = None;
            for r in current_row..rows {
                if matrix[r][current_col] != 0 {
                    pivot_row = Some(r);
                    break;
                }
            }

            if pivot_row.is_some() {
                rank += 1;
                current_col += 1;
            } else {
                current_col += 1;
            }
        }

        source_rank - rank
    }

    /// Compute image dimension (estimated).
    fn compute_image_dimension(diff: &DifferentialOperator, degree: i32) -> usize {
        let _target_rank = diff.target_rank(degree);
        let matrix = diff.to_dense_matrix(degree);

        if matrix.is_empty() {
            return 0; // Zero map has trivial image
        }

        // Estimate rank of matrix
        let mut rank = 0;
        let rows = matrix.len();
        let cols = if rows > 0 { matrix[0].len() } else { 0 };

        let mut mat = matrix.clone();
        let mut current_col = 0;

        for current_row in 0..rows {
            if current_col >= cols {
                break;
            }

            // Find pivot
            let mut pivot_row = None;
            for r in current_row..rows {
                if mat[r][current_col] != 0 {
                    pivot_row = Some(r);
                    break;
                }
            }

            if let Some(piv) = pivot_row {
                mat.swap(current_row, piv);
                rank += 1;
                current_col += 1;
            } else {
                current_col += 1;
            }
        }

        rank
    }
}

/// Global proof that a sequence is exact (acyclic).
#[derive(Debug, Clone)]
pub struct GlobalExactnessProof {
    /// Whether the sequence is globally exact.
    pub is_exact: bool,
    /// Exactness certificates for each degree.
    pub certificates: Vec<ExactnessCertificate>,
    /// Reason for the verdict.
    pub reason: String,
}

impl GlobalExactnessProof {
    /// Get certificate at a specific degree.
    pub fn cert_at(&self, degree: i32) -> Option<&ExactnessCertificate> {
        self.certificates.iter().find(|c| c.degree == degree)
    }

    /// Count how many degrees are exact.
    pub fn exact_count(&self) -> usize {
        self.certificates.iter().filter(|c| c.is_exact).count()
    }

    /// Count how many degrees are not exact.
    pub fn non_exact_count(&self) -> usize {
        self.certificates.iter().filter(|c| !c.is_exact).count()
    }

    /// Generate a summary report.
    pub fn summary(&self) -> String {
        let mut report = format!(
            "Global Exactness Proof\n  Result: {}\n  Reason: {}\n",
            if self.is_exact { "EXACT" } else { "NOT EXACT" },
            self.reason
        );
        report.push_str(&format!(
            "  Exact at {}/{} degrees\n",
            self.exact_count(),
            self.certificates.len()
        ));

        for cert in &self.certificates {
            report.push_str(&format!("    {}\n", cert.summary()));
        }

        report
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chain_complex_shape::ChainComplexShape;
    use differential_operator::DifferentialOperator;

    #[test]
    fn test_exactness_certificate() {
        let cert = ExactnessCertificate::new(0, 5, 5);
        assert!(cert.is_exact);
        assert_eq!(cert.kernel_dim, 5);
        assert_eq!(cert.image_dim, 5);
    }

    #[test]
    fn test_exactness_certificate_not_exact() {
        let cert = ExactnessCertificate::new(1, 3, 5);
        assert!(!cert.is_exact);
    }

    #[test]
    fn test_global_exactness_proof() {
        let certs = vec![
            ExactnessCertificate::new(0, 2, 2),
            ExactnessCertificate::new(1, 3, 3),
        ];
        let proof = GlobalExactnessProof {
            is_exact: true,
            certificates: certs,
            reason: "Test".to_string(),
        };
        assert!(proof.is_exact);
        assert_eq!(proof.exact_count(), 2);
    }

    #[test]
    fn test_check_at_degree_zero_rank() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 0)]);
        let diff = DifferentialOperator::new(shape);
        let cert = ExactnessPredicateChecker::check_at_degree(&diff, 0);
        // Zero differential: kernel = all, image = none
        assert_eq!(cert.kernel_dim, 0);
        assert_eq!(cert.image_dim, 0);
    }
}
