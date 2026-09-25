# `gap_tensor_equality` (C005)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

Equality semantics for gap tensor nodes and tensors: exact (bitwise on
spectral weight), approximate (weight tolerance) and structural (weight
ignored).

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C004 `gap_tensor_shape`](../C004/README.md)

## Public API

| Item | Description |
|---|---|
| `enum EqualityMode` | How spectral weights are compared. |
| `enum EqualityError` | Errors from tensor comparison. |
| `fn nodes_equal(a: &GapTensorNode, b: &GapTensorNode, mode: EqualityMode) -> bool` | Compare two nodes under `mode`. |
| `fn first_difference(a: &GapTensor, b: &GapTensor, mode: EqualityMode) -> Result<Option<usize>, EqualityError>` | Flat index of the first node that differs under `mode`, or `None` if the tensors are equal. |
| `fn count_differences(a: &GapTensor, b: &GapTensor, mode: EqualityMode) -> Result<usize, EqualityError>` | Number of nodes that differ under `mode`. |
| `fn tensors_equal(a: &GapTensor, b: &GapTensor, mode: EqualityMode) -> bool` | True iff the tensors have the same shape and all nodes are equal under `mode`. |

## Tests

`cargo test -p gap_tensor_equality` runs 5 unit tests.
