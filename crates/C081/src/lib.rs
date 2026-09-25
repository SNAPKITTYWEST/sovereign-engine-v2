//! runtime_state_snapshot
//!
//! Snapshots of runtime tensor state. Each snapshot stores the tensor and
//! its invariant report, and is also appended to a tamper-evident
//! [`TensorTrace`], so [`SnapshotStore::verify`] can prove the stored history
//! is exactly what was recorded.
//!
//! Also defines the interface every runtime binding implements to report
//! what it guarantees: [`RuntimeClaim`] and [`ClaimSource`]. Claims are
//! re-checked against the recorded execution when certificates are issued.

#![warn(missing_docs)]

pub use gap_tensor_core::{GapTensorNode, CANDIDATE_PRIMES, SIGMA_GAP_MAX};
pub use gap_tensor_invariants::{check_nodes, check_tensor, InvariantReport, Violation};
pub use gap_tensor_trace::{GapTensor, TensorShape, TensorTrace, TraceError};
use std::fmt;

/// True iff the tensors have the same shape and bit-identical nodes.
pub fn tensors_bitwise_equal(a: &GapTensor, b: &GapTensor) -> bool {
    a.shape() == b.shape()
        && a.nodes().iter().zip(b.nodes()).all(|(x, y)| {
            x.prime_val == y.prime_val
                && x.multiplicity == y.multiplicity
                && x.spectral_weight.to_bits() == y.spectral_weight.to_bits()
        })
}

/// A single-node Nil tensor, used where a snapshot has no data.
pub fn empty_state() -> GapTensor {
    GapTensor::nil(TensorShape::vector(1).expect("rank-1 shape of length 1"))
}

/// A vector tensor of `nodes` (a single Nil node if `nodes` is empty).
pub fn vector_state(nodes: Vec<GapTensorNode>) -> GapTensor {
    match TensorShape::vector(nodes.len()) {
        Ok(shape) => GapTensor::from_nodes(shape, nodes).expect("length matches shape"),
        Err(_) => empty_state(),
    }
}

/// One recorded runtime state.
#[derive(Debug, Clone, PartialEq)]
pub struct RuntimeSnapshot {
    /// Position in the store.
    pub step: u64,
    /// Caller-supplied label.
    pub label: String,
    /// The tensor state.
    pub tensor: GapTensor,
    /// Invariant report computed at capture time.
    pub invariants: InvariantReport,
    /// Trace digest of this snapshot.
    pub digest: u64,
}

impl RuntimeSnapshot {
    /// Did the state satisfy every tensor invariant?
    pub fn is_valid(&self) -> bool {
        self.invariants.is_valid()
    }
}

/// Why a snapshot store failed verification.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SnapshotError {
    /// The underlying trace is broken.
    Trace(TraceError),
    /// Snapshot and trace entry counts differ.
    CountMismatch {
        /// Snapshots stored.
        snapshots: usize,
        /// Trace entries.
        trace: usize,
    },
    /// A stored tensor differs from its trace entry.
    StateMismatch {
        /// Step.
        step: u64,
    },
    /// A stored invariant report differs from a recomputation.
    InvariantMismatch {
        /// Step.
        step: u64,
    },
    /// A stored step number or digest is wrong.
    MetadataMismatch {
        /// Step.
        step: u64,
    },
}

impl fmt::Display for SnapshotError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for SnapshotError {}

/// Append-only store of runtime snapshots backed by a chained trace.
#[derive(Debug, Clone, Default)]
pub struct SnapshotStore {
    snapshots: Vec<RuntimeSnapshot>,
    trace: TensorTrace,
}

impl SnapshotStore {
    /// An empty store.
    pub fn new() -> Self {
        Self::default()
    }

    /// Record a state.
    pub fn capture(&mut self, label: impl Into<String>, tensor: &GapTensor) -> &RuntimeSnapshot {
        let label = label.into();
        let digest = self.trace.record(label.clone(), tensor);
        let step = self.snapshots.len() as u64;
        self.snapshots.push(RuntimeSnapshot {
            step,
            label,
            tensor: tensor.clone(),
            invariants: check_tensor(tensor),
            digest,
        });
        self.snapshots.last().expect("just pushed")
    }

    /// All snapshots in order.
    pub fn snapshots(&self) -> &[RuntimeSnapshot] {
        &self.snapshots
    }

    /// Number of snapshots.
    pub fn len(&self) -> usize {
        self.snapshots.len()
    }

    /// Nothing recorded yet?
    pub fn is_empty(&self) -> bool {
        self.snapshots.is_empty()
    }

    /// Snapshot at `step`.
    pub fn get(&self, step: usize) -> Option<&RuntimeSnapshot> {
        self.snapshots.get(step)
    }

    /// Most recent snapshot.
    pub fn latest(&self) -> Option<&RuntimeSnapshot> {
        self.snapshots.last()
    }

