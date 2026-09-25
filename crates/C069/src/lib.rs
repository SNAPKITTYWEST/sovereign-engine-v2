//! krull_certification
//!
//! Certification that Krull dimension is correct.
//! Verify computation against bounds and algebraic properties.

#![warn(missing_docs)]

use spectrum_definition::Spectrum;
use spectrum_order::SpecializationPreorder;
use spectrum_chains::MaximalChains;
use krull_dimension_definition::KrullDim;
use dimension_upper_bounds::BoundCollection;

/// Proof that a dimension computation is correct: the exhaustive chain
/// enumeration's longest chains, checked to be strictly increasing and of
/// length `dim + 1`, plus (optionally) upper bounds.
#[derive(Clone, Debug)]
pub struct DimensionProof {
    /// Computed dimension
    pub dimension: KrullDim,
    /// Result of the last [`Self::check_bounds`] (`false` until bounds are
    /// checked — see `bounds_checked`)
    pub bounds_satisfied: bool,
    /// Whether [`Self::check_bounds`] has been run
    pub bounds_checked: bool,
    /// Longest chain achieving dimension
    pub longest_chain: Vec<u64>,
    /// All chains of maximal length
    pub maximal_chains: Vec<Vec<u64>>,
    /// The longest chains have `dim + 1` elements
    pub chain_length_ok: bool,
    /// Every maximal-length chain is strictly increasing in the
    /// specialization order
    pub chains_strictly_increasing: bool,
}

impl DimensionProof {
    /// Create proof from spectrum
    pub fn from_spectrum(spec: &Spectrum) -> Self {
        let dimension = KrullDim::from_spectrum(spec);
        let preorder = SpecializationPreorder::from_spectrum(spec);
        let chains = MaximalChains::find_all(spec, &preorder);

        let maximal_chains = dimension_chains(&chains);
        let longest_chain = maximal_chains.first().cloned().unwrap_or_default();
        let chain_length_ok = match maximal_chains.first() {
            Some(chain) => chain.len() == dimension.dim() + 1,
            None => dimension.dim() == 0,
        };
        let chains_strictly_increasing = maximal_chains.iter().all(|c| {
            c.windows(2)
                .all(|w| w[0] != w[1] && preorder.le(w[0], w[1]) && !preorder.le(w[1], w[0]))
        });

        Self {
            dimension,
            bounds_satisfied: false,
            bounds_checked: false,
            longest_chain,
            maximal_chains,
            chain_length_ok,
            chains_strictly_increasing,
        }
    }

    /// The chain witness is valid, and any checked bounds hold.
    pub fn verify(&self) -> bool {
        self.chain_length_ok
            && self.chains_strictly_increasing
            && self.verify_chain_lengths()
            && (!self.bounds_checked || self.bounds_satisfied)
    }

    /// Every recorded maximal chain has `dim + 1` elements.
    fn verify_chain_lengths(&self) -> bool {
        self.maximal_chains
            .iter()
            .all(|chain| chain.len() == self.dimension.dim() + 1)
    }

    /// Check dimension against upper bounds
    pub fn check_bounds(&mut self, bounds: &BoundCollection) {
        self.bounds_satisfied = bounds.all_satisfied(self.dimension);
        self.bounds_checked = true;
    }
}

/// Get maximal chains from chain finder
fn dimension_chains(chains: &spectrum_chains::MaximalChains) -> Vec<Vec<u64>> {
    chains
        .chains()
        .iter()
        .filter(|c| c.len() == chains.longest_length())
        .map(|c| c.elements().to_vec())
        .collect()
}

use spectrum_chains;

/// Certification checker with multiple properties
#[derive(Clone, Debug)]
pub struct CertificationChecker {
    spec: Spectrum,
    proof: DimensionProof,
}

impl CertificationChecker {
    /// Create checker for spectrum
    pub fn new(spec: Spectrum) -> Self {
        let proof = DimensionProof::from_spectrum(&spec);
        Self { spec, proof }
    }

    /// Run all certification checks. Bound checks are included only if
    /// bounds have been verified with [`Self::verify_bounds`].
    pub fn check_all(&mut self) -> CertificationResult {
        let mut results = CertificationResult::new();
        let dim = self.proof.dimension.dim();

        results.add_check("chain_ordering", self.proof.chains_strictly_increasing);
        results.add_check("chain_witness", self.proof.chain_length_ok && self.proof.verify_chain_lengths());
        results.add_check("catenary_property", KrullDim::is_catenary(&self.spec));
        results.add_check(
            "bounded_by_spectrum_size",
            dim + 1 <= self.spec.len().max(1),
        );
        if self.proof.bounds_checked {
            results.add_check("upper_bounds", self.proof.bounds_satisfied);
        }
        results
    }

