//! certificate_generation
//!
//! Execution certificates. Every claim of every runtime binding becomes a
//! proof obligation (`runtime_{source}_{claim}`). The claim is re-checked
//! against the recorded execution through a decision procedure: success
//! discharges the obligation with a [`DecisionCertificate`] (evidence grade
//! `Computed`), failure marks it failed with the counterexample. The
//! certificate records each source's history digest, binding it to exactly
//! that execution.

#![warn(missing_docs)]

use obligation_management::{DecisionCertificate, LeanType, Obligation, ObligationManager, ProofTerm};
pub use obligation_management::ObligationStatus;
use runtime_state_snapshot::ClaimSource;
use std::collections::BTreeMap;

pub use multiplicity_state_binding::ArenaBinding;
pub use prime_state_binding::PrimeStateBinding;
pub use recursion_runtime_binding::RecursionBinding;
pub use tensor_runtime_binding::TensorBinding;

/// Obligation id for a runtime claim.
pub fn claim_obligation_id(source: &str, claim: &str) -> String {
    format!("runtime_{source}_{claim}")
}

/// Certificate for one recorded execution.
#[derive(Debug, Clone)]
pub struct ExecutionCertificate {
    /// One obligation per claim.
    pub obligations: ObligationManager,
    /// History digest of each source.
    pub digests: BTreeMap<String, u64>,
    /// Counterexamples of failed claims, by obligation id.
    pub failures: BTreeMap<String, String>,
}

impl ExecutionCertificate {
    /// Claims that held.
    pub fn closed(&self) -> usize {
        self.obligations.count_closed()
    }

    /// Claims that failed.
    pub fn failed(&self) -> usize {
        self.obligations.count_status(ObligationStatus::Failed)
    }

    /// Every claim held.
    pub fn all_hold(&self) -> bool {
        self.failed() == 0 && self.closed() == self.obligations.obligations.len()
    }

    /// Did claim `claim` of `source` hold?
    pub fn holds(&self, source: &str, claim: &str) -> Option<bool> {
        self.obligations
            .get_obligation(&claim_obligation_id(source, claim))
            .map(|o| o.status == ObligationStatus::Closed)
    }

    /// One-line summary (used as a trace label).
    pub fn summary(&self) -> String {
        let digests: Vec<String> = self.digests.iter().map(|(s, d)| format!("{s}={d:016x}")).collect();
        format!(
            "certificate closed={} failed={} digests=[{}]",
            self.closed(),
            self.failed(),
            digests.join(",")
        )
    }
}

/// Issue a certificate for the given sources.
pub fn certify(sources: &[&dyn ClaimSource]) -> ExecutionCertificate {
    let mut obligations = ObligationManager::new();
    let mut digests = BTreeMap::new();
    let mut failures = BTreeMap::new();
    for source in sources {
        let name = source.source_name().to_string();
        digests.insert(name.clone(), source.digest());
        for claim in source.claims() {
            let id = claim_obligation_id(&name, &claim.id);
            let statement = LeanType::atom(format!("[{name}] {}", claim.statement));
            obligations.add_obligation(Obligation::new(id.clone(), statement.clone()));
            match DecisionCertificate::run(statement, format!("recheck:{name}.{}", claim.id), || source.recheck(&claim.id)) {
                Ok(cert) => {
                    obligations
                        .discharge(&id, ProofTerm::Decided(cert))
                        .expect("a decided certificate proves its own statement");
                }
                Err(counterexample) => {
                    obligations.mark_failed(&id).expect("obligation just added");
                    failures.insert(id, counterexample);
                }
            }
        }
    }
    ExecutionCertificate {
        obligations,
        digests,
        failures,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use runtime_state_snapshot::{vector_state, GapTensorNode};

    fn clean_tensor() -> TensorBinding {
        let mut t = TensorBinding::new("tensor", vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL]));
        t.set_node(1, GapTensorNode::new(5, 1, 1.0)).unwrap();
        t
    }

    #[test]
    fn clean_run_is_fully_certified() {
        let t = clean_tensor();
        let p = PrimeStateBinding::run("primes", 200).unwrap();
        let mut r = RecursionBinding::new("solver", 4);
        r.push(GapTensorNode::new(3, 1, 1.0)).unwrap();
        let cert = certify(&[&t, &p, &r]);
        assert!(cert.all_hold(), "failures: {:?}", cert.failures);
        assert_eq!(cert.closed(), 4 + 5 + 3);
        assert_eq!(cert.digests.len(), 3);
        assert_eq!(cert.holds("primes", "all_prime"), Some(true));
        assert!(cert.summary().starts_with("certificate closed=12 failed=0"));
    }

    #[test]
    fn failing_claims_are_recorded() {
        let mut t = TensorBinding::new("tensor", vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL]));
        t.set_node(1, GapTensorNode::new(13, 1, 1.0)).unwrap();
        let cert = certify(&[&t]);
        assert!(!cert.all_hold());
        assert_eq!(cert.holds("tensor", "invariants_hold"), Some(false));
        assert_eq!(cert.holds("tensor", "candidate_primes_only"), Some(true));
        assert!(cert.failures[&claim_obligation_id("tensor", "invariants_hold")].contains("Dissonance"));
    }

    #[test]
    fn certificates_are_bound_to_histories() {
        let a = clean_tensor();
        let mut b = clean_tensor();
        b.set_node(0, GapTensorNode::new(3, 1, 1.0)).unwrap();
        assert_ne!(certify(&[&a]).digests["tensor"], certify(&[&b]).digests["tensor"]);
    }
}
