//! gap_tensor_serialization
//!
//! Self-describing, checksummed binary encoding for [`GapTensor`].
//!
//! Layout (all integers little-endian):
//!
//! | Field    | Size        |
//! |----------|-------------|
//! | magic    | 4 (`GTS1`)  |
//! | version  | 1           |
//! | rank     | 4 (`u32`)   |
//! | dims     | 8 × rank    |
//! | count    | 8 (`u64`)   |
//! | nodes    | 12 × count (prime `u32`, multiplicity `u32`, weight bits `u32`) |
//! | checksum | 8 (FNV-1a 64 of every preceding byte) |
//!
//! Spectral weights are stored by bit pattern, so a round trip is exact
//! (including `-0.0` and NaN payloads).

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;
use gap_tensor_equality::{tensors_equal, EqualityMode};
pub use gap_tensor_shape::{GapTensor, ShapeError, TensorShape};
use std::fmt;

/// Format magic.
pub const MAGIC: [u8; 4] = *b"GTS1";
/// Format version.
pub const VERSION: u8 = 1;
/// Encoded size of one node.
pub const NODE_BYTES: usize = 12;
const HEADER_MIN: usize = 4 + 1 + 4 + 8;
const CHECKSUM_BYTES: usize = 8;

/// Errors from decoding.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SerializationError {
    /// The input ended early.
    Truncated {
        /// Bytes required.
        needed: usize,
        /// Bytes available.
        available: usize,
    },
    /// The input does not start with [`MAGIC`].
    BadMagic([u8; 4]),
    /// The version byte is not [`VERSION`].
    UnsupportedVersion(u8),
    /// The trailing checksum does not match the contents.
    ChecksumMismatch {
        /// Checksum stored in the input.
        stored: u64,
        /// Checksum computed over the input.
        computed: u64,
    },
    /// The encoded shape is invalid.
    InvalidShape(ShapeError),
    /// A dimension or count does not fit in `usize`.
    TooLarge,
    /// The declared node count disagrees with the shape.
    CountMismatch {
        /// Count stored in the input.
        declared: u64,
        /// Element count of the decoded shape.
        shape_len: usize,
    },
    /// Bytes remain after the last node.
    TrailingBytes(usize),
}

impl fmt::Display for SerializationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for SerializationError {}

/// 64-bit FNV-1a hash.
pub const fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut hash = 0xcbf2_9ce4_8422_2325u64;
    let mut i = 0;
    while i < bytes.len() {
        hash ^= bytes[i] as u64;
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
        i += 1;
    }
    hash
}

/// Append the 12-byte encoding of `node` to `out`.
pub fn encode_node(node: &GapTensorNode, out: &mut Vec<u8>) {
    out.extend_from_slice(&node.prime_val.to_le_bytes());
    out.extend_from_slice(&node.multiplicity.to_le_bytes());
    out.extend_from_slice(&node.spectral_weight.to_bits().to_le_bytes());
}

/// Decode one node from the first [`NODE_BYTES`] bytes of `bytes`.
pub fn decode_node(bytes: &[u8]) -> Result<GapTensorNode, SerializationError> {
    if bytes.len() < NODE_BYTES {
        return Err(SerializationError::Truncated {
            needed: NODE_BYTES,
            available: bytes.len(),
        });
    }
    let word = |i: usize| u32::from_le_bytes([bytes[i], bytes[i + 1], bytes[i + 2], bytes[i + 3]]);
    Ok(GapTensorNode::new(word(0), word(4), f32::from_bits(word(8))))
}

/// Encode a tensor.
pub fn serialize(tensor: &GapTensor) -> Vec<u8> {
    let dims = tensor.shape().dims();
    let mut out = Vec::with_capacity(
        HEADER_MIN + 8 * dims.len() + NODE_BYTES * tensor.nodes().len() + CHECKSUM_BYTES,
    );
    out.extend_from_slice(&MAGIC);
    out.push(VERSION);
    out.extend_from_slice(&(dims.len() as u32).to_le_bytes());
    for &d in dims {
        out.extend_from_slice(&(d as u64).to_le_bytes());
    }
    out.extend_from_slice(&(tensor.nodes().len() as u64).to_le_bytes());
    for node in tensor.nodes() {
        encode_node(node, &mut out);
    }
    let checksum = fnv1a64(&out);
    out.extend_from_slice(&checksum.to_le_bytes());
    out
}

struct Reader<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8], SerializationError> {
        let available = self.bytes.len() - self.pos;
        if n > available {
            return Err(SerializationError::Truncated { needed: n, available });
        }
        let slice = &self.bytes[self.pos..self.pos + n];
        self.pos += n;
        Ok(slice)
    }

    fn u32(&mut self) -> Result<u32, SerializationError> {
        let b = self.take(4)?;
        Ok(u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
    }

    fn u64(&mut self) -> Result<u64, SerializationError> {
        let b = self.take(8)?;
        let mut a = [0u8; 8];
        a.copy_from_slice(b);
        Ok(u64::from_le_bytes(a))
    }

    fn remaining(&self) -> usize {
        self.bytes.len() - self.pos
    }
}

