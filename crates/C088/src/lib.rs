//! rollback_mechanism
//!
//! Transactional updates of a runtime tensor. An update is applied to a
//! copy, checked with the runtime invariant checker, and committed only if
//! the new state is valid; otherwise the tensor keeps its last valid state
//! and the rollback is recorded in the (append-only) history, so the trace
//! shows every attempt and its outcome.

#![warn(missing_docs)]

use runtime_invariant_checking::{RuntimeInvariantChecker, Violation};
use runtime_state_snapshot::{GapTensor, SnapshotStore};

/// Why an update was rolled back.
#[derive(Debug, Clone, PartialEq)]
pub struct RollbackReport {
    /// Label of the rejected update.
    pub label: String,
    /// Violations the update would have introduced.
    pub violations: Vec<Violation>,
}

/// A tensor updated only through checked transactions.
#[derive(Debug, Clone)]
pub struct TransactionalTensor {
    tensor: GapTensor,
    store: SnapshotStore,
    commits: usize,
    rollbacks: Vec<RollbackReport>,
}

impl TransactionalTensor {
    /// Start from `tensor`. Refused if it already violates an invariant.
    pub fn new(tensor: GapTensor) -> Result<Self, Vec<Violation>> {
        let violations = RuntimeInvariantChecker::check_state(&tensor);
        if !violations.is_empty() {
            return Err(violations);
        }
        let mut store = SnapshotStore::new();
        store.capture("initial", &tensor);
        Ok(Self {
            tensor,
            store,
            commits: 0,
            rollbacks: Vec::new(),
        })
    }

    /// Apply `f` as a transaction: commit if the result is valid, otherwise
    /// keep the current state and record a rollback.
    pub fn apply(&mut self, label: &str, f: impl FnOnce(&mut GapTensor)) -> Result<(), RollbackReport> {
        let mut candidate = self.tensor.clone();
        f(&mut candidate);
        let violations = RuntimeInvariantChecker::check_state(&candidate);
        if violations.is_empty() {
            self.tensor = candidate;
            self.commits += 1;
            self.store.capture(format!("commit: {label}"), &self.tensor);
            return Ok(());
        }
        let report = RollbackReport {
            label: label.to_string(),
            violations,
        };
        self.rollbacks.push(report.clone());
        self.store.capture(format!("rollback: {label}"), &self.tensor);
        Err(report)
    }

    /// Current (always valid) state.
    pub fn tensor(&self) -> &GapTensor {
        &self.tensor
    }

    /// Full history, including rollbacks.
    pub fn store(&self) -> &SnapshotStore {
        &self.store
    }

    /// Committed updates.
    pub fn commits(&self) -> usize {
        self.commits
    }

    /// Rolled-back updates.
    pub fn rollbacks(&self) -> &[RollbackReport] {
        &self.rollbacks
    }

    /// Every recorded state is valid (rollbacks record the retained state).
    pub fn history_valid(&self) -> bool {
        self.store.snapshots().iter().all(|s| s.is_valid())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use runtime_state_snapshot::{vector_state, GapTensorNode};

    fn start() -> TransactionalTensor {
        TransactionalTensor::new(vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::new(3, 1, 1.0)])).unwrap()
    }

    #[test]
    fn valid_updates_commit() {
        let mut t = start();
        t.apply("bump", |x| x.nodes_mut()[1] = GapTensorNode::new(5, 2, 0.5)).unwrap();
        assert_eq!(t.commits(), 1);
        assert_eq!(t.tensor().nodes()[1].prime_val, 5);
        assert!(t.history_valid());
    }

    #[test]
    fn invalid_updates_roll_back() {
        let mut t = start();
        let err = t.apply("jump", |x| x.nodes_mut()[1] = GapTensorNode::new(13, 1, 1.0)).unwrap_err();
        assert!(matches!(err.violations[0], Violation::Dissonance { gap: 11, .. }));
        assert_eq!(t.tensor().nodes()[1].prime_val, 3);
        let err = t.apply("negative", |x| x.nodes_mut()[0].spectral_weight = -1.0).unwrap_err();
        assert!(matches!(err.violations[0], Violation::InvalidWeight { .. }));
        assert_eq!(t.rollbacks().len(), 2);
        assert_eq!(t.store().len(), 3);
        assert!(t.history_valid());
        assert!(t.store().verify().is_ok());
    }

    #[test]
    fn invalid_start_is_refused() {
        assert!(TransactionalTensor::new(vector_state(vec![GapTensorNode::new(4, 1, 1.0)])).is_err());
    }
}
