//! tensor_runtime_binding
//!
//! Binds a live gap tensor to the runtime snapshot store: every mutation
//! goes through the binding, is validated at the prime level, and is
//! recorded. The binding's claims (only candidate primes written, invariants
//! held, history intact) are re-checkable against the recording.

#![warn(missing_docs)]

use gap_tensor_primes::{validate_node, PrimeError};
use runtime_state_snapshot::{
    check_tensor, ClaimSource, GapTensor, GapTensorNode, RuntimeClaim, RuntimeSnapshot, SnapshotStore,
};
use std::fmt;

/// Why a write was refused.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BindingError {
    /// The node carries a non-candidate prime.
    Prime(PrimeError),
    /// Flat index outside the tensor.
    OutOfBounds {
        /// Index.
        index: usize,
        /// Tensor length.
        len: usize,
    },
}

impl fmt::Display for BindingError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for BindingError {}

/// A tensor whose every state is recorded.
#[derive(Debug, Clone)]
pub struct TensorBinding {
    name: String,
    tensor: GapTensor,
    store: SnapshotStore,
    rejected: Vec<(usize, GapTensorNode)>,
}

impl TensorBinding {
    /// Bind `tensor`, recording its initial state.
    pub fn new(name: impl Into<String>, tensor: GapTensor) -> Self {
        let mut store = SnapshotStore::new();
        store.capture("initial", &tensor);
        Self {
            name: name.into(),
            tensor,
            store,
            rejected: Vec::new(),
        }
    }

    /// Current state.
    pub fn tensor(&self) -> &GapTensor {
        &self.tensor
    }

    /// Recorded history.
    pub fn store(&self) -> &SnapshotStore {
        &self.store
    }

    /// Writes refused so far.
    pub fn rejected(&self) -> &[(usize, GapTensorNode)] {
        &self.rejected
    }

    /// Write node `index` (flat, row-major). Non-candidate primes and
    /// out-of-range indices are refused and nothing is recorded.
    pub fn set_node(&mut self, index: usize, node: GapTensorNode) -> Result<&RuntimeSnapshot, BindingError> {
        let len = self.tensor.nodes().len();
        if index >= len {
            return Err(BindingError::OutOfBounds { index, len });
        }
        if let Err(e) = validate_node(&node) {
            self.rejected.push((index, node));
            return Err(BindingError::Prime(e));
        }
        self.tensor.nodes_mut()[index] = node;
        Ok(self.store.capture(format!("set[{index}]"), &self.tensor))
    }

    /// Apply a bulk update and record the result. Nodes with non-candidate
    /// primes are still refused: the update is discarded if any appear.
    pub fn apply(
        &mut self,
        label: &str,
        f: impl FnOnce(&mut GapTensor),
    ) -> Result<&RuntimeSnapshot, BindingError> {
        let mut candidate = self.tensor.clone();
        f(&mut candidate);
        if let Some((i, n)) = candidate
            .nodes()
            .iter()
            .enumerate()
            .find(|(_, n)| validate_node(n).is_err())
        {
            self.rejected.push((i, *n));
            return Err(BindingError::Prime(validate_node(n).unwrap_err()));
        }
        self.tensor = candidate;
        Ok(self.store.capture(label.to_string(), &self.tensor))
    }
}

impl ClaimSource for TensorBinding {
    fn source_name(&self) -> &str {
        &self.name
    }

    fn digest(&self) -> u64 {
        self.store.head_digest()
    }

    fn claims(&self) -> Vec<RuntimeClaim> {
        vec![
            RuntimeClaim::new("candidate_primes_only", "every recorded state contains only candidate primes or Nil"),
            RuntimeClaim::new("invariants_hold", "every recorded state satisfies the gap tensor invariants"),
            RuntimeClaim::new("history_intact", "the recorded history verifies against its trace"),
            RuntimeClaim::new("current_state_recorded", "the current tensor equals the latest recorded state"),
        ]
    }

    fn recheck(&self, id: &str) -> Result<u64, String> {
        let snapshots = self.store.snapshots();
        match id {
            "candidate_primes_only" => {
                for s in snapshots {
                    if let Some(n) = s.tensor.nodes().iter().find(|n| validate_node(n).is_err()) {
                        return Err(format!("step {}: prime {}", s.step, n.prime_val));
                    }
                }
                Ok(snapshots.len() as u64)
            }
            "invariants_hold" => {
                for s in snapshots {
                    let report = check_tensor(&s.tensor);
                    if let Some(v) = report.violations.first() {
                        return Err(format!("step {}: {v:?}", s.step));
                    }
                }
                Ok(snapshots.len() as u64)
            }
            "history_intact" => self
                .store
                .verify()
                .map(|_| snapshots.len() as u64)
                .map_err(|e| e.to_string()),
            "current_state_recorded" => match self.store.latest() {
                Some(s) if runtime_state_snapshot::tensors_bitwise_equal(&s.tensor, &self.tensor) => Ok(1),
                _ => Err("current tensor differs from the latest snapshot".into()),
            },
            other => Err(format!("unknown claim `{other}`")),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use runtime_state_snapshot::vector_state;

    fn binding() -> TensorBinding {
        TensorBinding::new("t", vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL]))
    }

    #[test]
    fn writes_are_validated_and_recorded() {
        let mut b = binding();
        b.set_node(1, GapTensorNode::new(5, 2, 0.5)).unwrap();
        assert_eq!(b.store().len(), 2);
        assert!(matches!(b.set_node(0, GapTensorNode::new(9, 1, 1.0)), Err(BindingError::Prime(_))));
        assert!(matches!(b.set_node(7, GapTensorNode::NIL), Err(BindingError::OutOfBounds { .. })));
        assert_eq!(b.store().len(), 2);
        assert_eq!(b.rejected().len(), 1);
        b.apply("scale", |t| t.nodes_mut()[0].multiplicity = 4).unwrap();
        assert!(b.apply("bad", |t| t.nodes_mut()[0].prime_val = 4).is_err());
        assert_eq!(b.tensor().nodes()[0].prime_val, 2);
    }

    #[test]
    fn claims_hold_for_a_clean_run() {
        let mut b = binding();
        b.set_node(1, GapTensorNode::new(3, 1, 1.0)).unwrap();
        for claim in b.claims() {
            assert!(b.recheck(&claim.id).is_ok(), "{} failed: {:?}", claim.id, b.recheck(&claim.id));
        }
        assert!(b.recheck("nonsense").is_err());
    }

    #[test]
    fn invariant_claim_fails_on_dissonance() {
        let mut b = binding();
        b.set_node(1, GapTensorNode::new(13, 1, 1.0)).unwrap();
        let err = b.recheck("invariants_hold").unwrap_err();
        assert!(err.contains("Dissonance"), "{err}");
        assert!(b.recheck("candidate_primes_only").is_ok());
    }
}
