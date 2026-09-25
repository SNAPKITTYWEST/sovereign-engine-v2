//! gap_tensor_arithmetic
//!
//! Resonance-preserving arithmetic on gap tensor nodes and tensors.
//!
//! Merging two nodes of the same prime adds their multiplicities and picks
//! the weight that makes resonance additive:
//! `w = (m_a·w_a + m_b·w_b) / (m_a + m_b)`. Nil is the identity for merge.

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;
use gap_tensor_shape::{GapTensor, ShapeError};
use std::fmt;

/// Errors from node and tensor arithmetic.
#[derive(Debug, Clone, PartialEq)]
pub enum ArithmeticError {
    /// Two non-nil nodes with different primes cannot be merged.
    PrimeMismatch {
        /// Left prime.
        left: u32,
        /// Right prime.
        right: u32,
    },
    /// Multiplicity overflowed `u32`.
    MultiplicityOverflow,
    /// A weight or factor is (or would become) NaN or infinite.
    NonFiniteWeight,
    /// A split asked for more multiplicity than the node has.
    InsufficientMultiplicity {
        /// Requested.
        requested: u32,
        /// Available.
        available: u32,
    },
    /// Tensor shapes differ.
    Shape(ShapeError),
}

impl fmt::Display for ArithmeticError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for ArithmeticError {}

/// Merge two nodes. Nil is the identity; non-nil nodes must share a prime.
/// When the merged multiplicity is zero the merged weight is `0.0`.
pub fn merge_nodes(a: &GapTensorNode, b: &GapTensorNode) -> Result<GapTensorNode, ArithmeticError> {
    if a.is_nil() {
        return Ok(*b);
    }
    if b.is_nil() {
        return Ok(*a);
    }
    if a.prime_val != b.prime_val {
        return Err(ArithmeticError::PrimeMismatch {
            left: a.prime_val,
            right: b.prime_val,
        });
    }
    let multiplicity = a
        .multiplicity
        .checked_add(b.multiplicity)
        .ok_or(ArithmeticError::MultiplicityOverflow)?;
    let weight = if multiplicity == 0 {
        0.0
    } else {
        let resonance = a.multiplicity as f64 * a.spectral_weight as f64
            + b.multiplicity as f64 * b.spectral_weight as f64;
        (resonance / multiplicity as f64) as f32
    };
    if !weight.is_finite() {
        return Err(ArithmeticError::NonFiniteWeight);
    }
    Ok(GapTensorNode::new(a.prime_val, multiplicity, weight))
}

/// Multiply a node's weight by a finite factor.
pub fn scale_weight(node: &GapTensorNode, factor: f32) -> Result<GapTensorNode, ArithmeticError> {
    let weight = node.spectral_weight * factor;
    if !factor.is_finite() || !weight.is_finite() {
        return Err(ArithmeticError::NonFiniteWeight);
    }
    Ok(GapTensorNode::new(node.prime_val, node.multiplicity, weight))
}

/// Split `count` units of multiplicity off a node. Returns `(taken,
/// remainder)`, both with the original weight; a part with zero
/// multiplicity is Nil. Merging the two parts restores the original.
pub fn split_node(
    node: &GapTensorNode,
    count: u32,
) -> Result<(GapTensorNode, GapTensorNode), ArithmeticError> {
    if count > node.multiplicity {
        return Err(ArithmeticError::InsufficientMultiplicity {
            requested: count,
            available: node.multiplicity,
        });
    }
    let part = |m: u32| {
        if m == 0 {
            GapTensorNode::NIL
        } else {
            GapTensorNode::new(node.prime_val, m, node.spectral_weight)
        }
    };
    Ok((part(count), part(node.multiplicity - count)))
}

/// Element-wise merge of two tensors of the same shape.
pub fn merge_tensors(a: &GapTensor, b: &GapTensor) -> Result<GapTensor, ArithmeticError> {
    if a.shape() != b.shape() {
        return Err(ArithmeticError::Shape(ShapeError::LengthMismatch {
            expected: a.shape().len(),
            got: b.shape().len(),
        }));
    }
    let nodes = a
        .nodes()
        .iter()
        .zip(b.nodes())
        .map(|(x, y)| merge_nodes(x, y))
        .collect::<Result<Vec<_>, _>>()?;
    GapTensor::from_nodes(a.shape().clone(), nodes).map_err(ArithmeticError::Shape)
}

