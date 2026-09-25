//! memory_lemmas_library
//!
//! Proves theorems about memory arena properties: allocation correctness and deallocation safety.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};

/// Status of a memory lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MemoryLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Could not be proven
    Failed,
}

/// A memory safety lemma
#[derive(Clone, Debug)]
pub struct MemoryLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: MemoryLemmaStatus,
    /// Optional proof
    pub proof: Option<ProofTerm>,
    /// Category: allocation, deallocation, or general
    pub category: String,
}

impl MemoryLemma {
    /// Create a new memory lemma
    pub fn new(name: String, statement: LeanType, category: String) -> Self {
        Self {
            name,
            statement,
            status: MemoryLemmaStatus::Open,
            proof: None,
            category,
        }
    }

    /// Prove the lemma
    pub fn prove(&mut self, proof: ProofTerm) {
        if proof.is_complete() {
            self.proof = Some(proof);
            self.status = MemoryLemmaStatus::Closed;
        }
    }

    /// Check if proven
    pub fn is_proven(&self) -> bool {
        self.status == MemoryLemmaStatus::Closed
    }
}

/// Library of memory lemmas
#[derive(Clone, Debug)]
pub struct MemoryLemmasLibrary {
    /// All lemmas
    pub lemmas: BTreeMap<String, MemoryLemma>,
    /// Type context
    pub context: TypeContext,
}

impl MemoryLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: MemoryLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&MemoryLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut MemoryLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == MemoryLemmaStatus::Closed)
            .count()
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == MemoryLemmaStatus::Open)
            .count()
    }

    /// Get lemmas by category
    pub fn lemmas_by_category(&self, category: &str) -> Vec<&MemoryLemma> {
        self.lemmas
            .values()
            .filter(|l| l.category == category)
            .collect()
    }

    /// Get all allocation lemmas
    pub fn allocation_lemmas(&self) -> Vec<&MemoryLemma> {
        self.lemmas_by_category("allocation")
    }

    /// Get all deallocation lemmas
    pub fn deallocation_lemmas(&self) -> Vec<&MemoryLemma> {
        self.lemmas_by_category("deallocation")
    }
}

impl Default for MemoryLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_memory_lemma_creation() {
        let lemma = MemoryLemma::new(
            "alloc_safety".to_string(),
            LeanType::prop(),
            "allocation".to_string(),
        );
        assert_eq!(lemma.status, MemoryLemmaStatus::Open);
        assert_eq!(lemma.category, "allocation");
    }

    #[test]
    fn test_memory_lemma_prove() {
        let mut lemma = MemoryLemma::new(
            "dealloc_safety".to_string(),
            LeanType::prop(),
            "deallocation".to_string(),
        );
        lemma.prove(ProofTerm::Trivial);
        assert!(lemma.is_proven());
    }

    #[test]
    fn test_memory_library_add() {
        let mut lib = MemoryLemmasLibrary::new();
        let lemma = MemoryLemma::new(
            "test".to_string(),
            LeanType::prop(),
            "allocation".to_string(),
        );
        lib.add_lemma(lemma);
        assert!(lib.get_lemma("test").is_some());
    }

    #[test]
    fn test_memory_library_categories() {
        let mut lib = MemoryLemmasLibrary::new();
        let l1 = MemoryLemma::new(
            "alloc1".to_string(),
            LeanType::prop(),
            "allocation".to_string(),
        );
        let l2 = MemoryLemma::new(
            "dealloc1".to_string(),
            LeanType::prop(),
            "deallocation".to_string(),
        );
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        assert_eq!(lib.allocation_lemmas().len(), 1);
        assert_eq!(lib.deallocation_lemmas().len(), 1);
    }

    #[test]
    fn test_memory_library_count() {
        let mut lib = MemoryLemmasLibrary::new();
        let mut l1 = MemoryLemma::new(
            "lem1".to_string(),
            LeanType::prop(),
            "allocation".to_string(),
        );
        let l2 = MemoryLemma::new(
            "lem2".to_string(),
            LeanType::prop(),
            "deallocation".to_string(),
        );
        l1.prove(ProofTerm::Trivial);
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        assert_eq!(lib.count_proven(), 1);
        assert_eq!(lib.count_open(), 1);
    }

    #[test]
    fn test_memory_library_default() {
        let lib = MemoryLemmasLibrary::default();
        assert_eq!(lib.count_proven(), 0);
        assert_eq!(lib.count_open(), 0);
    }
}
