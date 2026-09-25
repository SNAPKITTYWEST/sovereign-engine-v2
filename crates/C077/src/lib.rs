//! tor_resolution_lemmas_library
//!
//! Proves theorems about Tor functors, resolutions, universal properties, and functoriality.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};

/// Status of a Tor lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TorLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Could not be proven
    Failed,
}

/// A Tor functor or resolution lemma
#[derive(Clone, Debug)]
pub struct TorLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: TorLemmaStatus,
    /// Optional proof
    pub proof: Option<ProofTerm>,
    /// Tor degree (i for Tor_i)
    pub tor_degree: Option<usize>,
}

impl TorLemma {
    /// Create a new Tor lemma
    pub fn new(name: String, statement: LeanType) -> Self {
        Self {
            name,
            statement,
            status: TorLemmaStatus::Open,
            proof: None,
            tor_degree: None,
        }
    }

    /// Set the Tor degree
    pub fn with_tor_degree(mut self, degree: usize) -> Self {
        self.tor_degree = Some(degree);
        self
    }

    /// Prove the lemma
    pub fn prove(&mut self, proof: ProofTerm) {
        if proof.is_complete() {
            self.proof = Some(proof);
            self.status = TorLemmaStatus::Closed;
        }
    }

    /// Check if proven
    pub fn is_proven(&self) -> bool {
        self.status == TorLemmaStatus::Closed
    }
}

/// Library of Tor lemmas
#[derive(Clone, Debug)]
pub struct TorLemmasLibrary {
    /// All lemmas
    pub lemmas: BTreeMap<String, TorLemma>,
    /// Type context
    pub context: TypeContext,
}

impl TorLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: TorLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&TorLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut TorLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == TorLemmaStatus::Closed)
            .count()
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.lemmas
            .values()
            .filter(|l| l.status == TorLemmaStatus::Open)
            .count()
    }

    /// Get lemmas for a specific Tor degree
    pub fn lemmas_for_degree(&self, degree: usize) -> Vec<&TorLemma> {
        self.lemmas
            .values()
            .filter(|l| l.tor_degree == Some(degree))
            .collect()
    }

    /// Get maximum Tor degree covered
    pub fn max_degree(&self) -> Option<usize> {
        self.lemmas
            .values()
            .filter_map(|l| l.tor_degree)
            .max()
    }
}

impl Default for TorLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tor_lemma_creation() {
        let lemma = TorLemma::new("tor_zero".to_string(), LeanType::prop());
        assert_eq!(lemma.status, TorLemmaStatus::Open);
        assert_eq!(lemma.tor_degree, None);
    }

    #[test]
    fn test_tor_lemma_with_degree() {
        let lemma = TorLemma::new("tor_one".to_string(), LeanType::prop())
            .with_tor_degree(1);
        assert_eq!(lemma.tor_degree, Some(1));
    }

    #[test]
    fn test_tor_lemma_prove() {
        let mut lemma = TorLemma::new("tor_zero".to_string(), LeanType::prop());
        lemma.prove(ProofTerm::Trivial);
        assert!(lemma.is_proven());
    }

    #[test]
    fn test_tor_library_add() {
        let mut lib = TorLemmasLibrary::new();
        let lemma = TorLemma::new("test".to_string(), LeanType::prop());
        lib.add_lemma(lemma);
        assert!(lib.get_lemma("test").is_some());
    }

    #[test]
    fn test_tor_library_degree_query() {
        let mut lib = TorLemmasLibrary::new();
        let l1 = TorLemma::new("tor0_lem1".to_string(), LeanType::prop())
            .with_tor_degree(0);
        let l2 = TorLemma::new("tor1_lem1".to_string(), LeanType::prop())
            .with_tor_degree(1);
        let l3 = TorLemma::new("tor2_lem1".to_string(), LeanType::prop())
            .with_tor_degree(2);
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        lib.add_lemma(l3);
        assert_eq!(lib.lemmas_for_degree(1).len(), 1);
        assert_eq!(lib.max_degree(), Some(2));
    }

    #[test]
    fn test_tor_library_count() {
        let mut lib = TorLemmasLibrary::new();
        let mut l1 = TorLemma::new("lem1".to_string(), LeanType::prop());
        let l2 = TorLemma::new("lem2".to_string(), LeanType::prop());
        l1.prove(ProofTerm::Trivial);
        lib.add_lemma(l1);
        lib.add_lemma(l2);
        assert_eq!(lib.count_proven(), 1);
        assert_eq!(lib.count_open(), 1);
    }
}
