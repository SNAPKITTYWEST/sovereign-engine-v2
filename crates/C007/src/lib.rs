//! gap_tensor_invariants
//!
//! Well-formedness invariants for gap tensor nodes and tensors:
//!
//! * a non-nil node carries a candidate prime;
//! * a Nil node is clean (zero multiplicity and zero weight);
//! * spectral weights are finite and non-negative;
//! * consecutive non-nil nodes (in row-major order) differ in prime by at most
//!   `SIGMA_GAP_MAX` — a larger jump is dissonance.

#![warn(missing_docs)]

use gap_tensor_core::{GapTensorNode, SIGMA_GAP_MAX};
use gap_tensor_primes::is_candidate_prime;
use gap_tensor_shape::GapTensor;

/// A single invariant violation, located by flat node index.
#[derive(Debug, Clone, PartialEq)]
pub enum Violation {
    /// A non-nil node whose prime is not a candidate prime.
    NonCandidatePrime {
        /// Node index.
        index: usize,
        /// Offending prime.
        prime: u32,
    },
    /// A Nil node with non-zero multiplicity or weight.
    DirtyNil {
        /// Node index.
        index: usize,
    },
    /// A spectral weight that is NaN, infinite or negative.
    InvalidWeight {
        /// Node index.
        index: usize,
        /// Offending weight.
        weight: f32,
    },
    /// A non-nil node whose prime differs from the previous non-nil node's
    /// prime by more than `SIGMA_GAP_MAX`.
    Dissonance {
        /// Index of the later node.
        index: usize,
        /// Size of the jump.
        gap: u32,
    },
}

/// Result of checking a node sequence.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct InvariantReport {
    /// Number of nodes checked.
    pub checked: usize,
    /// All violations found, in index order.
    pub violations: Vec<Violation>,
}

impl InvariantReport {
    /// True iff no violations were found.
    pub fn is_valid(&self) -> bool {
        self.violations.is_empty()
    }
}

/// Node-local invariants for the node at `index`.
pub fn check_node(index: usize, node: &GapTensorNode) -> Vec<Violation> {
    let mut violations = Vec::new();
    if node.is_nil() {
        if node.multiplicity != 0 || node.spectral_weight.to_bits() != 0 {
            violations.push(Violation::DirtyNil { index });
        }
        return violations;
    }
    if !is_candidate_prime(node.prime_val) {
        violations.push(Violation::NonCandidatePrime {
            index,
            prime: node.prime_val,
        });
    }
    let w = node.spectral_weight;
    if !w.is_finite() || w < 0.0 {
        violations.push(Violation::InvalidWeight { index, weight: w });
    }
    violations
}

/// Check every node-local invariant plus dissonance between consecutive
/// non-nil nodes.
pub fn check_nodes(nodes: &[GapTensorNode]) -> InvariantReport {
    let mut report = InvariantReport {
        checked: nodes.len(),
        violations: Vec::new(),
    };
    let mut previous_prime: Option<u32> = None;
    for (index, node) in nodes.iter().enumerate() {
        report.violations.extend(check_node(index, node));
        if let Some(prime) = node.prime_opt() {
            if let Some(prev) = previous_prime {
                let gap = prime.abs_diff(prev);
                if gap > SIGMA_GAP_MAX {
                    report.violations.push(Violation::Dissonance { index, gap });
                }
            }
            previous_prime = Some(prime);
        }
    }
    report
}

/// Check a tensor's nodes in row-major order.
pub fn check_tensor(tensor: &GapTensor) -> InvariantReport {
    check_nodes(tensor.nodes())
}

#[cfg(test)]
mod tests {
    use super::*;
    use gap_tensor_shape::TensorShape;

    #[test]
    fn valid_tensor_passes() {
        let t = GapTensor::from_nodes(
            TensorShape::vector(4).unwrap(),
            vec![
                GapTensorNode::new(2, 1, 1.0),
                GapTensorNode::NIL,
                GapTensorNode::new(7, 2, 0.5),
                GapTensorNode::new(13, 1, 0.0),
            ],
        )
        .unwrap();
        let report = check_tensor(&t);
        assert!(report.is_valid(), "{:?}", report.violations);
        assert_eq!(report.checked, 4);
    }

    #[test]
    fn node_local_violations() {
        assert_eq!(
            check_node(0, &GapTensorNode::new(4, 1, 1.0)),
            vec![Violation::NonCandidatePrime { index: 0, prime: 4 }]
        );
        assert_eq!(
            check_node(1, &GapTensorNode::new(0, 3, 0.0)),
            vec![Violation::DirtyNil { index: 1 }]
        );
        assert_eq!(
            check_node(2, &GapTensorNode::new(0, 0, -0.0)),
            vec![Violation::DirtyNil { index: 2 }]
        );
        assert!(matches!(
            check_node(3, &GapTensorNode::new(3, 1, f32::NAN))[..],
            [Violation::InvalidWeight { index: 3, .. }]
        ));
        assert_eq!(
            check_node(4, &GapTensorNode::new(3, 1, -1.0)),
            vec![Violation::InvalidWeight { index: 4, weight: -1.0 }]
        );
    }

    #[test]
    fn dissonance_skips_nil_nodes() {
        let nodes = [
            GapTensorNode::new(2, 1, 1.0),
            GapTensorNode::NIL,
            GapTensorNode::new(13, 1, 1.0),
            GapTensorNode::new(11, 1, 1.0),
        ];
        let report = check_nodes(&nodes);
        assert_eq!(report.violations, vec![Violation::Dissonance { index: 2, gap: 11 }]);
    }
}
