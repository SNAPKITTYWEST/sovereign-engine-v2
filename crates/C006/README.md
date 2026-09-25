# `gap_tensor_serialization` (C006)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

Self-describing, checksummed binary encoding for .

Layout (all integers little-endian):

| Field    | Size        |
|----------|-------------|
| magic    | 4 (`GTS1`)  |
| version  | 1           |
| rank     | 4 (`u32`)   |
| dims     | 8 × rank    |
| count    | 8 (`u64`)   |
| nodes    | 12 × count (prime `u32`, multiplicity `u32`, weight bits `u32`) |
| checksum | 8 (FNV-1a 64 of every preceding byte) |

Spectral weights are stored by bit pattern, so a round trip is exact
(including `-0.0` and NaN payloads).

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C004 `gap_tensor_shape`](../C004/README.md)
- [C005 `gap_tensor_equality`](../C005/README.md)

## Re-exports

- `gap_tensor_shape::{GapTensor, ShapeError, TensorShape}`

## Public API

| Item | Description |
|---|---|
| `const MAGIC: [u8` | Format magic. |
| `const VERSION: u8 = 1` | Format version. |
| `const NODE_BYTES: usize = 12` | Encoded size of one node. |
| `enum SerializationError` | Errors from decoding. |
| `const fn fnv1a64(bytes: &[u8]) -> u64` | 64-bit FNV-1a hash. |
| `fn encode_node(node: &GapTensorNode, out: &mut Vec<u8>)` | Append the 12-byte encoding of `node` to `out`. |
| `fn decode_node(bytes: &[u8]) -> Result<GapTensorNode, SerializationError>` | Decode one node from the first `NODE_BYTES` bytes of `bytes`. |
| `fn serialize(tensor: &GapTensor) -> Vec<u8>` | Encode a tensor. |
| `fn deserialize(bytes: &[u8]) -> Result<GapTensor, SerializationError>` | Decode a tensor, validating magic, version, checksum, shape and length. |
| `fn round_trips(tensor: &GapTensor) -> bool` | True iff `tensor` survives serialize → deserialize bit-for-bit. |

## Tests

`cargo test -p gap_tensor_serialization` runs 5 unit tests.
