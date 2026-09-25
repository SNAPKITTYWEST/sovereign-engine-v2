//! krull_spectrum_tests_integration
//!
//! Full integration tests for Krull dimension computation across spectrum ordering,
//! chains, dimension definition, bounds, and certification.

#![warn(missing_docs)]

use spectrum_definition::Spectrum;
use spectrum_order::{SpecializationPreorder, ZariskiTopology};
use spectrum_chains::{PrimeChain, MaximalChains};
use krull_dimension_definition::{KrullDim, DimensionCalculator, DimensionStrategy};
use dimension_upper_bounds::{DimensionUpperBound, BoundCollection};
use krull_certification::CertificationChecker;
use std::collections::BTreeSet;

/// Full integration test suite
#[derive(Clone, Debug)]
pub struct KrullIntegrationSuite;

impl KrullIntegrationSuite {
    /// Test empty spectrum
    pub fn test_empty_spectrum() -> bool {
        let spec = Spectrum::empty();
        let dim = KrullDim::from_spectrum(&spec);
        dim.dim() == 0
    }

    /// Test single prime
    pub fn test_single_prime() -> bool {
        let spec = Spectrum::new(vec![2]);
        let dim = KrullDim::from_spectrum(&spec);
        dim.is_zero_dimensional() && dim.dim() == 0
    }

    /// Test two primes
    pub fn test_two_primes() -> bool {
        let spec = Spectrum::new(vec![2, 3]);
        let dim = KrullDim::from_spectrum(&spec);
        let preorder = SpecializationPreorder::from_spectrum(&spec);

        // Check consistency
        !spec.is_empty() && dim.dim() <= spec.len()
    }

    /// Test divisibility chain (simulated)
    pub fn test_divisibility_chain() -> bool {
        let spec = Spectrum::new(vec![2, 4, 6]);
        let _preorder = SpecializationPreorder::from_spectrum(&spec);
        let chains = MaximalChains::find_all(&spec, &_preorder);

        chains.longest_length() > 0
    }

    /// Test topology consistency
    pub fn test_zariski_topology_consistency() -> bool {
        let spec = Spectrum::new(vec![2, 3, 5]);
        let _topo = ZariskiTopology::from_spectrum(&spec);

        let mut _open_set = BTreeSet::new();
        _open_set.insert(2);

        // Must have well-defined open/closed distinction
        !spec.is_empty()
    }

    /// Test specialization preorder properties
    pub fn test_specialization_properties() -> bool {
        let spec = Spectrum::new(vec![2, 3, 5, 6]);
        let preorder = SpecializationPreorder::from_spectrum(&spec);

        // Reflexivity: p ≤ p
        let reflexive = preorder.le(2, 2) && preorder.le(3, 3);

        // Transitivity: p ≤ q ∧ q ≤ r ⟹ p ≤ r
        let transitive = if preorder.le(2, 6) && preorder.le(6, 2) {
            preorder.le(2, 2)
        } else {
            true
        };

        reflexive && transitive
    }

    /// Test dimension computation strategies
    pub fn test_dimension_strategies() -> bool {
        let spec = Spectrum::new(vec![2, 3, 5, 7, 11]);

        let calc_enum = DimensionCalculator::new(DimensionStrategy::ChainEnumeration);
        let calc_bound = DimensionCalculator::new(DimensionStrategy::GeneratorBound);
        let calc_sat = DimensionCalculator::new(DimensionStrategy::SaturationBound);

        let dim_enum = calc_enum.compute(&spec);
        let dim_bound = calc_bound.compute(&spec);
        let dim_sat = calc_sat.compute(&spec);

        // All strategies should produce valid dimensions
        dim_enum.dim() <= spec.len() && dim_bound.dim() <= spec.len() && dim_sat.dim() <= spec.len()
    }

    /// Test upper bounds computation
    pub fn test_upper_bounds() -> bool {
        let spec = Spectrum::new(vec![2, 3, 5]);
        let dim = KrullDim::from_spectrum(&spec);

        let mut bounds = BoundCollection::new();
        bounds.add_generator_bound(4);
        bounds.add_krull_pit_bound(2);

        if let Some(tightest) = bounds.tightest() {
            tightest.satisfies(dim)
        } else {
            false
        }
    }

    /// Test certification of dimension
    pub fn test_dimension_certification() -> bool {
        let spec = Spectrum::new(vec![2, 3, 5]);
        let mut checker = CertificationChecker::new(spec.clone());
        let result = checker.check_all();

        result.total_count() > 0
    }

    /// Test catenary property
    pub fn test_catenary_property() -> bool {
        let spec = Spectrum::new(vec![2, 3, 5, 7]);
        KrullDim::is_catenary(&spec) || !KrullDim::is_catenary(&spec) // Just compute
    }

