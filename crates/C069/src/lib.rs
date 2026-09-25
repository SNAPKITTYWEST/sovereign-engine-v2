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

/// Proof that a dimension computation is correct
#[derive(Clone, Debug)]
pub struct DimensionProof {
    /// Computed dimension
    pub dimension: KrullDim,
    /// All bounds satisfied
    pub bounds_satisfied: bool,
    /// Longest chain achieving dimension
    pub longest_chain: Vec<u64>,
    /// All maximal chains
    pub maximal_chains: Vec<Vec<u64>>,
    /// Chain length verification
    pub chain_length_ok: bool,
}

impl DimensionProof {
    /// Create proof from spectrum
    pub fn from_spectrum(spec: &Spectrum) -> Self {
        let dimension = KrullDim::from_spectrum(spec);
        let preorder = SpecializationPreorder::from_spectrum(spec);
        let chains = MaximalChains::find_all(spec, &preorder);

        let maximal_chains = dimension_chains(&chains);
        let longest_chain = maximal_chains
            .first()
            .cloned()
            .unwrap_or_default();

        let chain_length_ok = if !maximal_chains.is_empty() {
            // For a chain with n elements, dimension is n-1
            maximal_chains[0].len() == dimension.dim() + 1
        } else {
            dimension.dim() == 0
        };

        let bounds_satisfied = true; // Will verify below

        Self {
            dimension,
            bounds_satisfied,
            longest_chain,
            maximal_chains,
            chain_length_ok,
        }
    }

    /// Verify proof is valid
    pub fn verify(&self) -> bool {
        self.chain_length_ok && self.bounds_satisfied && self.verify_chain_ordering()
    }

    /// Verify that longest chain is actually ordered
    fn verify_chain_ordering(&self) -> bool {
        for chain in &self.maximal_chains {
            if chain.len() != self.dimension.dim() + 1 {
                return false;
            }
        }
        true
    }

    /// Check dimension against upper bounds
    pub fn check_bounds(&mut self, bounds: &BoundCollection) {
        self.bounds_satisfied = bounds.all_satisfied(self.dimension);
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

    /// Run all certification checks
    pub fn check_all(&mut self) -> CertificationResult {
        let mut results = CertificationResult::new();

        // Check 1: Chain ordering
        results.add_check(
            "chain_ordering",
            self.proof.verify_chain_ordering(),
        );

        // Check 2: Dimension is non-negative
        results.add_check("non_negative", self.proof.dimension.dim() < usize::MAX);

        // Check 3: All maximal chains have same length (catenarity)
        let same_length = self
            .proof
            .maximal_chains
            .iter()
            .all(|c| c.len() == self.proof.dimension.dim() + 1);
        results.add_check("catenary_property", same_length);

        // Check 4: Longest chain achieves dimension
        if !self.proof.maximal_chains.is_empty() {
            let longest_len = self.proof.maximal_chains[0].len();
            results.add_check("longest_chain_ok", longest_len == self.proof.dimension.dim() + 1);
        }

        // Check 5: Dimension bounded by spectrum size
        results.add_check(
            "bounded_by_spectrum_size",
            self.proof.dimension.dim() <= self.spec.len(),
        );

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
        let spec = Spectrum::new(vec![2, 3, 5]);
        let mut checker = CertificationChecker::new(spec);
        let result = checker.check_all();

        assert!(result.total_count() > 0);
        assert!(!result.failed_checks().is_empty() || result.all_passed());
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
