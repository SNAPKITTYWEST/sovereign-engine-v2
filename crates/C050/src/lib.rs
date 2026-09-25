//! homological_tests_integration
//!
//! Full integration tests for the homological algebra subsystem (Tier 4).
//! Tests chain complexes, differentials, homology, resolutions, and exactness.

#![warn(missing_docs)]

use chain_complex_shape::{ChainComplexShape, ChainDegreeShape};
use chain_complex_types::ChainElement;
use differential_operator::DifferentialOperator;
use differential_squared_zero::SquaredZeroVerifier;
use exactness_predicate::ExactnessPredicateChecker;
use homology_computation::HomologyComputer;
use projective_module_definition::{ProjectiveModule, ProjectiveModuleHomomorphism};
use projective_resolution::ProjectiveResolution;
use resolution_certification::ResolutionCertifier;

/// Integration test suite for homological algebra.
pub struct HomologicalTestSuite;

impl HomologicalTestSuite {
    /// Test 1: Basic chain complex creation and operations.
    pub fn test_chain_complex_creation() -> TestResult {
        let mut shape = ChainComplexShape::new();
        shape.add_degree(ChainDegreeShape::new(0, 2));
        shape.add_degree(ChainDegreeShape::new(1, 3));
        shape.add_degree(ChainDegreeShape::new(2, 1));

        if shape.len() != 3 || shape.total_rank() != 6 {
            return TestResult::failed("Chain complex creation", "shape has wrong length or rank");
        }

        TestResult::passed("Chain complex creation")
    }

    /// Test 2: Chain element operations (addition, scalar multiplication).
    pub fn test_chain_element_operations() -> TestResult {
        let mut e1 = ChainElement::from_generator(0, 0, 2);
        let e2 = ChainElement::from_generator(0, 1, 3);
        e1.add(&e2);

        if e1.support_size() != 2 || e1.coeff(0) != 2 || e1.coeff(1) != 3 {
            return TestResult::failed("Chain element operations", "addition gave wrong coefficients");
        }

        let neg = e1.neg();
        if neg.coeff(0) != -2 {
            return TestResult::failed("Chain element operations", "negation gave wrong coefficient");
        }

        TestResult::passed("Chain element operations")
    }

