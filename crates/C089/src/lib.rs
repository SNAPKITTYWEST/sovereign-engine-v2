//! runtime_invariant_checking
//!
//! Re-checks the gap tensor invariants (Tier 0) over the recorded runtime
//! history of any binding, and compares the result with the report stored
//! at capture time. A mismatch means the recording and the static checker
//! disagree — which the cross-layer lemma
//! `runtime_invariants_match_static` rules out.

#![warn(missing_docs)]

use gap_tensor_invariants::check_tensor;
pub use multiplicity_state_binding::ArenaBinding;
pub use prime_state_binding::PrimeStateBinding;
pub use recursion_runtime_binding::RecursionBinding;
use runtime_state_snapshot::SnapshotStore;
pub use runtime_state_snapshot::{GapTensor, Violation};
pub use tensor_runtime_binding::TensorBinding;

/// Invariant results for one recorded history.
#[derive(Debug, Clone, PartialEq)]
pub struct StoreReport {
    /// Name of the history.
    pub source: String,
    /// Snapshots checked.
    pub steps_checked: usize,
    /// Violations found, with their steps.
    pub violations: Vec<(u64, Violation)>,
    /// Steps whose stored report differs from the recomputed one.
    pub disagreements: Vec<u64>,
}

impl StoreReport {
    /// No violations and no disagreements.
    pub fn is_clean(&self) -> bool {
        self.violations.is_empty() && self.disagreements.is_empty()
    }
}

/// Invariant results for several histories.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct RuntimeInvariantReport {
    /// Per-history results.
    pub stores: Vec<StoreReport>,
}

impl RuntimeInvariantReport {
    /// Total violations across all histories.
    pub fn total_violations(&self) -> usize {
        self.stores.iter().map(|s| s.violations.len()).sum()
    }

    /// Did every stored report agree with its recomputation?
    pub fn stored_reports_agree(&self) -> bool {
        self.stores.iter().all(|s| s.disagreements.is_empty())
    }
}

/// Runtime invariant checker.
pub struct RuntimeInvariantChecker;

impl RuntimeInvariantChecker {
    /// Check a single tensor (same rules as the static checker).
    pub fn check_state(tensor: &GapTensor) -> Vec<Violation> {
        check_tensor(tensor).violations
    }

    /// Re-check every snapshot of a history.
    pub fn check_store(source: &str, store: &SnapshotStore) -> StoreReport {
        let mut report = StoreReport {
            source: source.to_string(),
            steps_checked: store.len(),
            violations: Vec::new(),
            disagreements: Vec::new(),
        };
        for s in store.snapshots() {
            let recomputed = check_tensor(&s.tensor);
            if recomputed != s.invariants {
                report.disagreements.push(s.step);
            }
            report
                .violations
                .extend(recomputed.violations.into_iter().map(|v| (s.step, v)));
        }
        report
    }

    /// Re-check several named histories.
    pub fn check_all(stores: &[(&str, &SnapshotStore)]) -> RuntimeInvariantReport {
        RuntimeInvariantReport {
            stores: stores
                .iter()
                .map(|(name, store)| Self::check_store(name, store))
                .collect(),
        }
    }

    /// Histories of the four standard bindings.
    pub fn check_bindings(
        tensor: &TensorBinding,
        primes: &PrimeStateBinding,
        arena: &ArenaBinding,
        recursion: &RecursionBinding,
    ) -> RuntimeInvariantReport {
        Self::check_all(&[
            ("tensor", tensor.store()),
            ("primes", primes.store()),
            ("arena", arena.store()),
            ("recursion", recursion.store()),
        ])
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use runtime_state_snapshot::{vector_state, GapTensorNode};

    #[test]
    fn clean_and_dirty_histories() {
        let mut store = SnapshotStore::new();
        store.capture("ok", &vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::new(3, 1, 1.0)]));
        store.capture("bad", &vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::new(13, 1, 1.0)]));
        let report = RuntimeInvariantChecker::check_store("s", &store);
        assert_eq!(report.steps_checked, 2);
        assert_eq!(report.violations.len(), 1);
        assert_eq!(report.violations[0].0, 1);
        assert!(report.disagreements.is_empty());
        assert!(!report.is_clean());
    }

    #[test]
    fn stored_reports_are_compared() {
        let mut store = SnapshotStore::new();
        store.capture("x", &vector_state(vec![GapTensorNode::new(4, 1, 1.0)]));
        store.snapshots_mut_for_testing()[0].invariants.violations.clear();
        let report = RuntimeInvariantChecker::check_all(&[("s", &store)]);
        assert!(!report.stored_reports_agree());
        assert_eq!(report.total_violations(), 1);
    }

    #[test]
    fn prime_runs_leave_the_candidate_set() {
        let primes = PrimeStateBinding::run("p", 30).unwrap();
        let report = RuntimeInvariantChecker::check_store("p", primes.store());
        assert!(report.violations.iter().any(|(_, v)| matches!(v, Violation::NonCandidatePrime { prime: 17, .. })));
    }
}