    /// Verify against specific bounds
    pub fn verify_bounds(&mut self, bounds: &BoundCollection) -> bool {
        self.proof.check_bounds(bounds);
        self.proof.bounds_satisfied
    }

    /// Get the proof
    pub fn proof(&self) -> &DimensionProof {
        &self.proof
    }
}

/// Result of certification checks
#[derive(Clone, Debug)]
pub struct CertificationResult {
    checks: std::collections::BTreeMap<String, bool>,
}

impl CertificationResult {
    /// Create empty result
    pub fn new() -> Self {
        Self {
            checks: std::collections::BTreeMap::new(),
        }
    }

    /// Add a check result
    pub fn add_check(&mut self, name: &str, passed: bool) {
        self.checks.insert(name.to_string(), passed);
    }

    /// All checks passed
    pub fn all_passed(&self) -> bool {
        self.checks.values().all(|&b| b)
    }

    /// Get individual check result
    pub fn check(&self, name: &str) -> Option<bool> {
        self.checks.get(name).copied()
    }

    /// Get all checks
    pub fn checks(&self) -> &std::collections::BTreeMap<String, bool> {
        &self.checks
    }

    /// Count passed checks
    pub fn passed_count(&self) -> usize {
        self.checks.values().filter(|&&b| b).count()
    }

    /// Count total checks
    pub fn total_count(&self) -> usize {
        self.checks.len()
    }

    /// Get failed checks
    pub fn failed_checks(&self) -> Vec<String> {
        self.checks
            .iter()
            .filter(|(_, &b)| !b)
            .map(|(name, _)| name.clone())
            .collect()
    }
}

impl Default for CertificationResult {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dimension_proof_empty() {
        let spec = Spectrum::empty();
        let proof = DimensionProof::from_spectrum(&spec);
        assert_eq!(proof.dimension.dim(), 0);
    }

    #[test]
    fn test_dimension_proof_single_point() {
        let spec = Spectrum::new(vec![2]);
        let proof = DimensionProof::from_spectrum(&spec);
        assert!(proof.verify());
        assert!(proof.chain_length_ok);
    }

    #[test]
    fn test_certification_checker() {
        for primes in [vec![2, 3, 5], vec![0, 2, 3, 5, 7]] {
            let spec = Spectrum::new(primes);
            let mut checker = CertificationChecker::new(spec);
            let result = checker.check_all();
            assert!(result.all_passed(), "failed: {:?}", result.failed_checks());
            assert_eq!(result.check("upper_bounds"), None);
        }
    }

    #[test]
    fn spec_z_proof_has_strict_chains() {
        let proof = DimensionProof::from_spectrum(&Spectrum::new(vec![0, 2, 3]));
        assert_eq!(proof.dimension.dim(), 1);
        assert!(proof.chains_strictly_increasing);
        assert_eq!(proof.maximal_chains, vec![vec![0, 2], vec![0, 3]]);
        assert!(proof.verify());
    }

    #[test]
    fn violated_bounds_fail_verification() {
        let mut checker = CertificationChecker::new(Spectrum::new(vec![0, 2, 3]));
        let mut bounds = BoundCollection::new();
        bounds.add_generator_bound(0);
        assert!(!checker.verify_bounds(&bounds));
        assert!(checker.proof().bounds_checked);
        assert!(!checker.proof().verify());
        assert_eq!(checker.check_all().check("upper_bounds"), Some(false));
    }

    #[test]
    fn test_certification_result() {
        let mut result = CertificationResult::new();
        result.add_check("test1", true);
        result.add_check("test2", false);

        assert_eq!(result.passed_count(), 1);
        assert_eq!(result.total_count(), 2);
        assert!(!result.all_passed());
        assert!(!result.failed_checks().is_empty());
    }

    #[test]
    fn test_verify_bounds() {
        let spec = Spectrum::new(vec![2, 3]);
        let mut checker = CertificationChecker::new(spec);
        let mut bounds = BoundCollection::new();
        bounds.add_generator_bound(3);

        assert!(checker.verify_bounds(&bounds));
    }
}
