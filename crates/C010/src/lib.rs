//! gap_tensor_trace
//!
//! A tamper-evident, append-only trace of tensor states. Each entry stores
//! the serialized tensor and a digest chained to the previous entry, so any
//! edit, reordering or truncation in the middle of the trace is detected by
//! [`TensorTrace::verify`].
//!
//! Digest of entry `i`: FNV-1a 64 over
//! `prev_digest ‖ step ‖ label_len ‖ label ‖ payload` (integers little-endian),
//! where `prev_digest` is [`GENESIS_DIGEST`] for the first entry.

#![warn(missing_docs)]

use gap_tensor_equality::{first_difference, EqualityMode};
use gap_tensor_serialization::{deserialize, fnv1a64, serialize, SerializationError};
pub use gap_tensor_serialization::{GapTensor, TensorShape};

/// Digest that the first entry chains from.
pub const GENESIS_DIGEST: u64 = fnv1a64(b"gap_tensor_trace/genesis");

/// One recorded tensor state.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TraceEntry {
    /// Position in the trace (0-based).
    pub step: u64,
    /// Caller-supplied label.
    pub label: String,
    /// Serialized tensor (`gap_tensor_serialization` format).
    pub payload: Vec<u8>,
    /// Digest of the previous entry.
    pub prev_digest: u64,
    /// Digest of this entry.
    pub digest: u64,
}

/// Errors from trace verification and access.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TraceError {
    /// Index past the end of the trace.
    OutOfRange {
        /// Requested index.
        index: usize,
        /// Trace length.
        len: usize,
    },
    /// An entry's step does not equal its position.
    StepOutOfOrder {
        /// Entry position.
        index: usize,
    },
    /// An entry does not chain from the previous entry's digest.
    BrokenChain {
        /// Entry position.
        index: usize,
    },
    /// An entry's stored digest does not match its contents.
    DigestMismatch {
        /// Entry position.
        index: usize,
    },
    /// An entry's payload does not decode.
    Decode {
        /// Entry position.
        index: usize,
        /// Decoder error.
        error: SerializationError,
    },
    /// Two replayed states have different shapes.
    ShapeMismatch {
        /// First entry.
        left: usize,
        /// Second entry.
        right: usize,
    },
}

fn entry_digest(prev_digest: u64, step: u64, label: &str, payload: &[u8]) -> u64 {
    let mut buf = Vec::with_capacity(24 + label.len() + payload.len());
    buf.extend_from_slice(&prev_digest.to_le_bytes());
    buf.extend_from_slice(&step.to_le_bytes());
    buf.extend_from_slice(&(label.len() as u64).to_le_bytes());
    buf.extend_from_slice(label.as_bytes());
    buf.extend_from_slice(payload);
    fnv1a64(&buf)
}

/// Append-only chained trace of tensor states.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct TensorTrace {
    entries: Vec<TraceEntry>,
}

impl TensorTrace {
    /// An empty trace.
    pub fn new() -> Self {
        Self::default()
    }

    /// Rebuild a trace from stored entries, rejecting it unless it verifies.
    pub fn from_entries(entries: Vec<TraceEntry>) -> Result<Self, TraceError> {
        let trace = Self { entries };
        trace.verify()?;
        Ok(trace)
    }

    /// Record a tensor state. Returns the new entry's digest.
    pub fn record(&mut self, label: impl Into<String>, tensor: &GapTensor) -> u64 {
        let label = label.into();
        let step = self.entries.len() as u64;
        let prev_digest = self.head_digest();
        let payload = serialize(tensor);
        let digest = entry_digest(prev_digest, step, &label, &payload);
        self.entries.push(TraceEntry {
            step,
            label,
            payload,
            prev_digest,
            digest,
        });
        digest
    }

    /// Number of entries.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// True iff nothing has been recorded.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// All entries in order.
    pub fn entries(&self) -> &[TraceEntry] {
        &self.entries
    }

    /// Digest of the last entry, or [`GENESIS_DIGEST`] if empty.
    pub fn head_digest(&self) -> u64 {
        self.entries.last().map_or(GENESIS_DIGEST, |e| e.digest)
    }

