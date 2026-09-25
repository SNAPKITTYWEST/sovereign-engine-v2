//! krull_spectrum_tests_integration
//!
//! Integration scenarios for the Krull tier (C061–C069) on Spec(Z) and its
//! subspaces, each checked against known mathematics: `dim Spec(Z) = 1` via
//! the chains `(0) ⊂ (p)`, closed points form a 0-dimensional space, the
//! generic point `(0)` is dense, and ideal arithmetic follows gcd/lcm.

#![warn(missing_docs)]

use dimension_upper_bounds::{BoundCollection, DimensionUpperBound};
use ideal_interface::Ideal;
use krull_certification::CertificationChecker;
use krull_dimension_definition::{DimensionCalculator, DimensionStrategy, KrullDim};
use maximal_ideal_predicate::is_maximal_ideal;
use prime_ideal_predicate::is_prime_ideal;
use spectrum_chains::{MaximalChains, PrimeChain};
use spectrum_definition::Spectrum;
use spectrum_order::{SpecializationPreorder, ZariskiTopology};
use std::collections::BTreeSet;

const SMALL_PRIMES: [u64; 15] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47];

fn spec_z() -> Spectrum {
    let mut points = vec![0];
    points.extend(SMALL_PRIMES);
    Spectrum::new(points)
}

fn closed_points() -> Spectrum {
    Spectrum::new(SMALL_PRIMES.to_vec())
}

/// Full integration test suite
#[derive(Clone, Debug)]
pub struct KrullIntegrationSuite;

impl KrullIntegrationSuite {
    /// The empty spectrum has dimension 0 and no chains.
    pub fn test_empty_spectrum() -> bool {
        let spec = Spectrum::empty();
        KrullDim::from_spectrum(&spec) == KrullDim(0) && KrullDim::maximal_chains(&spec).is_empty()
    }

    /// A single closed point has dimension 0.
    pub fn test_single_prime() -> bool {
        let spec = Spectrum::new(vec![2]);
        KrullDim::from_spectrum(&spec).is_zero_dimensional() && spec.len() == 1
    }

    /// Finitely many closed points: dimension 0, one singleton chain each.
    pub fn test_two_primes() -> bool {
        let spec = closed_points();
        let chains = KrullDim::maximal_chains(&spec);
        KrullDim::from_spectrum(&spec) == KrullDim(0)
            && chains.len() == SMALL_PRIMES.len()
            && chains.iter().all(|c| c.len() == 1)
    }

    /// Spec(Z) truncated to small primes has dimension 1, and every longest
    /// chain is `(0) ⊂ (p)`.
    pub fn test_divisibility_chain() -> bool {
        let spec = spec_z();
        let chains = KrullDim::maximal_chains(&spec);
        KrullDim::from_spectrum(&spec) == KrullDim(1)
            && chains.len() == SMALL_PRIMES.len()
            && chains.iter().all(|c| c.len() == 2 && c[0] == 0 && SMALL_PRIMES.contains(&c[1]))
    }

    /// The generic point is dense; closed points are closed.
    pub fn test_zariski_topology_consistency() -> bool {
        let spec = spec_z();
        let topo = ZariskiTopology::from_spectrum(&spec);
        let everything: BTreeSet<u64> = spec.primes.iter().copied().collect();
        let generic: BTreeSet<u64> = [0].into_iter().collect();
        topo.closure(&generic, &spec) == everything
            && SMALL_PRIMES
                .iter()
                .all(|&p| topo.is_closed(&[p].into_iter().collect(), &spec))
            && !topo.is_closed(&generic, &spec)
    }

    /// The specialization order on Spec(Z) is a partial order with (0) at the
    /// bottom.
    pub fn test_specialization_properties() -> bool {
        let spec = spec_z();
        let order = SpecializationPreorder::from_spectrum(&spec);
        let points: Vec<u64> = spec.primes.iter().copied().collect();
        let reflexive = points.iter().all(|&p| order.le(p, p));
        let antisymmetric = points
            .iter()
            .all(|&p| points.iter().all(|&q| p == q || !(order.le(p, q) && order.le(q, p))));
        let transitive = points.iter().all(|&p| {
            points.iter().all(|&q| {
                points
                    .iter()
                    .all(|&r| !(order.le(p, q) && order.le(q, r)) || order.le(p, r))
            })
        });
        reflexive && antisymmetric && transitive && spec.minimal_primes() == vec![0]
    }

    /// Upper-bound strategies never undercut the exact dimension.
    pub fn test_dimension_strategies() -> bool {
        [closed_points(), spec_z(), Spectrum::empty()].iter().all(|spec| {
            let exact = DimensionCalculator::new(DimensionStrategy::ChainEnumeration).compute(spec);
            [DimensionStrategy::GeneratorBound, DimensionStrategy::SaturationBound]
                .into_iter()
                .all(|s| DimensionCalculator::new(s).compute(spec) >= exact)
        })
    }