    /// Most recent snapshot that satisfies every invariant.
    pub fn last_valid(&self) -> Option<&RuntimeSnapshot> {
        self.snapshots.iter().rev().find(|s| s.is_valid())
    }

    /// First invariant violation, with its step.
    pub fn first_violation(&self) -> Option<(u64, Violation)> {
        self.snapshots
            .iter()
            .find_map(|s| s.invariants.violations.first().map(|v| (s.step, v.clone())))
    }

    /// The backing trace.
    pub fn trace(&self) -> &TensorTrace {
        &self.trace
    }

    /// Digest identifying the whole history.
    pub fn head_digest(&self) -> u64 {
        self.trace.head_digest()
    }

    /// Check the trace chain, and that every stored snapshot matches its
    /// trace entry and a fresh invariant check.
    pub fn verify(&self) -> Result<(), SnapshotError> {
        if self.snapshots.len() != self.trace.len() {
            return Err(SnapshotError::CountMismatch {
                snapshots: self.snapshots.len(),
                trace: self.trace.len(),
            });
        }
        self.trace.verify().map_err(SnapshotError::Trace)?;
        for (i, s) in self.snapshots.iter().enumerate() {
            let entry = &self.trace.entries()[i];
            if s.step != i as u64 || s.digest != entry.digest || s.label != entry.label {
                return Err(SnapshotError::MetadataMismatch { step: s.step });
            }
            let replayed = self.trace.replay(i).map_err(SnapshotError::Trace)?;
            if !tensors_bitwise_equal(&replayed, &s.tensor) {
                return Err(SnapshotError::StateMismatch { step: s.step });
            }
            if check_tensor(&s.tensor) != s.invariants {
                return Err(SnapshotError::InvariantMismatch { step: s.step });
            }
        }
        Ok(())
    }

    /// Mutable access to stored snapshots (for tamper tests).
    #[doc(hidden)]
    pub fn snapshots_mut_for_testing(&mut self) -> &mut Vec<RuntimeSnapshot> {
        &mut self.snapshots
    }
}

/// A property a runtime binding guarantees about its recorded execution.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeClaim {
    /// Identifier, unique within its source.
    pub id: String,
    /// Statement of the property.
    pub statement: String,
}

impl RuntimeClaim {
    /// A claim.
    pub fn new(id: &str, statement: impl Into<String>) -> Self {
        Self {
            id: id.to_string(),
            statement: statement.into(),
        }
    }
}

/// A runtime binding that reports claims and can re-check them against its
/// recorded execution.
pub trait ClaimSource {
    /// Name of the binding.
    fn source_name(&self) -> &str;
    /// Digest of the recorded execution the claims refer to.
    fn digest(&self) -> u64;
    /// Claims the binding makes.
    fn claims(&self) -> Vec<RuntimeClaim>;
    /// Re-check claim `id`: the number of cases checked, or a
    /// counterexample.
    fn recheck(&self, id: &str) -> Result<u64, String>;
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(p: u32) -> GapTensor {
        vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::new(p, 1, 1.0)])
    }

    #[test]
    fn capture_and_verify() {
        let mut store = SnapshotStore::new();
        store.capture("start", &state(3));
        store.capture("bad", &state(4));
        assert_eq!(store.len(), 2);
        assert!(store.verify().is_ok());
        assert!(store.get(0).unwrap().is_valid());
        assert!(!store.latest().unwrap().is_valid());
        assert_eq!(store.last_valid().unwrap().step, 0);
        assert_eq!(store.first_violation().map(|(s, _)| s), Some(1));
        assert_eq!(store.head_digest(), store.trace().head_digest());
    }

    #[test]
    fn tampering_is_detected() {
        let mut store = SnapshotStore::new();
        store.capture("a", &state(3));
        store.capture("b", &state(5));
        store.snapshots_mut_for_testing()[1].tensor = state(7);
        assert_eq!(store.verify(), Err(SnapshotError::StateMismatch { step: 1 }));

        let mut store = SnapshotStore::new();
        store.capture("a", &state(3));
        store.snapshots_mut_for_testing()[0].invariants.violations.clear();
        store.snapshots_mut_for_testing()[0].tensor = state(4);
        assert!(store.verify().is_err());

        let mut store = SnapshotStore::new();
        store.capture("a", &state(3));
        store.snapshots_mut_for_testing()[0].label = "edited".into();
        assert_eq!(store.verify(), Err(SnapshotError::MetadataMismatch { step: 0 }));
    }

    #[test]
    fn helpers() {
        assert!(tensors_bitwise_equal(&state(3), &state(3)));
        assert!(!tensors_bitwise_equal(&state(3), &state(5)));
        assert_eq!(vector_state(vec![]).nodes().len(), 1);
        assert!(empty_state().nodes()[0].is_nil());
    }
}
