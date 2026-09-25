//! differential_squared_zero
//!
//! Verification that d² = 0 in a chain complex. This is the defining property
//! of a chain complex: composing the differential with itself yields zero.

#![warn(missing_docs)]

use differential_operator::DifferentialOperator;

/// Proof certificate that d² = 0 at a specific degree.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SquaredZeroCertificate {
    /// The degree where d² = 0 is verified.
    pub degree: i32,
    /// Whether the verification passed.
    pub is_valid: bool,
    /// Number of generators checked.
    pub generators_checked: usize,
    /// Number of test cases passed.
    pub test_cases_passed: usize,
}

impl SquaredZeroCertificate {
    /// Create a new certificate.
    pub fn new(degree: i32) -> Self {
        Self {
            degree,
            is_valid: false,
            generators_checked: 0,
            test_cases_passed: 0,
        }
    }

    /// Mark this certificate as valid with statistics.
    pub fn mark_valid(mut self, generators_checked: usize, test_cases_passed: usize) -> Self {
        self.is_valid = true;
        self.generators_checked = generators_checked;
        self.test_cases_passed = test_cases_passed;
        self
    }
}

/// Verifies that d² = 0 for a differential operator.
/// For each generator g in C_n, checks that d(d(g)) = 0 in C_{n-2}.
pub struct SquaredZeroVerifier;

impl SquaredZeroVerifier {
    /// Verify d² = 0 at a specific degree.
    ///
    /// Checks that for all generators g at degree n:
    /// d(d(g)) = 0 in C_{n-2}
    ///
    /// Returns a certificate with the result.
    pub fn verify_at_degree(diff: &DifferentialOperator, degree: i32) -> SquaredZeroCertificate {
        let mut cert = SquaredZeroCertificate::new(degree);
        // Every generator is checked (no early exit), so test_cases_passed
        // counts exactly the generators with d(d(g)) = 0.
        for gen_idx in 0..diff.source_rank(degree) {
            cert.generators_checked += 1;
            let first_image = diff.apply_to_generator(degree, gen_idx);
            if diff.apply_to_element(&first_image).is_zero() {
                cert.test_cases_passed += 1;
            }
        }
        cert.is_valid = cert.test_cases_passed == cert.generators_checked;
        cert
    }

    /// Verify d² = 0 for all degrees in the chain complex.
    ///
    /// Returns a list of certificates, one per degree.
    pub fn verify_all(diff: &DifferentialOperator) -> Vec<SquaredZeroCertificate> {
        let mut certificates = Vec::new();

        for degree in diff.support_degrees() {
            let cert = Self::verify_at_degree(diff, degree);
            certificates.push(cert);
        }

        // Also check degrees where differential might apply but isn't explicitly set
        // (rank 0 case)
        for degree in diff.shape.degrees.iter().map(|d| d.degree) {
            if diff.matrix_at(degree).is_none() && degree > 0 {
                let mut cert = SquaredZeroCertificate::new(degree);
                // Zero differential vacuously satisfies d² = 0
                cert.is_valid = true;
                cert.generators_checked = 0;
                cert.test_cases_passed = 0;
                if !certificates.iter().any(|c| c.degree == degree) {
                    certificates.push(cert);
                }
            }
        }

        certificates
    }

    /// Global verification: check d² = 0 everywhere and return unified status.
    pub fn verify_global(diff: &DifferentialOperator) -> GlobalSquaredZeroProof {
        let certificates = Self::verify_all(diff);
        let all_valid = certificates.iter().all(|c| c.is_valid);
        let total_generators_checked: usize =
            certificates.iter().map(|c| c.generators_checked).sum();
        let total_test_cases_passed: usize =
            certificates.iter().map(|c| c.test_cases_passed).sum();

        GlobalSquaredZeroProof {
            is_valid: all_valid,
            certificates,
            total_generators_checked,
            total_test_cases_passed,
        }
    }
}

