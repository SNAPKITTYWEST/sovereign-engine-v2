//! exactness_predicate
//!
//! Exactness checking for chain complexes and sequences.
//! A sequence is exact at a point if kernel = image.
//! A complex is exact everywhere if homology is zero everywhere.

#![warn(missing_docs)]

use chain_complex_shape::integer_matrix::smith_form;
use differential_operator::DifferentialOperator;
use differential_squared_zero::SquaredZeroVerifier;
use homology_computation::HomologyComputationResult;

/// A certificate that a sequence is exact at a given degree.
///
/// Over Z, exactness at degree n (`ker d_n = im d_{n+1}`) needs equal ranks
/// *and* a torsion-free quotient: for `0 → Z --·2--> Z → 0`, at degree 0
/// both `ker d_0` and `im d_1` have rank 1, yet `ker d_0 / im d_1 = Z/2`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExactnessCertificate {
    /// The degree where exactness is certified.
    pub degree: i32,
    /// Whether the sequence is exact at this degree.
    pub is_exact: bool,
    /// Rank of `ker d_n`.
    pub kernel_dim: usize,
    /// Rank of `im d_{n+1}`.
    pub image_dim: usize,
    /// Whether `ker d_n / im d_{n+1}` is torsion-free.
    pub torsion_free: bool,
}

impl ExactnessCertificate {
    /// Certificate from ranks, assuming a torsion-free quotient.
    pub fn new(degree: i32, kernel_dim: usize, image_dim: usize) -> Self {
        Self::from_ranks(degree, kernel_dim, image_dim, true)
    }

    /// Certificate from ranks and the torsion status of the quotient.
    pub fn from_ranks(degree: i32, kernel_dim: usize, image_dim: usize, torsion_free: bool) -> Self {
        Self {
            degree,
            is_exact: kernel_dim == image_dim && torsion_free,
            kernel_dim,
            image_dim,
            torsion_free,
        }
    }

    /// Certificate for a degree where the check could not be carried out
    /// (d² ≠ 0 or arithmetic overflow): never exact.
    pub fn failed(degree: i32) -> Self {
        Self {
            degree,
            is_exact: false,
            kernel_dim: 0,
            image_dim: 0,
            torsion_free: false,
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
        // im d_{n+1} ⊆ ker d_n requires d_n ∘ d_{n+1} = 0.
        if !SquaredZeroVerifier::verify_at_degree(diff, degree + 1).is_valid {
            return ExactnessCertificate::failed(degree);
        }
        let outgoing = smith_form(&diff.to_dense_matrix(degree), diff.source_rank(degree));
        let incoming = smith_form(&diff.to_dense_matrix(degree + 1), diff.source_rank(degree + 1));
        let (Ok(outgoing), Ok(incoming)) = (outgoing, incoming) else {
            return ExactnessCertificate::failed(degree);
        };
        let kernel_dim = diff.source_rank(degree).saturating_sub(outgoing.rank());
        ExactnessCertificate::from_ranks(degree, kernel_dim, incoming.rank(), incoming.is_torsion_free())
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

    fn complex(ranks: Vec<(i32, usize)>, maps: &[(i32, usize, Vec<(usize, i64)>)]) -> DifferentialOperator {
        let mut diff = DifferentialOperator::new(ChainComplexShape::from_ranks(ranks));
        for (degree, gen, image) in maps {
            diff.set_generator_image(*degree, *gen, degree - 1, image.clone());
        }
        diff
    }

    #[test]
    fn identity_complex_is_exact() {
        let diff = complex(vec![(0, 2), (1, 2)], &[(1, 0, vec![(0, 1)]), (1, 1, vec![(1, 1)])]);
        let proof = ExactnessPredicateChecker::check_global_exactness(&diff);
        assert!(proof.is_exact, "{}", proof.summary());
    }

    #[test]
    fn zero_differential_is_not_exact() {
        let diff = complex(vec![(0, 1), (1, 1)], &[(1, 0, vec![])]);
        let proof = ExactnessPredicateChecker::check_global_exactness(&diff);
        assert!(!proof.is_exact);
        let c0 = proof.cert_at(0).unwrap();
        assert_eq!((c0.kernel_dim, c0.image_dim), (1, 0));
    }

    #[test]
    fn torsion_breaks_exactness() {
        let diff = complex(vec![(0, 1), (1, 1)], &[(1, 0, vec![(0, 2)])]);
        let c0 = ExactnessPredicateChecker::check_at_degree(&diff, 0);
        assert_eq!((c0.kernel_dim, c0.image_dim), (1, 1));
        assert!(!c0.torsion_free);
        assert!(!c0.is_exact);
        assert!(ExactnessPredicateChecker::check_at_degree(&diff, 1).is_exact);
    }

    #[test]
    fn non_complex_is_never_exact() {
        let diff = complex(
            vec![(0, 1), (1, 1), (2, 1)],
            &[(1, 0, vec![(0, 1)]), (2, 0, vec![(0, 1)])],
        );
        let c1 = ExactnessPredicateChecker::check_at_degree(&diff, 1);
        assert!(!c1.is_exact);
        assert!(!ExactnessPredicateChecker::check_global_exactness(&diff).is_exact);
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
