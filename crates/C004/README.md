# `gap_tensor_shape` (C004)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

Tensor shapes (dimensions, row-major strides, index conversion) and
, a shaped, bounds-checked container of gap tensor nodes.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)

## Public API

| Item | Description |
|---|---|
| `enum ShapeError` | Errors from shape construction and indexing. |
| `struct TensorShape` | Dimensions of a tensor. |
| `fn TensorShape::new(dims: Vec<usize>) -> Result<Self, ShapeError>` | Validate and build a shape. |
| `fn TensorShape::vector(n: usize) -> Result<Self, ShapeError>` | A rank-1 shape of `n` elements. |
| `fn TensorShape::matrix(rows: usize, cols: usize) -> Result<Self, ShapeError>` | A rank-2 shape. |
| `fn TensorShape::dims(&self) -> &[usize]` | The dimensions. |
| `fn TensorShape::rank(&self) -> usize` | Number of axes. |
| `fn TensorShape::len(&self) -> usize` | Number of elements. |
| `fn TensorShape::is_empty(&self) -> bool` | Always false: a valid shape has at least one element. |
| `fn TensorShape::strides(&self) -> Vec<usize>` | Row-major strides (last axis has stride 1). |
| `fn TensorShape::flat_index(&self, index: &[usize]) -> Result<usize, ShapeError>` | Convert a multi-index to a flat row-major offset. |
| `fn TensorShape::multi_index(&self, flat: usize) -> Result<Vec<usize>, ShapeError>` | Convert a flat row-major offset to a multi-index. |
| `struct GapTensor` | A shaped tensor of gap tensor nodes stored in row-major order. |
| `fn GapTensor::nil(shape: TensorShape) -> Self` | A tensor filled with Nil nodes. |
| `fn GapTensor::from_nodes(shape: TensorShape, nodes: Vec<GapTensorNode>) -> Result<Self, ShapeError>` | Wrap an existing node buffer; its length must match the shape. |
| `fn GapTensor::shape(&self) -> &TensorShape` | The tensor's shape. |
| `fn GapTensor::nodes(&self) -> &[GapTensorNode]` | All nodes in row-major order. |
| `fn GapTensor::nodes_mut(&mut self) -> &mut [GapTensorNode]` | Mutable access to all nodes in row-major order. |
| `fn GapTensor::into_nodes(self) -> Vec<GapTensorNode>` | Consume the tensor and return its node buffer. |
| `fn GapTensor::get(&self, index: &[usize]) -> Result<GapTensorNode, ShapeError>` | Read the node at a multi-index. |
| `fn GapTensor::set(&mut self, index: &[usize], node: GapTensorNode) -> Result<(), ShapeError>` | Write the node at a multi-index. |
| `fn GapTensor::reshape(&mut self, shape: TensorShape) -> Result<(), ShapeError>` | Change the shape in place; the element count must be preserved. |

## Tests

`cargo test -p gap_tensor_shape` runs 6 unit tests.
