//! homological_lemmas_library
//!
//! Proves theorems about chain complexes, exactness, and differential properties in homology.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};

/// Status of a homology lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HomologyLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Could not be proven
    Failed,
}

/// A homology or chain complex lemma
#[derive(Clone, Debug)]
pub struct HomologyLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: HomologyLemmaStatus,
    /// Optional proof
    pub proof: Option<ProofTerm>,
    /// Type: exactness, differential, homology, or general
    pub lemma_type: String,
}

impl HomologyLemma {
    /// Create a new homology lemma
    pub fn new(name: String, statement: LeanType, lemma_type: String) -> Self {
        Self {
            name,
            statement,
            status: HomologyLemmaStatus::Open,
            proof: None,
            lemma_type,
        }
    }

    /// Prove the lemma
    pub fn prove(&mut self, proof: ProofTerm) {
        if proof.is_complete() {
            self.proof = Some(proof);
            self.status = HomologyLemmaStatus::Closed;
        }
    }

    /// Check if proven
    pub fn is_proven(&self) -> bool {
        self.status == HomologyLemmaStatus::Closed
    }
}

/// Library of homology lemmas
#[derive(Clone, Debug)]
pub struct HomologyLemmasLibrary {
    /// All lemmas
    pub lemmas: BTreeMap<String, HomologyLemma>,
    /// Type context
    pub context: TypeContext,
}

impl HomologyLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: HomologyLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&HomologyLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut HomologyLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == HomologyLemmaStatus::Closed)
            .count()
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == HomologyLemmaStatus::Open)
            .count()
    }

    /// Get lemmas by type
    pub fn lemmas_by_type(&self, lemma_type: &str) -> Vec<&HomologyLemma> {
        self.lemmas
            .values()
            .filter(|l| l.lemma_type == lemma_type)
            .collect()
    }

    /// Get all exactness lemmas
    pub fn exactness_lemmas(&self) -> Vec<&HomologyLemma> {
        self.lemmas_by_type("exactness")
    }

    /// Get all differential lemmas
    pub fn differential_lemmas(&self) -> Vec<&HomologyLemma> {
        self.lemmas_by_type("differential")
    }
}

impl Default for HomologyLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_homology_lemma_creation() {
        let lemma =
            HomologyLemma::new("exact_seq".to_string(), LeanType::prop(), "exactness".to_string());
        assert_eq!(lemma.status, HomologyLemmaStatus::Open);
        assert_eq!(lemma.lemma_type, "exactness");
    }

    #[test]
    fn test_homology_lemma_prove() {
        let mut lemma =
            HomologyLemma::new("exact_seq".to_string(), LeanType::prop(), "exactness".to_string());
        lemma.prove(ProofTerm::Trivial);
        assert!(lemma.is_proven());
    }

    #[test]
    fn test_homology_library_add() {
        let mut lib = HomologyLemmasLibrary::new();
        let lemma =
            HomologyLemma::new("test".to_string(), LeanType::prop(), "differential".to_string());
        lib.add_lemma(lemma);
        assert!(lib.get_lemma("test").is_some());
    }

    #[test]
    fn test_homology_library_types() {
        let mut lib = HomologyLemmasLibrary::new();
        let l1 = HomologyLemma::new(
            "exact1".to_string(),
            LeanType::prop(),
            "exactness".to_string(),
        );
        let l2 = HomologyLemma::new(
            "diff1".to_string(),
            LeanType::prop(),
            "differential".to_string(),
        );
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        assert_eq!(lib.exactness_lemmas().len(), 1);
        assert_eq!(lib.differential_lemmas().len(), 1);
    }

    #[test]
    fn test_homology_library_count() {
        let mut lib = HomologyLemmasLibrary::new();
        let mut l1 = HomologyLemma::new(
            "lem1".to_string(),
            LeanType::prop(),
            "exactness".to_string(),
        );
        let l2 = HomologyLemma::new(
            "lem2".to_string(),
            LeanType::prop(),
            "differential".to_string(),
        );
        l1.prove(ProofTerm::Trivial);
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        assert_eq!(lib.count_proven(), 1);
        assert_eq!(lib.count_open(), 1);
    }

    #[test]
    fn test_homology_library_default() {
        let lib = HomologyLemmasLibrary::default();
        assert_eq!(lib.count_proven(), 0);
    }
}
