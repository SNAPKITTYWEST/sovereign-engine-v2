//! gap_tensor_shape
//!
//! Tensor shapes (dimensions, row-major strides, index conversion) and
//! [`GapTensor`], a shaped, bounds-checked container of gap tensor nodes.

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;
use std::fmt;

/// Errors from shape construction and indexing.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ShapeError {
    /// A shape must have at least one dimension.
    EmptyShape,
    /// Every dimension must be non-zero.
    ZeroDimension {
        /// Offending axis.
        axis: usize,
    },
    /// The element count does not fit in `usize`.
    Overflow,
    /// An index had the wrong number of components.
    RankMismatch {
        /// Rank of the shape.
        expected: usize,
        /// Components supplied.
        got: usize,
    },
    /// A component of a multi-index is out of bounds.
    IndexOutOfBounds {
        /// Axis of the bad component.
        axis: usize,
        /// Supplied index.
        index: usize,
        /// Size of that axis.
        dim: usize,
    },
    /// A flat index is out of bounds.
    FlatIndexOutOfBounds {
        /// Supplied flat index.
        index: usize,
        /// Element count.
        len: usize,
    },
    /// A node buffer does not match the shape's element count.
    LengthMismatch {
        /// Element count required by the shape.
        expected: usize,
        /// Element count supplied.
        got: usize,
    },
}

impl fmt::Display for ShapeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for ShapeError {}

/// Dimensions of a tensor. Always rank >= 1 with non-zero dimensions and an
/// element count that fits in `usize`.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TensorShape {
    dims: Vec<usize>,
    len: usize,
}

impl TensorShape {
    /// Validate and build a shape.
    pub fn new(dims: Vec<usize>) -> Result<Self, ShapeError> {
        if dims.is_empty() {
            return Err(ShapeError::EmptyShape);
        }
        if let Some(axis) = dims.iter().position(|&d| d == 0) {
            return Err(ShapeError::ZeroDimension { axis });
        }
        let len = dims
            .iter()
            .try_fold(1usize, |acc, &d| acc.checked_mul(d))
            .ok_or(ShapeError::Overflow)?;
        Ok(Self { dims, len })
    }

    /// A rank-1 shape of `n` elements.
    pub fn vector(n: usize) -> Result<Self, ShapeError> {
        Self::new(vec![n])
    }

    /// A rank-2 shape.
    pub fn matrix(rows: usize, cols: usize) -> Result<Self, ShapeError> {
        Self::new(vec![rows, cols])
    }

    /// The dimensions.
    pub fn dims(&self) -> &[usize] {
        &self.dims
    }

    /// Number of axes.
    pub fn rank(&self) -> usize {
        self.dims.len()
    }

    /// Number of elements.
    pub fn len(&self) -> usize {
        self.len
    }

    /// Always false: a valid shape has at least one element.
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    /// Row-major strides (last axis has stride 1).
    pub fn strides(&self) -> Vec<usize> {
        let mut strides = vec![1usize; self.dims.len()];
        for axis in (0..self.dims.len().saturating_sub(1)).rev() {
            strides[axis] = strides[axis + 1] * self.dims[axis + 1];
        }
        strides
    }

    /// Convert a multi-index to a flat row-major offset.
    pub fn flat_index(&self, index: &[usize]) -> Result<usize, ShapeError> {
        if index.len() != self.dims.len() {
            return Err(ShapeError::RankMismatch {
                expected: self.dims.len(),
                got: index.len(),
            });
        }
        let mut flat = 0usize;
        for (axis, (&i, &dim)) in index.iter().zip(&self.dims).enumerate() {
            if i >= dim {
                return Err(ShapeError::IndexOutOfBounds { axis, index: i, dim });
            }
            flat = flat * dim + i;
        }
        Ok(flat)
    }

    /// Convert a flat row-major offset to a multi-index.
    pub fn multi_index(&self, flat: usize) -> Result<Vec<usize>, ShapeError> {
        if flat >= self.len {
            return Err(ShapeError::FlatIndexOutOfBounds {
                index: flat,
                len: self.len,
            });
        }
        let mut index = vec![0usize; self.dims.len()];
        let mut rest = flat;
        for axis in (0..self.dims.len()).rev() {
            index[axis] = rest % self.dims[axis];
            rest /= self.dims[axis];
        }
        Ok(index)
    }
}

/// A shaped tensor of gap tensor nodes stored in row-major order.
#[derive(Debug, Clone, PartialEq)]
pub struct GapTensor {
    shape: TensorShape,
    nodes: Vec<GapTensorNode>,
}

impl GapTensor {
    /// A tensor filled with Nil nodes.
    pub fn nil(shape: TensorShape) -> Self {
        let nodes = vec![GapTensorNode::NIL; shape.len()];
        Self { shape, nodes }
    }

