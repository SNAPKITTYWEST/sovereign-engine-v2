//! obligation_management
//!
//! Proof obligations and their bookkeeping. An obligation is closed only by
//! a proof that type-checks against its proposition
//! (`type_checking_interface`), and — when discharged through the manager —
//! only after every dependency is closed. Dependency cycles and references to
//! unknown obligations are detected, not silently ignored.

#![warn(missing_docs)]

use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

pub use type_checking_interface::{
    DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError,
};

/// Status of a proof obligation
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ObligationStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// A proof attempt was refuted (e.g. a decision procedure found a
    /// counterexample)
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
    /// Proof that closed it, if any
    pub proof: Option<ProofTerm>,
    /// Obligations that must be closed first
    pub dependencies: BTreeSet<String>,
}

impl Obligation {
    /// Create a new open obligation
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

    /// Check if all dependencies are closed
    pub fn dependencies_satisfied(&self, obligations: &[Obligation]) -> bool {
        self.dependencies.iter().all(|dep_id| {
            obligations
                .iter()
                .find(|o| &o.id == dep_id)
                .map(|o| o.status == ObligationStatus::Closed)
                .unwrap_or(false)
        })
    }

    /// Close with a self-contained proof (checked in an empty context: only
    /// `Trivial` for `True` and decided statements qualify). Use
    /// [`ObligationManager::discharge`] for proofs that cite theorems.
    pub fn prove(&mut self, proof: ProofTerm) -> Result<(), TypeError> {
        TypeContext::new().check(&proof, &self.proposition)?;
        self.proof = Some(proof);
        self.status = ObligationStatus::Closed;
        Ok(())
    }

    /// Evidence grade of the closing proof, if closed.
    pub fn evidence(&self) -> Option<Evidence> {
        match (&self.proof, self.status) {
            (Some(p), ObligationStatus::Closed) => Some(p.evidence()),
            _ => None,
        }
    }
}

/// Why an obligation could not be discharged.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DischargeError {
    /// No obligation with this id.
    UnknownObligation(String),
    /// Some dependencies are not closed.
    OpenDependencies(Vec<String>),
    /// The proof does not prove the proposition.
    Rejected(TypeError),
}

impl fmt::Display for DischargeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnknownObligation(id) => write!(f, "unknown obligation `{id}`"),
            Self::OpenDependencies(deps) => write!(f, "open dependencies: {}", deps.join(", ")),
            Self::Rejected(e) => write!(f, "proof rejected: {e}"),
        }
    }
}

impl std::error::Error for DischargeError {}

/// Manager for a collection of proof obligations
#[derive(Clone, Debug)]
pub struct ObligationManager {
    /// All obligations
    pub obligations: BTreeMap<String, Obligation>,
    /// Theorems and axioms available to proofs
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

    /// Close obligation `id` with `proof`, checked in this manager's context.
    /// Requires every dependency to be closed. A closed obligation's
    /// proposition becomes available to later proofs as theorem `id`.
    pub fn discharge(&mut self, id: &str, proof: ProofTerm) -> Result<(), DischargeError> {
        let obligation = self
            .obligations
            .get(id)
            .ok_or_else(|| DischargeError::UnknownObligation(id.to_string()))?;
        let open: Vec<String> = obligation
            .dependencies
            .iter()
            .filter(|dep| {
                self.obligations
                    .get(*dep)
                    .map_or(true, |o| o.status != ObligationStatus::Closed)
            })
            .cloned()
            .collect();
        if !open.is_empty() {
            return Err(DischargeError::OpenDependencies(open));
        }
        self.context
            .check(&proof, &obligation.proposition)
            .map_err(DischargeError::Rejected)?;
        let proposition = obligation.proposition.clone();
        let obligation = self.obligations.get_mut(id).expect("checked above");
        obligation.proof = Some(proof);
        obligation.status = ObligationStatus::Closed;
        self.context.add_theorem(id.to_string(), proposition);
        Ok(())
    }

    /// Mark obligation `id` as refuted.
    pub fn mark_failed(&mut self, id: &str) -> Result<(), DischargeError> {
        let obligation = self
            .obligations
            .get_mut(id)
            .ok_or_else(|| DischargeError::UnknownObligation(id.to_string()))?;
        obligation.status = ObligationStatus::Failed;
        obligation.proof = None;
        Ok(())
    }

    /// Count open obligations
    pub fn count_open(&self) -> usize {
        self.count_status(ObligationStatus::Open)
    }

    /// Count closed obligations
    pub fn count_closed(&self) -> usize {
        self.count_status(ObligationStatus::Closed)
    }

    /// Count obligations with a given status
    pub fn count_status(&self, status: ObligationStatus) -> usize {
        self.obligations.values().filter(|o| o.status == status).count()
    }

    /// Closed obligations grouped by the evidence grade of their proofs.
    pub fn evidence_counts(&self) -> BTreeMap<Evidence, usize> {
        let mut counts = BTreeMap::new();
        for evidence in self.obligations.values().filter_map(Obligation::evidence) {
            *counts.entry(evidence).or_insert(0) += 1;
        }
        counts
    }

    /// Dependencies that name no obligation, as `(obligation, missing id)`.
    pub fn missing_dependencies(&self) -> Vec<(String, String)> {
        self.obligations
            .values()
            .flat_map(|o| {
                o.dependencies
                    .iter()
                    .filter(|d| !self.obligations.contains_key(*d))
                    .map(move |d| (o.id.clone(), d.clone()))
            })
            .collect()
    }

