//! cross_layer_lemmas_library
//!
//! Cross-tier lemmas relating different layers of the system.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use type_checking_interface::{LeanType, ProofTerm};

/// A cross-layer relationship between two tiers
#[derive(Clone, Debug)]
pub struct CrossLayerLemma {
    /// Lemma identifier
    pub id: String,
    /// Source tier (0-9)
    pub source_tier: usize,
    /// Target tier
    pub target_tier: usize,
    /// Statement of the lemma
    pub statement: LeanType,
    /// Proof term (if proven)
    pub proof: Option<ProofTerm>,
}

impl CrossLayerLemma {
    /// Create a cross-layer lemma
    pub fn new(
        id: String,
        source_tier: usize,
        target_tier: usize,
        statement: LeanType,
    ) -> Self {
        Self {
            id,
            source_tier,
            target_tier,
            statement,
            proof: None,
        }
    }

    /// Prove the lemma
    pub fn prove(&mut self, proof: ProofTerm) {
        if proof.is_complete() {
            self.proof = Some(proof);
        }
    }

    /// Is this lemma proven?
    pub fn is_proven(&self) -> bool {
        self.proof.is_some()
    }

    /// Get direction name
    pub fn direction_name(&self) -> String {
        format!(
            "Tier {} -> Tier {}",
            self.source_tier, self.target_tier
        )
    }
}

/// Collection of cross-layer relationships
#[derive(Clone, Debug)]
pub struct CrossLayerLemmaLibrary {
    /// Lemmas organized by direction
    pub lemmas: BTreeMap<String, CrossLayerLemma>,
}

impl CrossLayerLemmaLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
        }
    }

    /// Add a lemma to the library
    pub fn add_lemma(&mut self, lemma: CrossLayerLemma) {
        self.lemmas.insert(lemma.id.clone(), lemma);
    }

    /// Get a lemma by ID
    pub fn get_lemma(&self, id: &str) -> Option<&CrossLayerLemma> {
        self.lemmas.get(id)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.is_proven())
            .count()
    }

    /// Get all lemmas for a given tier transition
    pub fn lemmas_for_transition(
        &self,
        from: usize,
        to: usize,
    ) -> Vec<&CrossLayerLemma> {
        self.lemmas
            .values()
            .filter(|l| l.source_tier == from && l.target_tier == to)
            .collect()
    }

    /// Check if two tiers are related (direct lemma exists)
    pub fn are_tiers_related(&self, tier1: usize, tier2: usize) -> bool {
        !self.lemmas_for_transition(tier1, tier2).is_empty()
            || !self.lemmas_for_transition(tier2, tier1).is_empty()
    }

    /// Get proof coverage (% of lemmas with proofs)
    pub fn proof_coverage(&self) -> f64 {
        if self.lemmas.is_empty() {
            return 1.0;
        }
        self.count_proven() as f64 / self.lemmas.len() as f64
    }
}

impl Default for CrossLayerLemmaLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cross_layer_lemma_creation() {
        let lemma = CrossLayerLemma::new(
            "tier2_to_tier3".to_string(),
            2,
            3,
            LeanType::prop(),
        );
        assert_eq!(lemma.source_tier, 2);
        assert_eq!(lemma.target_tier, 3);
        assert!(!lemma.is_proven());
    }

    #[test]
    fn test_cross_layer_lemma_prove() {
        let mut lemma = CrossLayerLemma::new(
            "test".to_string(),
            0,
            1,
            LeanType::prop(),
        );
        lemma.prove(ProofTerm::Trivial);
        assert!(lemma.is_proven());
    }

    #[test]
    fn test_cross_layer_library_add() {
        let mut lib = CrossLayerLemmaLibrary::new();
        let lemma = CrossLayerLemma::new(
            "test".to_string(),
            0,
            1,
            LeanType::prop(),
        );
        lib.add_lemma(lemma);
        assert_eq!(lib.lemmas.len(), 1);
    }

    #[test]
    fn test_cross_layer_library_coverage() {
        let mut lib = CrossLayerLemmaLibrary::new();
        let mut lemma1 = CrossLayerLemma::new(
            "test1".to_string(),
            0,
            1,
            LeanType::prop(),
        );
        lemma1.prove(ProofTerm::Trivial);
        lib.add_lemma(lemma1);

        let lemma2 = CrossLayerLemma::new(
            "test2".to_string(),
            1,
            2,
            LeanType::prop(),
        );
        lib.add_lemma(lemma2);

        assert_eq!(lib.proof_coverage(), 0.5);
    }

    #[test]
    fn test_cross_layer_library_transition() {
        let mut lib = CrossLayerLemmaLibrary::new();
        let lemma = CrossLayerLemma::new(
            "test".to_string(),
            2,
            3,
            LeanType::prop(),
        );
        lib.add_lemma(lemma);
        assert_eq!(lib.lemmas_for_transition(2, 3).len(), 1);
        assert_eq!(lib.lemmas_for_transition(3, 2).len(), 0);
    }
}