    /// Wrap an existing node buffer; its length must match the shape.
    pub fn from_nodes(shape: TensorShape, nodes: Vec<GapTensorNode>) -> Result<Self, ShapeError> {
        if nodes.len() != shape.len() {
            return Err(ShapeError::LengthMismatch {
                expected: shape.len(),
                got: nodes.len(),
            });
        }
        Ok(Self { shape, nodes })
    }

    /// The tensor's shape.
    pub fn shape(&self) -> &TensorShape {
        &self.shape
    }

    /// All nodes in row-major order.
    pub fn nodes(&self) -> &[GapTensorNode] {
        &self.nodes
    }

    /// Mutable access to all nodes in row-major order.
    pub fn nodes_mut(&mut self) -> &mut [GapTensorNode] {
        &mut self.nodes
    }

    /// Consume the tensor and return its node buffer.
    pub fn into_nodes(self) -> Vec<GapTensorNode> {
        self.nodes
    }

    /// Read the node at a multi-index.
    pub fn get(&self, index: &[usize]) -> Result<GapTensorNode, ShapeError> {
        let flat = self.shape.flat_index(index)?;
        Ok(self.nodes[flat])
    }

    /// Write the node at a multi-index.
    pub fn set(&mut self, index: &[usize], node: GapTensorNode) -> Result<(), ShapeError> {
        let flat = self.shape.flat_index(index)?;
        self.nodes[flat] = node;
        Ok(())
    }

    /// Change the shape in place; the element count must be preserved.
    pub fn reshape(&mut self, shape: TensorShape) -> Result<(), ShapeError> {
        if shape.len() != self.shape.len() {
            return Err(ShapeError::LengthMismatch {
                expected: self.shape.len(),
                got: shape.len(),
            });
        }
        self.shape = shape;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shape_validation() {
        assert_eq!(TensorShape::new(vec![]), Err(ShapeError::EmptyShape));
        assert_eq!(
            TensorShape::new(vec![2, 0, 3]),
            Err(ShapeError::ZeroDimension { axis: 1 })
        );
        assert_eq!(
            TensorShape::new(vec![usize::MAX, 2]),
            Err(ShapeError::Overflow)
        );
        let s = TensorShape::new(vec![2, 3, 4]).unwrap();
        assert_eq!(s.rank(), 3);
        assert_eq!(s.len(), 24);
        assert!(!s.is_empty());
    }

    #[test]
    fn row_major_strides() {
        let s = TensorShape::new(vec![2, 3, 4]).unwrap();
        assert_eq!(s.strides(), vec![12, 4, 1]);
        assert_eq!(TensorShape::vector(5).unwrap().strides(), vec![1]);
    }

    #[test]
    fn index_round_trip_covers_every_element() {
        let s = TensorShape::new(vec![2, 3, 4]).unwrap();
        for flat in 0..s.len() {
            let multi = s.multi_index(flat).unwrap();
            assert_eq!(s.flat_index(&multi).unwrap(), flat);
        }
        assert_eq!(s.flat_index(&[1, 2, 3]).unwrap(), 23);
    }

    #[test]
    fn index_errors() {
        let s = TensorShape::matrix(2, 3).unwrap();
        assert_eq!(
            s.flat_index(&[1]),
            Err(ShapeError::RankMismatch { expected: 2, got: 1 })
        );
        assert_eq!(
            s.flat_index(&[0, 3]),
            Err(ShapeError::IndexOutOfBounds { axis: 1, index: 3, dim: 3 })
        );
        assert_eq!(
            s.multi_index(6),
            Err(ShapeError::FlatIndexOutOfBounds { index: 6, len: 6 })
        );
    }

    #[test]
    fn tensor_get_set_reshape() {
        let mut t = GapTensor::nil(TensorShape::matrix(2, 3).unwrap());
        let node = GapTensorNode::new(5, 2, 0.5);
        t.set(&[1, 2], node).unwrap();
        assert_eq!(t.get(&[1, 2]).unwrap(), node);
        assert_eq!(t.nodes()[5], node);
        assert!(t.get(&[2, 0]).is_err());

        t.reshape(TensorShape::vector(6).unwrap()).unwrap();
        assert_eq!(t.get(&[5]).unwrap(), node);
        assert_eq!(
            t.reshape(TensorShape::vector(7).unwrap()),
            Err(ShapeError::LengthMismatch { expected: 6, got: 7 })
        );
    }

    #[test]
    fn from_nodes_checks_length() {
        let shape = TensorShape::vector(3).unwrap();
        assert!(GapTensor::from_nodes(shape.clone(), vec![GapTensorNode::NIL; 3]).is_ok());
        assert_eq!(
            GapTensor::from_nodes(shape, vec![GapTensorNode::NIL; 2]),
            Err(ShapeError::LengthMismatch { expected: 3, got: 2 })
        );
    }
}
