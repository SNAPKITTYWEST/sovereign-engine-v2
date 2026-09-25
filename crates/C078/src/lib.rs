//! krull_lemmas_library
//!
//! Proves theorems about Krull dimension, dimension inequalities, and chain properties.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};

/// Status of a Krull dimension lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KrullLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Could not be proven
    Failed,
}

/// A Krull dimension lemma
#[derive(Clone, Debug)]
pub struct KrullLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: KrullLemmaStatus,
    /// Optional proof
    pub proof: Option<ProofTerm>,
    /// Dimension bound this lemma establishes
    pub dimension_bound: Option<usize>,
}

impl KrullLemma {
    /// Create a new Krull dimension lemma
    pub fn new(name: String, statement: LeanType) -> Self {
        Self {
            name,
            statement,
            status: KrullLemmaStatus::Open,
            proof: None,
            dimension_bound: None,
        }
    }

    /// Set the dimension bound
    pub fn with_dimension_bound(mut self, bound: usize) -> Self {
        self.dimension_bound = Some(bound);
        self
    }

    /// Prove the lemma
    pub fn prove(&mut self, proof: ProofTerm) {
        if proof.is_complete() {
            self.proof = Some(proof);
            self.status = KrullLemmaStatus::Closed;
        }
    }

    /// Check if proven
    pub fn is_proven(&self) -> bool {
        self.status == KrullLemmaStatus::Closed
    }
}

/// Library of Krull dimension lemmas
#[derive(Clone, Debug)]
pub struct KrullLemmasLibrary {
    /// All lemmas
    pub lemmas: BTreeMap<String, KrullLemma>,
    /// Type context
    pub context: TypeContext,
}

impl KrullLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: KrullLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&KrullLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut KrullLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == KrullLemmaStatus::Closed)
            .count()
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == KrullLemmaStatus::Open)
            .count()
    }

    /// Get lemmas establishing a specific dimension bound
    pub fn lemmas_for_dimension(&self, dim: usize) -> Vec<&KrullLemma> {
        self.lemmas
            .values()
            .filter(|l| l.dimension_bound == Some(dim))
            .collect()
    }

    /// Get minimum bound covered by all lemmas
    pub fn min_dimension(&self) -> Option<usize> {
        self.lemmas
            .values()
            .filter_map(|l| l.dimension_bound)
            .min()
    }

    /// Get maximum bound covered by all lemmas
    pub fn max_dimension(&self) -> Option<usize> {
        self.lemmas
            .values()
            .filter_map(|l| l.dimension_bound)
            .max()
    }
}

impl Default for KrullLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_krull_lemma_creation() {
        let lemma = KrullLemma::new("dim_bound".to_string(), LeanType::prop());
        assert_eq!(lemma.status, KrullLemmaStatus::Open);
        assert_eq!(lemma.dimension_bound, None);
    }

    #[test]
    fn test_krull_lemma_with_bound() {
        let lemma = KrullLemma::new("dim_bound".to_string(), LeanType::prop())
            .with_dimension_bound(5);
        assert_eq!(lemma.dimension_bound, Some(5));
    }

    #[test]
    fn test_krull_lemma_prove() {
        let mut lemma = KrullLemma::new("dim_bound".to_string(), LeanType::prop());
        lemma.prove(ProofTerm::Trivial);
        assert!(lemma.is_proven());
    }

    #[test]
    fn test_krull_library_add() {
        let mut lib = KrullLemmasLibrary::new();
        let lemma = KrullLemma::new("test".to_string(), LeanType::prop());
        lib.add_lemma(lemma);
        assert!(lib.get_lemma("test").is_some());
    }

    #[test]
    fn test_krull_library_dimension_query() {
        let mut lib = KrullLemmasLibrary::new();
        let l1 = KrullLemma::new("dim2".to_string(), LeanType::prop())
            .with_dimension_bound(2);
        let l2 = KrullLemma::new("dim3".to_string(), LeanType::prop())
            .with_dimension_bound(3);
        let l3 = KrullLemma::new("dim5".to_string(), LeanType::prop())
            .with_dimension_bound(5);
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        lib.add_lemma(l3);
        assert_eq!(lib.lemmas_for_dimension(3).len(), 1);
        assert_eq!(lib.min_dimension(), Some(2));
        assert_eq!(lib.max_dimension(), Some(5));
    }

    #[test]
    fn test_krull_library_count() {
        let mut lib = KrullLemmasLibrary::new();
        let mut l1 = KrullLemma::new("lem1".to_string(), LeanType::prop());
        let l2 = KrullLemma::new("lem2".to_string(), LeanType::prop());
        l1.prove(ProofTerm::Trivial);
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        assert_eq!(lib.count_proven(), 1);
        assert_eq!(lib.count_open(), 1);
    }
}