/// Sum of multiplicities over all non-nil nodes.
pub fn total_multiplicity(tensor: &GapTensor) -> u64 {
    tensor
        .nodes()
        .iter()
        .filter(|n| n.is_prime())
        .map(|n| n.multiplicity as u64)
        .sum()
}

/// Sum of resonance over all non-nil nodes, accumulated in `f64`.
pub fn total_resonance(tensor: &GapTensor) -> f64 {
    tensor
        .nodes()
        .iter()
        .filter(|n| n.is_prime())
        .map(|n| n.multiplicity as f64 * n.spectral_weight as f64)
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;
    use gap_tensor_shape::TensorShape;

    #[test]
    fn merge_preserves_resonance() {
        let a = GapTensorNode::new(5, 2, 1.5);
        let b = GapTensorNode::new(5, 3, 0.5);
        let m = merge_nodes(&a, &b).unwrap();
        assert_eq!(m.multiplicity, 5);
        assert!((m.resonance() - (a.resonance() + b.resonance())).abs() < 1e-6);
    }

    #[test]
    fn merge_identity_and_errors() {
        let a = GapTensorNode::new(5, 2, 1.5);
        assert_eq!(merge_nodes(&a, &GapTensorNode::NIL).unwrap(), a);
        assert_eq!(merge_nodes(&GapTensorNode::NIL, &a).unwrap(), a);
        assert_eq!(
            merge_nodes(&a, &GapTensorNode::new(7, 1, 1.0)),
            Err(ArithmeticError::PrimeMismatch { left: 5, right: 7 })
        );
        assert_eq!(
            merge_nodes(&GapTensorNode::new(5, u32::MAX, 1.0), &a),
            Err(ArithmeticError::MultiplicityOverflow)
        );
        let zero = merge_nodes(&GapTensorNode::new(5, 0, 9.0), &GapTensorNode::new(5, 0, 3.0)).unwrap();
        assert_eq!(zero, GapTensorNode::new(5, 0, 0.0));
    }

    #[test]
    fn scaling() {
        let a = GapTensorNode::new(3, 2, 1.5);
        assert_eq!(scale_weight(&a, 2.0).unwrap().spectral_weight, 3.0);
        assert_eq!(scale_weight(&a, f32::NAN), Err(ArithmeticError::NonFiniteWeight));
        assert_eq!(scale_weight(&a, f32::MAX), Err(ArithmeticError::NonFiniteWeight));
    }

    #[test]
    fn split_then_merge_restores_node() {
        let a = GapTensorNode::new(11, 5, 0.25);
        let (taken, rest) = split_node(&a, 2).unwrap();
        assert_eq!(taken.multiplicity, 2);
        assert_eq!(rest.multiplicity, 3);
        assert_eq!(merge_nodes(&taken, &rest).unwrap(), a);
        let (all, none) = split_node(&a, 5).unwrap();
        assert_eq!(all, a);
        assert!(none.is_nil());
        assert!(split_node(&a, 6).is_err());
    }

    #[test]
    fn tensor_merge_and_totals() {
        let shape = TensorShape::vector(3).unwrap();
        let a = GapTensor::from_nodes(
            shape.clone(),
            vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL, GapTensorNode::new(3, 2, 2.0)],
        )
        .unwrap();
        let b = GapTensor::from_nodes(
            shape,
            vec![GapTensorNode::new(2, 3, 1.0), GapTensorNode::new(7, 1, 4.0), GapTensorNode::NIL],
        )
        .unwrap();
        let m = merge_tensors(&a, &b).unwrap();
        assert_eq!(total_multiplicity(&m), 7);
        assert!((total_resonance(&m) - (total_resonance(&a) + total_resonance(&b))).abs() < 1e-9);

        let other = GapTensor::nil(TensorShape::vector(4).unwrap());
        assert!(matches!(merge_tensors(&a, &other), Err(ArithmeticError::Shape(_))));
    }
}