/// Decode a tensor, validating magic, version, checksum, shape and length.
pub fn deserialize(bytes: &[u8]) -> Result<GapTensor, SerializationError> {
    if bytes.len() < HEADER_MIN + CHECKSUM_BYTES {
        return Err(SerializationError::Truncated {
            needed: HEADER_MIN + CHECKSUM_BYTES,
            available: bytes.len(),
        });
    }
    let magic = [bytes[0], bytes[1], bytes[2], bytes[3]];
    if magic != MAGIC {
        return Err(SerializationError::BadMagic(magic));
    }
    if bytes[4] != VERSION {
        return Err(SerializationError::UnsupportedVersion(bytes[4]));
    }
    let (body, tail) = bytes.split_at(bytes.len() - CHECKSUM_BYTES);
    let mut stored = [0u8; 8];
    stored.copy_from_slice(tail);
    let stored = u64::from_le_bytes(stored);
    let computed = fnv1a64(body);
    if stored != computed {
        return Err(SerializationError::ChecksumMismatch { stored, computed });
    }

    let mut r = Reader { bytes: body, pos: 5 };
    let rank = r.u32()? as usize;
    if rank > r.remaining() / 8 {
        return Err(SerializationError::Truncated {
            needed: rank.saturating_mul(8),
            available: r.remaining(),
        });
    }
    let mut dims = Vec::with_capacity(rank);
    for _ in 0..rank {
        dims.push(usize::try_from(r.u64()?).map_err(|_| SerializationError::TooLarge)?);
    }
    let shape = TensorShape::new(dims).map_err(SerializationError::InvalidShape)?;
    let declared = r.u64()?;
    if usize::try_from(declared).ok() != Some(shape.len()) {
        return Err(SerializationError::CountMismatch {
            declared,
            shape_len: shape.len(),
        });
    }
    let node_bytes = shape
        .len()
        .checked_mul(NODE_BYTES)
        .ok_or(SerializationError::TooLarge)?;
    let payload = r.take(node_bytes)?;
    if r.remaining() != 0 {
        return Err(SerializationError::TrailingBytes(r.remaining()));
    }
    let nodes = payload
        .chunks_exact(NODE_BYTES)
        .map(decode_node)
        .collect::<Result<Vec<_>, _>>()?;
    GapTensor::from_nodes(shape, nodes).map_err(SerializationError::InvalidShape)
}

/// True iff `tensor` survives serialize → deserialize bit-for-bit.
pub fn round_trips(tensor: &GapTensor) -> bool {
    deserialize(&serialize(tensor))
        .map(|decoded| tensors_equal(tensor, &decoded, EqualityMode::Exact))
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> GapTensor {
        let shape = TensorShape::matrix(2, 2).unwrap();
        GapTensor::from_nodes(
            shape,
            vec![
                GapTensorNode::new(2, 1, 1.5),
                GapTensorNode::NIL,
                GapTensorNode::new(13, 7, -0.0),
                GapTensorNode::new(5, 3, f32::NAN),
            ],
        )
        .unwrap()
    }

    fn rechecksum(mut bytes: Vec<u8>) -> Vec<u8> {
        let body_len = bytes.len() - CHECKSUM_BYTES;
        let sum = fnv1a64(&bytes[..body_len]);
        bytes[body_len..].copy_from_slice(&sum.to_le_bytes());
        bytes
    }

    #[test]
    fn round_trip_is_exact() {
        let t = sample();
        assert!(round_trips(&t));
        let bytes = serialize(&t);
        assert_eq!(bytes.len(), HEADER_MIN + 16 + 4 * NODE_BYTES + CHECKSUM_BYTES);
        let decoded = deserialize(&bytes).unwrap();
        assert_eq!(decoded.nodes()[2].spectral_weight.to_bits(), (-0.0f32).to_bits());
        assert!(decoded.nodes()[3].spectral_weight.is_nan());
    }

    #[test]
    fn corruption_is_detected() {
        let mut bytes = serialize(&sample());
        let last_node_byte = bytes.len() - CHECKSUM_BYTES - 1;
        bytes[last_node_byte] ^= 0xff;
        assert!(matches!(
            deserialize(&bytes),
            Err(SerializationError::ChecksumMismatch { .. })
        ));
    }

    #[test]
    fn header_errors() {
        let mut bytes = serialize(&sample());
        bytes[0] = b'X';
        assert_eq!(deserialize(&bytes), Err(SerializationError::BadMagic(*b"XTS1")));

        let mut bytes = serialize(&sample());
        bytes[4] = 2;
        assert_eq!(deserialize(&bytes), Err(SerializationError::UnsupportedVersion(2)));

        assert!(matches!(
            deserialize(&[0u8; 3]),
            Err(SerializationError::Truncated { .. })
        ));
    }

    #[test]
    fn count_and_length_errors() {
        let bytes = serialize(&sample());
        let count_offset = 4 + 1 + 4 + 16;
        let mut wrong_count = bytes.clone();
        wrong_count[count_offset] = 5;
        assert_eq!(
            deserialize(&rechecksum(wrong_count)),
            Err(SerializationError::CountMismatch { declared: 5, shape_len: 4 })
        );

        let mut trailing = bytes.clone();
        trailing.splice(bytes.len() - CHECKSUM_BYTES..bytes.len() - CHECKSUM_BYTES, [0u8; 3]);
        assert_eq!(
            deserialize(&rechecksum(trailing)),
            Err(SerializationError::TrailingBytes(3))
        );

        let mut short = bytes[..bytes.len() - CHECKSUM_BYTES - NODE_BYTES].to_vec();
        short.extend_from_slice(&[0u8; CHECKSUM_BYTES]);
        assert!(matches!(
            deserialize(&rechecksum(short)),
            Err(SerializationError::Truncated { .. })
        ));
    }

    #[test]
    fn zero_rank_is_rejected() {
        let mut body = Vec::new();
        body.extend_from_slice(&MAGIC);
        body.push(VERSION);
        body.extend_from_slice(&0u32.to_le_bytes());
        body.extend_from_slice(&0u64.to_le_bytes());
        body.extend_from_slice(&[0u8; CHECKSUM_BYTES]);
        assert_eq!(
            deserialize(&rechecksum(body)),
            Err(SerializationError::InvalidShape(ShapeError::EmptyShape))
        );
    }
}
