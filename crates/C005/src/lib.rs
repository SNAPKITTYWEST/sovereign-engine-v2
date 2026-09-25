//! gap_tensor_equality
//!
//! Equality semantics for gap tensor nodes and tensors: exact (bitwise on
//! spectral weight), approximate (weight tolerance) and structural (weight
//! ignored).

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;
use gap_tensor_shape::GapTensor;

/// How spectral weights are compared. Primes and multiplicities must always
/// match exactly.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum EqualityMode {
    /// Weights compared by IEEE-754 bit pattern. This is the equality that is
    /// consistent with `GapTensorNode`'s `Hash`: `0.0` and `-0.0` differ, and a
    /// NaN equals itself.
    Exact,
    /// Weights equal within an absolute tolerance. NaN never matches;
    /// identical infinities do.
    Approximate(f32),
    /// Weights ignored.
    Structural,
}

/// Errors from tensor comparison.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EqualityError {
    /// The tensors have different shapes.
    ShapeMismatch {
        /// Dimensions of the left tensor.
        left: Vec<usize>,
        /// Dimensions of the right tensor.
        right: Vec<usize>,
    },
}

/// Compare two nodes under `mode`.
pub fn nodes_equal(a: &GapTensorNode, b: &GapTensorNode, mode: EqualityMode) -> bool {
    if a.prime_val != b.prime_val || a.multiplicity != b.multiplicity {
        return false;
    }
    let (x, y) = (a.spectral_weight, b.spectral_weight);
    match mode {
        EqualityMode::Exact => x.to_bits() == y.to_bits(),
        EqualityMode::Approximate(tolerance) => {
            if x.is_nan() || y.is_nan() {
                false
            } else if x == y {
                true
            } else {
                (x - y).abs() <= tolerance
            }
        }
        EqualityMode::Structural => true,
    }
}

fn check_shapes(a: &GapTensor, b: &GapTensor) -> Result<(), EqualityError> {
    if a.shape() != b.shape() {
        return Err(EqualityError::ShapeMismatch {
            left: a.shape().dims().to_vec(),
            right: b.shape().dims().to_vec(),
        });
    }
    Ok(())
}

/// Flat index of the first node that differs under `mode`, or `None` if the
/// tensors are equal.
pub fn first_difference(
    a: &GapTensor,
    b: &GapTensor,
    mode: EqualityMode,
) -> Result<Option<usize>, EqualityError> {
    check_shapes(a, b)?;
    Ok(a
        .nodes()
        .iter()
        .zip(b.nodes())
        .position(|(x, y)| !nodes_equal(x, y, mode)))
}

/// Number of nodes that differ under `mode`.
pub fn count_differences(
    a: &GapTensor,
    b: &GapTensor,
    mode: EqualityMode,
) -> Result<usize, EqualityError> {
    check_shapes(a, b)?;
    Ok(a
        .nodes()
        .iter()
        .zip(b.nodes())
        .filter(|(x, y)| !nodes_equal(x, y, mode))
        .count())
}

/// True iff the tensors have the same shape and all nodes are equal under
/// `mode`.
pub fn tensors_equal(a: &GapTensor, b: &GapTensor, mode: EqualityMode) -> bool {
    matches!(first_difference(a, b, mode), Ok(None))
}

#[cfg(test)]
mod tests {
    use super::*;
    use gap_tensor_shape::TensorShape;

    fn node(w: f32) -> GapTensorNode {
        GapTensorNode::new(3, 2, w)
    }

    #[test]
    fn exact_is_bitwise() {
        assert!(nodes_equal(&node(1.5), &node(1.5), EqualityMode::Exact));
        assert!(!nodes_equal(&node(0.0), &node(-0.0), EqualityMode::Exact));
        assert!(nodes_equal(&node(f32::NAN), &node(f32::NAN), EqualityMode::Exact));
    }

    #[test]
    fn approximate_uses_tolerance() {
        let mode = EqualityMode::Approximate(1e-3);
        assert!(nodes_equal(&node(1.0), &node(1.0005), mode));
        assert!(!nodes_equal(&node(1.0), &node(1.01), mode));
        assert!(!nodes_equal(&node(f32::NAN), &node(f32::NAN), mode));
        assert!(nodes_equal(&node(f32::INFINITY), &node(f32::INFINITY), mode));
        assert!(nodes_equal(&node(0.0), &node(-0.0), mode));
    }

    #[test]
    fn structural_ignores_weight_but_not_prime_or_multiplicity() {
        assert!(nodes_equal(&node(1.0), &node(9.0), EqualityMode::Structural));
        let other_prime = GapTensorNode::new(5, 2, 1.0);
        let other_mult = GapTensorNode::new(3, 3, 1.0);
        assert!(!nodes_equal(&node(1.0), &other_prime, EqualityMode::Structural));
        assert!(!nodes_equal(&node(1.0), &other_mult, EqualityMode::Structural));
    }

    #[test]
    fn tensor_comparison() {
        let shape = TensorShape::vector(3).unwrap();
        let a = GapTensor::from_nodes(shape.clone(), vec![node(1.0), node(2.0), node(3.0)]).unwrap();
        let b = GapTensor::from_nodes(shape, vec![node(1.0), node(2.5), node(3.5)]).unwrap();
        assert!(tensors_equal(&a, &a, EqualityMode::Exact));
        assert_eq!(first_difference(&a, &b, EqualityMode::Exact), Ok(Some(1)));
        assert_eq!(count_differences(&a, &b, EqualityMode::Exact), Ok(2));
        assert!(tensors_equal(&a, &b, EqualityMode::Structural));
    }

    #[test]
    fn shape_mismatch_is_reported() {
        let a = GapTensor::nil(TensorShape::vector(6).unwrap());
        let b = GapTensor::nil(TensorShape::matrix(2, 3).unwrap());
        assert!(!tensors_equal(&a, &b, EqualityMode::Structural));
        assert_eq!(
            first_difference(&a, &b, EqualityMode::Exact),
            Err(EqualityError::ShapeMismatch { left: vec![6], right: vec![2, 3] })
        );
    }
}