    /// A dependency cycle, if any, as the ids along it (first id repeated at
    /// the end).
    pub fn find_cycle(&self) -> Option<Vec<String>> {
        #[derive(Clone, Copy, PartialEq)]
        enum Mark {
            Visiting,
            Done,
        }
        fn visit(
            id: &str,
            obligations: &BTreeMap<String, Obligation>,
            marks: &mut BTreeMap<String, Mark>,
            path: &mut Vec<String>,
        ) -> Option<Vec<String>> {
            match marks.get(id) {
                Some(Mark::Done) => return None,
                Some(Mark::Visiting) => {
                    let start = path.iter().position(|p| p == id).unwrap_or(0);
                    let mut cycle = path[start..].to_vec();
                    cycle.push(id.to_string());
                    return Some(cycle);
                }
                None => {}
            }
            marks.insert(id.to_string(), Mark::Visiting);
            path.push(id.to_string());
            if let Some(o) = obligations.get(id) {
                for dep in &o.dependencies {
                    if let Some(cycle) = visit(dep, obligations, marks, path) {
                        return Some(cycle);
                    }
                }
            }
            path.pop();
            marks.insert(id.to_string(), Mark::Done);
            None
        }
        let mut marks = BTreeMap::new();
        for id in self.obligations.keys() {
            let mut path = Vec::new();
            if let Some(cycle) = visit(id, &self.obligations, &mut marks, &mut path) {
                return Some(cycle);
            }
        }
        None
    }

    /// Obligations with dependencies first, or the cycle that prevents such
    /// an order.
    pub fn try_topological_order(&self) -> Result<Vec<String>, Vec<String>> {
        if let Some(cycle) = self.find_cycle() {
            return Err(cycle);
        }
        Ok(self.topological_order())
    }

    /// Obligations with dependencies first. Edges that close a cycle are
    /// ignored; use [`Self::try_topological_order`] to detect cycles.
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
                ordered.push(id.to_string());
            }
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

    fn atom(s: &str) -> LeanType {
        LeanType::atom(s)
    }

    #[test]
    fn test_obligation_creation() {
        let obl = Obligation::new("test".to_string(), LeanType::prop());
        assert_eq!(obl.status, ObligationStatus::Open);
        assert!(obl.proof.is_none());
    }

    #[test]
    fn prove_requires_a_checking_proof() {
        let mut truth = Obligation::new("t".into(), LeanType::truth());
        assert!(truth.prove(ProofTerm::Trivial).is_ok());
        assert_eq!(truth.status, ObligationStatus::Closed);
        assert_eq!(truth.evidence(), Some(Evidence::Constructive));

        let mut claim = Obligation::new("c".into(), atom("P"));
        assert!(claim.prove(ProofTerm::Trivial).is_err());
        assert!(claim.prove(ProofTerm::axiom("undeclared")).is_err());
        assert_eq!(claim.status, ObligationStatus::Open);
    }

    #[test]
    fn discharge_checks_dependencies_and_context() {
        let mut mgr = ObligationManager::new();
        mgr.add_obligation(Obligation::new("p".into(), atom("P")));
        let mut q = Obligation::new("q".into(), atom("Q"));
        q.add_dependency("p".into());
        mgr.add_obligation(q);
        mgr.context.add_axiom("p_implies_q".into(), LeanType::arrow(atom("P"), atom("Q")));
        mgr.context.add_axiom("p_ax".into(), atom("P"));

        let q_proof = ProofTerm::app(ProofTerm::axiom("p_implies_q"), ProofTerm::reference("p"));
        assert_eq!(
            mgr.discharge("q", q_proof.clone()),
            Err(DischargeError::OpenDependencies(vec!["p".into()]))
        );
        assert!(matches!(mgr.discharge("p", ProofTerm::Trivial), Err(DischargeError::Rejected(_))));
        mgr.discharge("p", ProofTerm::axiom("p_ax")).unwrap();
        mgr.discharge("q", q_proof).unwrap();
        assert_eq!(mgr.count_closed(), 2);
        assert_eq!(mgr.evidence_counts().get(&Evidence::Assumed), Some(&2));
        assert!(matches!(mgr.discharge("zzz", ProofTerm::Trivial), Err(DischargeError::UnknownObligation(_))));
    }

    #[test]
    fn test_obligation_manager_count() {
        let mut mgr = ObligationManager::new();
        mgr.add_obligation(Obligation::new("test".to_string(), LeanType::prop()));
        assert_eq!(mgr.count_open(), 1);
        assert_eq!(mgr.count_closed(), 0);
        mgr.mark_failed("test").unwrap();
        assert_eq!(mgr.count_status(ObligationStatus::Failed), 1);
    }

    #[test]
    fn test_obligation_manager_topological_order() {
        let mut mgr = ObligationManager::new();
        let obl1 = Obligation::new("first".to_string(), LeanType::prop());
        let mut obl2 = Obligation::new("second".to_string(), LeanType::prop());
        obl2.add_dependency("first".to_string());
        mgr.add_obligation(obl1);
        mgr.add_obligation(obl2);
        assert_eq!(mgr.try_topological_order(), Ok(vec!["first".to_string(), "second".to_string()]));
    }

    #[test]
    fn cycles_and_missing_dependencies_are_reported() {
        let mut mgr = ObligationManager::new();
        let mut a = Obligation::new("a".into(), atom("A"));
        let mut b = Obligation::new("b".into(), atom("B"));
        a.add_dependency("b".into());
        b.add_dependency("a".into());
        b.add_dependency("ghost".into());
        mgr.add_obligation(a);
        mgr.add_obligation(b);
        let cycle = mgr.find_cycle().unwrap();
        assert_eq!(cycle.first(), cycle.last());
        assert!(mgr.try_topological_order().is_err());
        assert_eq!(mgr.missing_dependencies(), vec![("b".to_string(), "ghost".to_string())]);
        assert_eq!(mgr.topological_order().len(), 2);
    }
}