    /// Bounds are checked honestly: a true bound passes, a false one fails.
    pub fn test_upper_bounds() -> bool {
        let dim = KrullDim::from_spectrum(&spec_z());
        let mut good = BoundCollection::new();
        good.add_generator_bound(3);
        good.add_krull_pit_bound(1);
        let mut bad = BoundCollection::new();
        bad.add_krull_pit_bound(0);
        good.tightest() == Some(DimensionUpperBound(1)) && good.all_satisfied(dim) && !bad.all_satisfied(dim)
    }

    /// Certification passes for both spectra and catches a violated bound.
    pub fn test_dimension_certification() -> bool {
        let passes = [closed_points(), spec_z()]
            .into_iter()
            .all(|spec| CertificationChecker::new(spec).check_all().all_passed());
        let mut checker = CertificationChecker::new(spec_z());
        let mut bad = BoundCollection::new();
        bad.add_generator_bound(0);
        passes && !checker.verify_bounds(&bad) && !checker.check_all().all_passed()
    }

    /// Both model spectra are catenary.
    pub fn test_catenary_property() -> bool {
        KrullDim::is_catenary(&spec_z()) && KrullDim::is_catenary(&closed_points())
    }

    /// Chains extend only strictly upward.
    pub fn test_chain_extension() -> bool {
        let spec = spec_z();
        let order = SpecializationPreorder::from_spectrum(&spec);
        let generic = PrimeChain::singleton(0);
        let up = generic.extend(7, &order);
        up.as_ref().map(|c| c.elements() == [0, 7]).unwrap_or(false)
            && generic.extend(0, &order).is_none()
            && PrimeChain::singleton(7).extend(0, &order).is_none()
            && PrimeChain::singleton(7).extend(11, &order).is_none()
            && up.map(|c| c.is_valid(&order)).unwrap_or(false)
    }

    /// Every maximal chain is valid and none is longer than the dimension
    /// allows.
    pub fn test_maximal_chains_consistency() -> bool {
        let spec = spec_z();
        let order = SpecializationPreorder::from_spectrum(&spec);
        let chains = MaximalChains::find_all(&spec, &order);
        chains.longest_length() == 2
            && chains.chains().iter().all(|c| c.is_valid(&order) && c.len() <= 2)
    }

    /// Ideal arithmetic in Z: membership by gcd, intersection by lcm, prime
    /// and maximal ideals.
    pub fn test_localization_behavior() -> bool {
        let membership = (1..=24u64).all(|a| {
            (1..=24u64).all(|b| {
                let (i, j) = (Ideal::principal(a), Ideal::principal(b));
                let meet = i.intersection(&j).expect("small lcm");
                let sum = i.sum(&j);
                (0..=48u64).all(|x| {
                    meet.contains(x) == (i.contains(x) && j.contains(x))
                        && sum.contains(x) == (x % sum.gcd() == 0)
                })
            })
        });
        let primes = is_prime_ideal(&Ideal::zero())
            && !is_maximal_ideal(&Ideal::zero())
            && SMALL_PRIMES.iter().all(|&p| is_maximal_ideal(&Ideal::principal(p)))
            && !is_prime_ideal(&Ideal::principal(4))
            && is_prime_ideal(&Ideal::new(vec![6, 10]));
        membership && primes && KrullDim::localization_respects_dimension(KrullDim(1), KrullDim(0))
    }

    /// An integral-extension bound equals the dimension it is built from.
    pub fn test_integral_extension() -> bool {
        let dim = KrullDim::from_spectrum(&spec_z());
        let bound = DimensionUpperBound::integral_extension_bound(dim);
        bound.bound() == dim.dim() && bound.satisfies(dim) && !DimensionUpperBound(0).satisfies(dim)
    }

    /// Run all integration tests
    pub fn run_all() -> IntegrationTestResult {
        let mut result = IntegrationTestResult::new();
        result.add_test("empty_spectrum", Self::test_empty_spectrum());
        result.add_test("single_prime", Self::test_single_prime());
        result.add_test("closed_points", Self::test_two_primes());
        result.add_test("spec_z_dimension_one", Self::test_divisibility_chain());
        result.add_test("zariski_topology", Self::test_zariski_topology_consistency());
        result.add_test("specialization_properties", Self::test_specialization_properties());
        result.add_test("dimension_strategies", Self::test_dimension_strategies());
        result.add_test("upper_bounds", Self::test_upper_bounds());
        result.add_test("certification", Self::test_dimension_certification());
        result.add_test("catenary", Self::test_catenary_property());
        result.add_test("chain_extension", Self::test_chain_extension());
        result.add_test("maximal_chains", Self::test_maximal_chains_consistency());
        result.add_test("ideal_arithmetic", Self::test_localization_behavior());
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
    fn test_all_integration_suite() {
        let result = KrullIntegrationSuite::run_all();
        assert_eq!(result.total_count(), 14);
        assert!(result.all_passed(), "failed: {:?}", result.failed_tests());
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
        assert_eq!(result.failed_tests(), vec!["test3".to_string()]);
    }
}
