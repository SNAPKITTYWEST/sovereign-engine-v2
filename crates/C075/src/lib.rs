//! recursion_lemmas_library
//!
//! Proves theorems about recursive solver termination, depth bounds, and recursion properties.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};

/// Status of a recursion lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RecursionLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Could not be proven
    Failed,
}

/// A recursion termination or depth lemma
#[derive(Clone, Debug)]
pub struct RecursionLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: RecursionLemmaStatus,
    /// Optional proof
    pub proof: Option<ProofTerm>,
    /// Maximum depth this lemma applies to
    pub max_depth: Option<usize>,
}

impl RecursionLemma {
    /// Create a new recursion lemma
    pub fn new(name: String, statement: LeanType) -> Self {
        Self {
            name,
            statement,
            status: RecursionLemmaStatus::Open,
            proof: None,
            max_depth: None,
        }
    }

    /// Set the maximum depth
    pub fn with_max_depth(mut self, depth: usize) -> Self {
        self.max_depth = Some(depth);
        self
    }

    /// Prove the lemma
    pub fn prove(&mut self, proof: ProofTerm) {
        if proof.is_complete() {
            self.proof = Some(proof);
            self.status = RecursionLemmaStatus::Closed;
        }
    }

    /// Check if proven
    pub fn is_proven(&self) -> bool {
        self.status == RecursionLemmaStatus::Closed
    }
}

/// Library of recursion lemmas
#[derive(Clone, Debug)]
pub struct RecursionLemmasLibrary {
    /// All lemmas
    pub lemmas: BTreeMap<String, RecursionLemma>,
    /// Type context
    pub context: TypeContext,
}

impl RecursionLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: RecursionLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&RecursionLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut RecursionLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == RecursionLemmaStatus::Closed)
            .count()
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == RecursionLemmaStatus::Open)
            .count()
    }

    /// Get lemmas applicable up to a given depth
    pub fn lemmas_for_depth(&self, depth: usize) -> Vec<&RecursionLemma> {
        self.lemmas
            .values()
            .filter(|l| l.max_depth.map_or(true, |md| md >= depth))
            .collect()
    }

    /// Get maximum depth covered by all lemmas
    pub fn max_covered_depth(&self) -> Option<usize> {
        self.lemmas
            .values()
            .filter_map(|l| l.max_depth)
            .max()
    }
}

impl Default for RecursionLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_recursion_lemma_creation() {
        let lemma = RecursionLemma::new("termination".to_string(), LeanType::prop());
        assert_eq!(lemma.status, RecursionLemmaStatus::Open);
        assert_eq!(lemma.max_depth, None);
    }

    #[test]
    fn test_recursion_lemma_with_depth() {
        let lemma = RecursionLemma::new("termination".to_string(), LeanType::prop())
            .with_max_depth(100);
        assert_eq!(lemma.max_depth, Some(100));
    }

    #[test]
    fn test_recursion_lemma_prove() {
        let mut lemma = RecursionLemma::new("termination".to_string(), LeanType::prop());
        lemma.prove(ProofTerm::Trivial);
        assert!(lemma.is_proven());
    }

    #[test]
    fn test_recursion_library_add() {
        let mut lib = RecursionLemmasLibrary::new();
        let lemma = RecursionLemma::new("test".to_string(), LeanType::prop());
        lib.add_lemma(lemma);
        assert!(lib.get_lemma("test").is_some());
    }

    #[test]
    fn test_recursion_library_depth_query() {
        let mut lib = RecursionLemmasLibrary::new();
        let l1 = RecursionLemma::new("lem1".to_string(), LeanType::prop())
            .with_max_depth(50);
        let l2 = RecursionLemma::new("lem2".to_string(), LeanType::prop())
            .with_max_depth(100);
        let l3 = RecursionLemma::new("lem3".to_string(), LeanType::prop());
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        lib.add_lemma(l3);
        assert_eq!(lib.lemmas_for_depth(60).len(), 2);
        assert_eq!(lib.max_covered_depth(), Some(100));
    }

    #[test]
    fn test_recursion_library_count() {
        let mut lib = RecursionLemmasLibrary::new();
        let mut l1 = RecursionLemma::new("lem1".to_string(), LeanType::prop());
        let l2 = RecursionLemma::new("lem2".to_string(), LeanType::prop());
        l1.prove(ProofTerm::Trivial);
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        assert_eq!(lib.count_proven(), 1);
        assert_eq!(lib.count_open(), 1);
    }
}