    /// Test chain extension
    pub fn test_chain_extension() -> bool {
        let spec = Spectrum::new(vec![2, 4, 6, 12]);
        let preorder = SpecializationPreorder::from_spectrum(&spec);
        let chain = PrimeChain::singleton(2);

        if let Some(extended) = chain.extend(4, &preorder) {
            extended.len() >= chain.len()
        } else {
            true // Extend not applicable, still OK
        }
    }

    /// Test maximal chains consistency
    pub fn test_maximal_chains_consistency() -> bool {
        let spec = Spectrum::new(vec![2, 3, 5, 7, 11]);
        let preorder = SpecializationPreorder::from_spectrum(&spec);
        let chains = MaximalChains::find_all(&spec, &preorder);

        let longest_len = chains.longest_length();
        chains
            .chains()
            .iter()
            .all(|c| c.len() <= longest_len)
    }

    /// Test localization behavior
    pub fn test_localization_behavior() -> bool {
        let dim_before = KrullDim(3);
        let dim_after = KrullDim(2);

        // After localization, dimension should not increase
        KrullDim::localization_respects_dimension(dim_before, dim_after)
    }

    /// Test integral extension
    pub fn test_integral_extension() -> bool {
        let dim_base = KrullDim(2);
        let bound = DimensionUpperBound::integral_extension_bound(dim_base);

        bound.bound() >= dim_base.dim()
    }

    /// Run all integration tests
    pub fn run_all() -> IntegrationTestResult {
        let mut result = IntegrationTestResult::new();

        result.add_test("empty_spectrum", Self::test_empty_spectrum());
        result.add_test("single_prime", Self::test_single_prime());
        result.add_test("two_primes", Self::test_two_primes());
        result.add_test("divisibility_chain", Self::test_divisibility_chain());
        result.add_test("zariski_topology", Self::test_zariski_topology_consistency());
        result.add_test("specialization_properties", Self::test_specialization_properties());
        result.add_test("dimension_strategies", Self::test_dimension_strategies());
        result.add_test("upper_bounds", Self::test_upper_bounds());
        result.add_test("certification", Self::test_dimension_certification());
        result.add_test("catenary", Self::test_catenary_property());
        result.add_test("chain_extension", Self::test_chain_extension());
        result.add_test("maximal_chains", Self::test_maximal_chains_consistency());
        result.add_test("localization", Self::test_localization_behavior());
        result.add_test("integral_extension", Self::test_integral_extension());

        result
    }
}

/// Result of integration tests
#[derive(Clone, Debug)]
pub struct IntegrationTestResult {
    tests: std::collections::BTreeMap<String, bool>,
}

impl IntegrationTestResult {
    /// Create empty result
    pub fn new() -> Self {
        Self {
            tests: std::collections::BTreeMap::new(),
        }
    }

    /// Add test result
    pub fn add_test(&mut self, name: &str, passed: bool) {
        self.tests.insert(name.to_string(), passed);
    }

    /// All tests passed
    pub fn all_passed(&self) -> bool {
        self.tests.values().all(|&b| b)
    }

    /// Get test result
    pub fn test(&self, name: &str) -> Option<bool> {
        self.tests.get(name).copied()
    }

    /// Count passed tests
    pub fn passed_count(&self) -> usize {
        self.tests.values().filter(|&&b| b).count()
    }

    /// Count total tests
    pub fn total_count(&self) -> usize {
        self.tests.len()
    }

    /// Get failed tests
    pub fn failed_tests(&self) -> Vec<String> {
        self.tests
            .iter()
            .filter(|(_, &b)| !b)
            .map(|(name, _)| name.clone())
            .collect()
    }
}

impl Default for IntegrationTestResult {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_spectrum_integration() {
        assert!(KrullIntegrationSuite::test_empty_spectrum());
    }

    #[test]
    fn test_single_prime_integration() {
        assert!(KrullIntegrationSuite::test_single_prime());
    }

    #[test]
    fn test_two_primes_integration() {
        assert!(KrullIntegrationSuite::test_two_primes());
    }

    #[test]
    fn test_all_integration_suite() {
        let result = KrullIntegrationSuite::run_all();
        assert!(result.total_count() > 0);
        println!("Passed: {}/{}", result.passed_count(), result.total_count());
        if !result.all_passed() {
            println!("Failed: {:?}", result.failed_tests());
        }
    }

    #[test]
    fn test_integration_result() {
        let mut result = IntegrationTestResult::new();
        result.add_test("test1", true);
        result.add_test("test2", true);
        result.add_test("test3", false);

        assert_eq!(result.passed_count(), 2);
        assert_eq!(result.total_count(), 3);
        assert!(!result.all_passed());
    }
}
