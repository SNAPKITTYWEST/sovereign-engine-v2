//! trace_recording_runtime
//!
//! One tamper-evident trace for a whole execution: the recorded states of
//! every binding and the certificates issued for them, interleaved in a
//! single hash chain. Certificates are recorded as labelled entries (the
//! label is covered by the chain digest), so editing a certificate summary,
//! a state, or the order of entries is detected by [`RuntimeTrace::verify`].

#![warn(missing_docs)]

use certificate_generation::ExecutionCertificate;
use gap_tensor_trace::{TensorTrace, TraceEntry, TraceError};
use runtime_state_snapshot::{empty_state, GapTensor, SnapshotStore};

/// Label prefix of certificate entries.
pub const CERTIFICATE_PREFIX: &str = "certificate ";

/// Kind of a trace entry.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EntryKind {
    /// A recorded state of `source` at `step`.
    State {
        /// Binding name.
        source: String,
        /// Step within that binding's history.
        step: u64,
    },
    /// A certificate summary.
    Certificate(String),
    /// A free-form state.
    Other(String),
}

/// A whole-execution trace.
#[derive(Debug, Clone, Default)]
pub struct RuntimeTrace {
    trace: TensorTrace,
}

impl RuntimeTrace {
    /// An empty trace.
    pub fn new() -> Self {
        Self::default()
    }

    /// Rebuild from entries, rejecting a broken chain.
    pub fn from_entries(entries: Vec<TraceEntry>) -> Result<Self, TraceError> {
        Ok(Self {
            trace: TensorTrace::from_entries(entries)?,
        })
    }

    /// Record a free-form state.
    pub fn record_state(&mut self, label: &str, tensor: &GapTensor) -> u64 {
        self.trace.record(label, tensor)
    }

    /// Append every snapshot of a binding's history.
    pub fn record_store(&mut self, source: &str, store: &SnapshotStore) {
        for s in store.snapshots() {
            self.trace.record(format!("{source}#{}:{}", s.step, s.label), &s.tensor);
        }
    }

    /// Append a certificate summary.
    pub fn record_certificate(&mut self, certificate: &ExecutionCertificate) -> u64 {
        self.trace.record(certificate.summary(), &empty_state())
    }

    /// Verify the whole chain.
    pub fn verify(&self) -> Result<(), TraceError> {
        self.trace.verify()
    }

    /// Number of entries.
    pub fn len(&self) -> usize {
        self.trace.len()
    }

    /// Nothing recorded?
    pub fn is_empty(&self) -> bool {
        self.trace.is_empty()
    }

    /// Digest of the whole execution.
    pub fn head_digest(&self) -> u64 {
        self.trace.head_digest()
    }

    /// Raw entries.
    pub fn entries(&self) -> &[TraceEntry] {
        self.trace.entries()
    }

    /// Classify entry `index`.
    pub fn kind(&self, index: usize) -> Option<EntryKind> {
        let label = &self.trace.entries().get(index)?.label;
        if label.starts_with(CERTIFICATE_PREFIX) {
            return Some(EntryKind::Certificate(label.clone()));
        }
        if let Some((source, rest)) = label.split_once('#') {
            if let Some((step, _)) = rest.split_once(':') {
                if let Ok(step) = step.parse() {
                    return Some(EntryKind::State {
                        source: source.to_string(),
                        step,
                    });
                }
            }
        }
        Some(EntryKind::Other(label.clone()))
    }

    /// Replay entry `index`.
    pub fn replay(&self, index: usize) -> Result<GapTensor, TraceError> {
        self.trace.replay(index)
    }

    /// Certificate summaries in order.
    pub fn certificates(&self) -> Vec<String> {
        (0..self.len())
            .filter_map(|i| match self.kind(i) {
                Some(EntryKind::Certificate(s)) => Some(s),
                _ => None,
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use certificate_generation::{certify, TensorBinding};
    use runtime_state_snapshot::{tensors_bitwise_equal, vector_state, GapTensorNode};

    fn execution() -> (TensorBinding, RuntimeTrace) {
        let mut t = TensorBinding::new("tensor", vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL]));
        t.set_node(1, GapTensorNode::new(3, 1, 1.0)).unwrap();
        let mut trace = RuntimeTrace::new();
        trace.record_store("tensor", t.store());
        trace.record_certificate(&certify(&[&t]));
        (t, trace)
    }

    #[test]
    fn states_and_certificates_share_one_chain() {
        let (t, trace) = execution();
        assert_eq!(trace.len(), 3);
        assert!(trace.verify().is_ok());
        assert_eq!(trace.kind(1), Some(EntryKind::State { source: "tensor".into(), step: 1 }));
        assert_eq!(trace.certificates().len(), 1);
        assert!(tensors_bitwise_equal(&trace.replay(1).unwrap(), t.tensor()));
    }

    #[test]
    fn tampering_is_detected() {
        let (_, trace) = execution();
        let mut entries = trace.entries().to_vec();
        entries[2].label = entries[2].label.replace("failed=0", "failed=9");
        assert!(RuntimeTrace::from_entries(entries).is_err());

        let mut entries = trace.entries().to_vec();
        entries.swap(0, 1);
        assert!(RuntimeTrace::from_entries(entries).is_err());
    }
}