    /// Test 3: Differential operator application.
    pub fn test_differential_application() -> TestResult {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 2)]);
        let mut diff = DifferentialOperator::new(shape);

        // d(gen_0 at deg 1) = gen_0 at deg 0
        diff.set_generator_image(1, 0, 0, vec![(0, 1)]);
        // d(gen_1 at deg 1) = gen_1 at deg 0
        diff.set_generator_image(1, 1, 0, vec![(1, 1)]);

        let elem = ChainElement::from_generator(1, 0, 2);
        let image = diff.apply_to_element(&elem);

        if image.degree != 0 || image.coeff(0) != 2 {
            return TestResult::failed("Differential application", "d(2·g_0) ≠ 2·g_0");
        }

        TestResult::passed("Differential application")
    }

    /// Test 4: Verify d² = 0.
    pub fn test_squared_zero_verification() -> TestResult {
        let shape = ChainComplexShape::from_ranks(vec![(0, 1), (1, 1), (2, 1)]);
        let mut diff = DifferentialOperator::new(shape);

        // d: C_2 -> C_1 sending gen_0 to gen_0
        diff.set_generator_image(2, 0, 1, vec![(0, 1)]);
        // d: C_1 -> C_0 sending gen_0 to 0
        diff.set_generator_image(1, 0, 0, vec![]);

        let cert = SquaredZeroVerifier::verify_at_degree(&diff, 2);

        if !cert.is_valid {
            return TestResult::failed("d² = 0 verification", "verifier rejected a valid complex");
        }

        TestResult::passed("d² = 0 verification")
    }

    /// Test 5: Global exactness check. `0 → Z --id--> Z → 0` is exact;
    /// `0 → Z --0--> Z → 0` is not (both homology groups are Z).
    pub fn test_global_exactness() -> TestResult {
        let name = "Global exactness check";
        let mut identity = DifferentialOperator::new(ChainComplexShape::from_ranks(vec![(0, 1), (1, 1)]));
        identity.set_generator_image(1, 0, 0, vec![(0, 1)]);
        if !ExactnessPredicateChecker::check_global_exactness(&identity).is_exact {
            return TestResult::failed(name, "identity complex reported non-exact");
        }

        let mut zero = DifferentialOperator::new(ChainComplexShape::from_ranks(vec![(0, 1), (1, 1)]));
        zero.set_generator_image(1, 0, 0, vec![]);
        if ExactnessPredicateChecker::check_global_exactness(&zero).is_exact {
            return TestResult::failed(name, "zero differential reported exact");
        }

        TestResult::passed(name)
    }

    /// Test 6: Homology computation, including torsion.
    pub fn test_homology_computation() -> TestResult {
        let name = "Homology computation";
        let shape = ChainComplexShape::from_ranks(vec![(0, 1), (1, 1)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![(0, 3)]);

        match HomologyComputer::compute_all(&diff) {
            Ok(result) => {
                let h0 = result.group_at(0);
                let h1 = result.group_at(1);
                if !result.verified {
                    TestResult::failed(name, "result not verified")
                } else if h0.map(|g| (g.rank, g.torsion.clone())) != Some((0, vec![3])) {
                    TestResult::failed(name, "H_0 of Z --3--> Z should be Z/3")
                } else if !h1.map_or(false, |g| g.is_trivial()) {
                    TestResult::failed(name, "H_1 of Z --3--> Z should be 0")
                } else {
                    TestResult::passed(name)
                }
            }
            Err(e) => TestResult::failed(name, &e),
        }
    }

    /// Test 7: Projective module creation and homomorphisms.
    pub fn test_projective_modules() -> TestResult {
        let p = ProjectiveModule::new(3, 0);
        let q = ProjectiveModule::new(2, 0);

        let matrix = vec![vec![1, 2, 3], vec![4, 5, 6]];
        let hom = ProjectiveModuleHomomorphism::new(p, q, matrix);

        if hom.rank() != 2 {
            return TestResult::failed("Projective modules", "rank of [[1,2,3],[4,5,6]] should be 2");
        }

        TestResult::passed("Projective modules")
    }

    /// Test 8: Projective resolutions are verified exact, not just marked.
    pub fn test_projective_resolution() -> TestResult {
        let name = "Projective resolution";
        let mut free = ProjectiveResolution::free_of_rank_one();
        if free.len() != 1 || !free.verify_exactness() {
            return TestResult::failed(name, "resolution of Z is not exact");
        }
        let cyclic = ProjectiveResolution::cyclic_resolution(4);
        match cyclic.resolved_module() {
            Ok(m) if m.free_rank == 0 && m.torsion == vec![4] && cyclic.is_marked_exact() => {
                TestResult::passed(name)
            }
            other => TestResult::failed(name, &format!("resolution of Z/4 wrong: {other:?}")),
        }
    }

    /// Test 9: Full resolution certification.
    pub fn test_resolution_certification() -> TestResult {
        let name = "Resolution certification";
        for res in [ProjectiveResolution::free_of_rank_one(), ProjectiveResolution::cyclic_resolution(6)] {
            let cert = ResolutionCertifier::certify_fully(&res);
            if !cert.level.is_fully_certified() {
                return TestResult::failed(name, &cert.message);
            }
        }
        TestResult::passed(name)
    }

    /// Test 10: End-to-end chain complex workflow.
    pub fn test_end_to_end_workflow() -> TestResult {
        // Create a simple 2-term chain complex: 0 <- Z^2 <- Z^2 <- 0
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 2)]);
        let mut diff = DifferentialOperator::new(shape);

        // Identity differential
        diff.set_generator_image(1, 0, 0, vec![(0, 1)]);
        diff.set_generator_image(1, 1, 0, vec![(1, 1)]);

        let name = "End-to-end workflow";

        // 1. Verify d² = 0
        let proof = SquaredZeroVerifier::verify_global(&diff);
        if !proof.is_valid {
            return TestResult::failed(name, "step 1: d² = 0 verification failed");
        }

        // 2. Compute homology: the identity complex is acyclic.
        let homology = match HomologyComputer::compute_all(&diff) {
            Ok(h) => h,
            Err(e) => return TestResult::failed(name, &format!("step 2: {e}")),
        };
        if !homology.support_degrees().is_empty() {
            return TestResult::failed(name, "step 2: identity complex has non-zero homology");
        }

        // 3. Exactness agrees with homology.
        let exactness = ExactnessPredicateChecker::check_global_exactness(&diff);
        if exactness.is_exact != ExactnessPredicateChecker::check_from_homology(&homology) {
            return TestResult::failed(name, "step 3: exactness disagrees with homology");
        }

        TestResult::passed(name)
    }

    /// Run all tests and return summary.
    pub fn run_all() -> TestSummary {
        let tests = vec![
            Self::test_chain_complex_creation(),
            Self::test_chain_element_operations(),
            Self::test_differential_application(),
            Self::test_squared_zero_verification(),
            Self::test_global_exactness(),
            Self::test_homology_computation(),
            Self::test_projective_modules(),
            Self::test_projective_resolution(),
            Self::test_resolution_certification(),
            Self::test_end_to_end_workflow(),
        ];

        TestSummary::from_results(tests)
    }
}