/// Global proof that d² = 0 everywhere in a chain complex.
#[derive(Debug, Clone)]
pub struct GlobalSquaredZeroProof {
    /// Whether d² = 0 holds everywhere.
    pub is_valid: bool,
    /// Certificates for each degree.
    pub certificates: Vec<SquaredZeroCertificate>,
    /// Total generators checked.
    pub total_generators_checked: usize,
    /// Total test cases passed.
    pub total_test_cases_passed: usize,
}

impl GlobalSquaredZeroProof {
    /// Get the certificate at a specific degree.
    pub fn cert_at(&self, degree: i32) -> Option<&SquaredZeroCertificate> {
        self.certificates.iter().find(|c| c.degree == degree)
    }

    /// Pretty-print the proof.
    pub fn summary(&self) -> String {
        format!(
            "GlobalSquaredZeroProof {{\n  is_valid: {},\n  degrees_checked: {},\n  total_generators: {},\n  total_tests_passed: {}\n}}",
            self.is_valid, self.certificates.len(), self.total_generators_checked, self.total_test_cases_passed
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use differential_operator::DifferentialOperator;
    use chain_complex_shape::ChainComplexShape;

    #[test]
    fn test_squared_zero_certificate() {
        let mut cert = SquaredZeroCertificate::new(1);
        assert!(!cert.is_valid);
        cert = cert.mark_valid(5, 5);
        assert!(cert.is_valid);
        assert_eq!(cert.generators_checked, 5);
    }

    #[test]
    fn test_verify_at_degree_zero_rank() {
        let shape = ChainComplexShape::from_ranks(vec![(1, 0)]);
        let diff = DifferentialOperator::new(shape);
        let cert = SquaredZeroVerifier::verify_at_degree(&diff, 1);
        // Zero differential satisfies d² = 0 vacuously
        assert!(cert.is_valid || cert.generators_checked == 0);
    }

    #[test]
    fn test_verify_at_degree_trivial() {
        // Chain C_0 = Z, C_1 = Z with d: Z -> Z sending 1 to 0
        let shape = ChainComplexShape::from_ranks(vec![(0, 1), (1, 1)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![]); // d(gen_0) = 0

        let cert = SquaredZeroVerifier::verify_at_degree(&diff, 1);
        assert!(cert.is_valid);
        assert_eq!(cert.generators_checked, 1);
    }

    #[test]
    fn test_verify_at_degree_nontrivial() {
        // C_0 = Z^2, C_1 = Z^2, C_2 = Z^2 with d nontrivial
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 2), (2, 2)]);
        let mut diff = DifferentialOperator::new(shape);

        // d: C_2 -> C_1 sending gen_0 to gen_0, gen_1 to gen_1
        diff.set_generator_image(2, 0, 1, vec![(0, 1)]);
        diff.set_generator_image(2, 1, 1, vec![(1, 1)]);

        // d: C_1 -> C_0 sending gen_0 to 0, gen_1 to 0
        diff.set_generator_image(1, 0, 0, vec![]);
        diff.set_generator_image(1, 1, 0, vec![]);

        // Now d² = 0 because d(d(x)) = d(0) = 0 for all x
        let cert = SquaredZeroVerifier::verify_at_degree(&diff, 2);
        assert!(cert.is_valid);
    }

    #[test]
    fn failures_are_counted_not_short_circuited() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 1), (1, 1), (2, 3)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![(0, 1)]);
        diff.set_generator_image(2, 0, 1, vec![(0, 1)]);
        diff.set_generator_image(2, 1, 1, vec![]);
        diff.set_generator_image(2, 2, 1, vec![(0, 2)]);
        let cert = SquaredZeroVerifier::verify_at_degree(&diff, 2);
        assert!(!cert.is_valid);
        assert_eq!((cert.generators_checked, cert.test_cases_passed), (3, 1));
    }

    #[test]
    fn test_verify_all() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 1), (1, 1)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![]);

        let proof = SquaredZeroVerifier::verify_global(&diff);
        assert!(proof.is_valid);
    }
}