    /// Check step order, chaining and every digest.
    pub fn verify(&self) -> Result<(), TraceError> {
        let mut expected_prev = GENESIS_DIGEST;
        for (index, e) in self.entries.iter().enumerate() {
            if e.step != index as u64 {
                return Err(TraceError::StepOutOfOrder { index });
            }
            if e.prev_digest != expected_prev {
                return Err(TraceError::BrokenChain { index });
            }
            if entry_digest(e.prev_digest, e.step, &e.label, &e.payload) != e.digest {
                return Err(TraceError::DigestMismatch { index });
            }
            expected_prev = e.digest;
        }
        Ok(())
    }

    /// Decode the tensor recorded at `index`.
    pub fn replay(&self, index: usize) -> Result<GapTensor, TraceError> {
        let entry = self.entries.get(index).ok_or(TraceError::OutOfRange {
            index,
            len: self.entries.len(),
        })?;
        deserialize(&entry.payload).map_err(|error| TraceError::Decode { index, error })
    }

    /// First flat node index at which the states at `left` and `right`
    /// differ under `mode`, or `None` if they are equal.
    pub fn first_divergence(
        &self,
        left: usize,
        right: usize,
        mode: EqualityMode,
    ) -> Result<Option<usize>, TraceError> {
        let a = self.replay(left)?;
        let b = self.replay(right)?;
        first_difference(&a, &b, mode).map_err(|_| TraceError::ShapeMismatch { left, right })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use gap_tensor_core::GapTensorNode;
    use gap_tensor_equality::tensors_equal;

    fn state(w: f32) -> GapTensor {
        GapTensor::from_nodes(
            TensorShape::vector(3).unwrap(),
            vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL, GapTensorNode::new(5, 2, w)],
        )
        .unwrap()
    }

    fn sample() -> TensorTrace {
        let mut t = TensorTrace::new();
        t.record("init", &state(1.0));
        t.record("step", &state(2.0));
        t.record("final", &state(2.0));
        t
    }

    #[test]
    fn record_and_verify() {
        let t = sample();
        assert_eq!(t.len(), 3);
        assert!(t.verify().is_ok());
        assert_eq!(t.entries()[0].prev_digest, GENESIS_DIGEST);
        assert_eq!(t.entries()[1].prev_digest, t.entries()[0].digest);
        assert_eq!(t.head_digest(), t.entries()[2].digest);
        assert_eq!(TensorTrace::new().head_digest(), GENESIS_DIGEST);
    }

    #[test]
    fn tampering_is_detected() {
        let mut entries = sample().entries().to_vec();
        entries[1].payload[20] ^= 1;
        assert_eq!(
            TensorTrace::from_entries(entries).unwrap_err(),
            TraceError::DigestMismatch { index: 1 }
        );

        let mut entries = sample().entries().to_vec();
        entries[1].label = "edited".into();
        assert_eq!(
            TensorTrace::from_entries(entries).unwrap_err(),
            TraceError::DigestMismatch { index: 1 }
        );

        let mut entries = sample().entries().to_vec();
        entries.remove(1);
        assert_eq!(
            TensorTrace::from_entries(entries).unwrap_err(),
            TraceError::StepOutOfOrder { index: 1 }
        );

        let mut entries = sample().entries().to_vec();
        entries[2].prev_digest ^= 1;
        assert_eq!(
            TensorTrace::from_entries(entries).unwrap_err(),
            TraceError::BrokenChain { index: 2 }
        );
    }

    #[test]
    fn replay_and_divergence() {
        let t = sample();
        assert!(tensors_equal(&t.replay(0).unwrap(), &state(1.0), EqualityMode::Exact));
        assert_eq!(t.first_divergence(0, 1, EqualityMode::Exact), Ok(Some(2)));
        assert_eq!(t.first_divergence(1, 2, EqualityMode::Exact), Ok(None));
        assert_eq!(
            t.replay(3).unwrap_err(),
            TraceError::OutOfRange { index: 3, len: 3 }
        );
    }
}
