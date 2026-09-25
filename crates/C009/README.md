# `gap_tensor_arithmetic` (C009)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

Resonance-preserving arithmetic on gap tensor nodes and tensors.

Merging two nodes of the same prime adds their multiplicities and picks
the weight that makes resonance additive:
`w = (m_a·w_a + m_b·w_b) / (m_a + m_b)`. Nil is the identity for merge.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C004 `gap_tensor_shape`](../C004/README.md)

## Public API

| Item | Description |
|---|---|
| `enum ArithmeticError` | Errors from node and tensor arithmetic. |
| `fn merge_nodes(a: &GapTensorNode, b: &GapTensorNode) -> Result<GapTensorNode, ArithmeticError>` | Merge two nodes. |
| `fn scale_weight(node: &GapTensorNode, factor: f32) -> Result<GapTensorNode, ArithmeticError>` | Multiply a node's weight by a finite factor. |
| `fn split_node(node: &GapTensorNode, count: u32) -> Result<(GapTensorNode, GapTensorNode), ArithmeticError>` | Split `count` units of multiplicity off a node. |
| `fn merge_tensors(a: &GapTensor, b: &GapTensor) -> Result<GapTensor, ArithmeticError>` | Element-wise merge of two tensors of the same shape. |
| `fn total_multiplicity(tensor: &GapTensor) -> u64` | Sum of multiplicities over all non-nil nodes. |
| `fn total_resonance(tensor: &GapTensor) -> f64` | Sum of resonance over all non-nil nodes, accumulated in `f64`. |

## Tests

`cargo test -p gap_tensor_arithmetic` runs 5 unit tests.
