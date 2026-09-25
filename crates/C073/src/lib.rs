//! gap_lemmas_library
//!
//! Proves theorems about prime gaps, gap distributions, and gap relationships.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};

/// Status of a lemma proof
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Could not be proven
    Failed,
}

/// A gap lemma statement and its proof
#[derive(Clone, Debug)]
pub struct GapLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement in Lean
    pub statement: LeanType,
    /// Proof status
    pub status: LemmaStatus,
    /// Optional proof term
    pub proof: Option<ProofTerm>,
    /// Gap size it applies to
    pub gap_size: Option<usize>,
}

impl GapLemma {
    /// Create a new lemma
    pub fn new(name: String, statement: LeanType) -> Self {
        Self {
            name,
            statement,
            status: LemmaStatus::Open,
            proof: None,
            gap_size: None,
        }
    }

    /// Set the gap size this lemma applies to
    pub fn with_gap_size(mut self, size: usize) -> Self {
        self.gap_size = Some(size);
        self
    }

    /// Prove the lemma
    pub fn prove(&mut self, proof: ProofTerm) {
        if proof.is_complete() {
            self.proof = Some(proof);
            self.status = LemmaStatus::Closed;
        }
    }

    /// Check if lemma is proven
    pub fn is_proven(&self) -> bool {
        self.status == LemmaStatus::Closed
    }
}

/// Library of gap lemmas
#[derive(Clone, Debug)]
pub struct GapLemmasLibrary {
    /// All lemmas indexed by name
    pub lemmas: BTreeMap<String, GapLemma>,
    /// Type context for formal statements
    pub context: TypeContext,
}

impl GapLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// Add a lemma to the library
    pub fn add_lemma(&mut self, lemma: GapLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&GapLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut GapLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == LemmaStatus::Closed)
            .count()
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == LemmaStatus::Open)
            .count()
    }

    /// Get all lemmas for a specific gap size
    pub fn lemmas_for_gap(&self, size: usize) -> Vec<&GapLemma> {
        self.lemmas
            .values()
            .filter(|l| l.gap_size == Some(size))
            .collect()
    }
}

impl Default for GapLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gap_lemma_creation() {
        let lemma = GapLemma::new("gap_bounded".to_string(), LeanType::prop());
        assert_eq!(lemma.status, LemmaStatus::Open);
        assert!(lemma.proof.is_none());
        assert_eq!(lemma.gap_size, None);
    }

    #[test]
    fn test_gap_lemma_with_gap_size() {
        let lemma = GapLemma::new("gap_bounded".to_string(), LeanType::prop())
            .with_gap_size(6);
        assert_eq!(lemma.gap_size, Some(6));
    }

    #[test]
    fn test_gap_lemma_prove() {
        let mut lemma = GapLemma::new("gap_bounded".to_string(), LeanType::prop());
        lemma.prove(ProofTerm::Trivial);
        assert_eq!(lemma.status, LemmaStatus::Closed);
        assert!(lemma.is_proven());
    }

    #[test]
    fn test_gap_library_add_and_retrieve() {
        let mut lib = GapLemmasLibrary::new();
        let lemma = GapLemma::new("gap_bounded".to_string(), LeanType::prop())
            .with_gap_size(6);
        lib.add_lemma(lemma);
        assert!(lib.get_lemma("gap_bounded").is_some());
    }

    #[test]
    fn test_gap_library_count() {
        let mut lib = GapLemmasLibrary::new();
        let mut lemma1 = GapLemma::new("gap1".to_string(), LeanType::prop());
        let lemma2 = GapLemma::new("gap2".to_string(), LeanType::prop());
        lemma1.prove(ProofTerm::Trivial);
        lib.add_lemma(lemma1);
        lib.add_lemma(lemma2);
        assert_eq!(lib.count_proven(), 1);
        assert_eq!(lib.count_open(), 1);
    }

    #[test]
    fn test_gap_library_by_gap_size() {
        let mut lib = GapLemmasLibrary::new();
        let l1 = GapLemma::new("gap1".to_string(), LeanType::prop()).with_gap_size(6);
        let l2 = GapLemma::new("gap2".to_string(), LeanType::prop()).with_gap_size(6);
        let l3 = GapLemma::new("gap3".to_string(), LeanType::prop()).with_gap_size(12);
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        lib.add_lemma(l3);
        assert_eq!(lib.lemmas_for_gap(6).len(), 2);
        assert_eq!(lib.lemmas_for_gap(12).len(), 1);
    }
}