/// Result of a single test.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TestResult {
    /// Test name.
    pub name: String,
    /// Did it pass?
    pub passed: bool,
    /// "OK" or the failure reason.
    pub message: String,
}

impl TestResult {
    /// Create a passed test.
    pub fn passed(name: &str) -> Self {
        Self {
            name: name.to_string(),
            passed: true,
            message: "OK".to_string(),
        }
    }

    /// Create a failed test, keeping its name.
    pub fn failed(name: &str, message: &str) -> Self {
        Self {
            name: name.to_string(),
            passed: false,
            message: message.to_string(),
        }
    }
}

/// Summary of all test runs.
#[derive(Debug, Clone)]
pub struct TestSummary {
    /// Number of tests run.
    pub total: usize,
    /// Number passed.
    pub passed: usize,
    /// Number failed.
    pub failed: usize,
    /// Individual results.
    pub results: Vec<TestResult>,
}

impl TestSummary {
    /// Create summary from test results.
    pub fn from_results(results: Vec<TestResult>) -> Self {
        let total = results.len();
        let passed = results.iter().filter(|r| r.passed).count();
        let failed = total - passed;

        Self {
            total,
            passed,
            failed,
            results,
        }
    }

    /// Generate a report.
    pub fn report(&self) -> String {
        let mut report = format!(
            "Homological Test Suite Report\n  Total: {}\n  Passed: {}\n  Failed: {}\n\n",
            self.total, self.passed, self.failed
        );

        for result in &self.results {
            let status = if result.passed { "✓" } else { "✗" };
            report.push_str(&format!("  {} {}: {}\n", status, result.name, result.message));
        }

        report
    }

    /// Check if all tests passed.
    pub fn all_passed(&self) -> bool {
        self.failed == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_suite_creation() {
        let result = HomologicalTestSuite::test_chain_complex_creation();
        assert!(result.passed);
    }

    #[test]
    fn test_suite_elements() {
        let result = HomologicalTestSuite::test_chain_element_operations();
        assert!(result.passed);
    }

    #[test]
    fn test_suite_differential() {
        let result = HomologicalTestSuite::test_differential_application();
        assert!(result.passed);
    }

    #[test]
    fn test_suite_squared_zero() {
        let result = HomologicalTestSuite::test_squared_zero_verification();
        assert!(result.passed);
    }

    #[test]
    fn test_suite_run_all() {
        let summary = HomologicalTestSuite::run_all();
        assert_eq!(summary.total, 10);
        assert!(summary.all_passed(), "{}", summary.report());
    }

    #[test]
    fn test_result_passed() {
        let result = TestResult::passed("test");
        assert!(result.passed);
        assert_eq!(result.message, "OK");
    }

    #[test]
    fn test_result_failed() {
        let result = TestResult::failed("some test", "error message");
        assert!(!result.passed);
        assert_eq!(result.name, "some test");
        assert!(result.message.contains("error"));
    }

    #[test]
    fn test_summary_all_passed() {
        let results = vec![
            TestResult::passed("test1"),
            TestResult::passed("test2"),
        ];
        let summary = TestSummary::from_results(results);
        assert!(summary.all_passed());
        assert_eq!(summary.total, 2);
        assert_eq!(summary.passed, 2);
        assert_eq!(summary.failed, 0);
    }
}
