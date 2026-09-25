//! obligation_management
//!
//! Management framework for proof obligations.

#![warn(missing_docs)]

use std::collections::{BTreeMap, BTreeSet};

pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};

/// Status of a proof obligation
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ObligationStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Could not be proven
    Failed,
}

/// A single proof obligation
#[derive(Clone, Debug)]
pub struct Obligation {
    /// Unique identifier
    pub id: String,
    /// The proposition to prove
    pub proposition: LeanType,
    /// Current status
    pub status: ObligationStatus,
    /// Optional proof term
    pub proof: Option<ProofTerm>,
    /// Dependencies (other obligations that must be proven first)
    pub dependencies: BTreeSet<String>,
}

impl Obligation {
    /// Create a new obligation
    pub fn new(id: String, proposition: LeanType) -> Self {
        Self {
            id,
            proposition,
            status: ObligationStatus::Open,
            proof: None,
            dependencies: BTreeSet::new(),
        }
    }

    /// Add a dependency
    pub fn add_dependency(&mut self, dep_id: String) {
        self.dependencies.insert(dep_id);
    }

    /// Check if all dependencies are satisfied (closed)
    pub fn dependencies_satisfied(&self, obligations: &[Obligation]) -> bool {
        self.dependencies.iter().all(|dep_id| {
            obligations
                .iter()
                .find(|o| &o.id == dep_id)
                .map(|o| o.status == ObligationStatus::Closed)
                .unwrap_or(false)
        })
    }

    /// Mark as proven with a proof term
    pub fn prove(&mut self, proof: ProofTerm) {
        if proof.is_complete() {
            self.proof = Some(proof);
            self.status = ObligationStatus::Closed;
        }
    }
}

/// Manager for a collection of proof obligations
#[derive(Clone, Debug)]
pub struct ObligationManager {
    /// All obligations
    pub obligations: BTreeMap<String, Obligation>,
    /// Type checking context
    pub context: TypeContext,
}

impl ObligationManager {
    /// Create a new obligation manager
    pub fn new() -> Self {
        Self {
            obligations: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// Add an obligation
    pub fn add_obligation(&mut self, obligation: Obligation) {
        self.obligations.insert(obligation.id.clone(), obligation);
    }

    /// Get an obligation by ID
    pub fn get_obligation(&self, id: &str) -> Option<&Obligation> {
        self.obligations.get(id)
    }

    /// Get mutable obligation
    pub fn get_obligation_mut(&mut self, id: &str) -> Option<&mut Obligation> {
        self.obligations.get_mut(id)
    }

    /// Count open obligations
    pub fn count_open(&self) -> usize {
        self.obligations
            .values()
            .filter(|o| o.status == ObligationStatus::Open)
            .count()
    }

    /// Count closed obligations
    pub fn count_closed(&self) -> usize {
        self.obligations
            .values()
            .filter(|o| o.status == ObligationStatus::Closed)
            .count()
    }

    /// Get all obligations in topological order (dependencies first)
    pub fn topological_order(&self) -> Vec<String> {
        let mut ordered = Vec::new();
        let mut visited = BTreeSet::new();

        fn visit(
            id: &str,
            obligations: &BTreeMap<String, Obligation>,
            visited: &mut BTreeSet<String>,
            ordered: &mut Vec<String>,
        ) {
            if visited.contains(id) {
                return;
            }
            visited.insert(id.to_string());

            if let Some(obl) = obligations.get(id) {
                for dep_id in &obl.dependencies {
                    visit(dep_id, obligations, visited, ordered);
                }
            }
            ordered.push(id.to_string());
        }

        for id in self.obligations.keys() {
            visit(id, &self.obligations, &mut visited, &mut ordered);
        }

        ordered
    }
}

impl Default for ObligationManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_obligation_creation() {
        let obl = Obligation::new("test".to_string(), LeanType::prop());
        assert_eq!(obl.status, ObligationStatus::Open);
        assert!(obl.proof.is_none());
    }

    #[test]
    fn test_obligation_prove() {
        let mut obl = Obligation::new("test".to_string(), LeanType::prop());
        obl.prove(ProofTerm::Trivial);
        assert_eq!(obl.status, ObligationStatus::Closed);
        assert!(obl.proof.is_some());
    }

    #[test]
    fn test_obligation_manager_add() {
        let mut mgr = ObligationManager::new();
        let obl = Obligation::new("test".to_string(), LeanType::prop());
        mgr.add_obligation(obl);
        assert!(mgr.get_obligation("test").is_some());
    }

    #[test]
    fn test_obligation_manager_count() {
        let mut mgr = ObligationManager::new();
        let obl = Obligation::new("test".to_string(), LeanType::prop());
        mgr.add_obligation(obl);
        assert_eq!(mgr.count_open(), 1);
        assert_eq!(mgr.count_closed(), 0);
    }

    #[test]
    fn test_obligation_manager_topological_order() {
        let mut mgr = ObligationManager::new();
        let mut obl1 = Obligation::new("first".to_string(), LeanType::prop());
        let mut obl2 = Obligation::new("second".to_string(), LeanType::prop());
        obl2.add_dependency("first".to_string());

        mgr.add_obligation(obl1);
        mgr.add_obligation(obl2);

        let order = mgr.topological_order();
        assert_eq!(order.len(), 2);
        assert_eq!(order[0], "first");
        assert_eq!(order[1], "second");
    }
}
