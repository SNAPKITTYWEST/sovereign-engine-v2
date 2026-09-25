//! tensor_homology_correspondence
//!
//! Correspondence between the dissonance invariant of a gap tensor (Tier 0)
//! and homology (Tier 4). The *consonance path complex* of a tensor has one
//! vertex per non-nil node (in order) and an edge between consecutive
//! non-nil nodes whose primes differ by at most the gap bound, with
//! `d(edge) = v_{k+1} − v_k`. It is a disjoint union of paths, so
//!
//! * `rank H₀` = number of path components = `1 + #dissonances` (0 if every
//!   node is Nil), and
//! * `H₁ = 0`.
//!
//! [`check_dissonance_equals_path_components`] verifies this with the
//! Smith-normal-form homology of Tier 4 over a family of tensors.

#![warn(missing_docs)]

use cross_layer_types::{check_tensor, CorrespondenceReport, GapTensor, Violation, SIGMA_GAP_MAX};
use homology_computation::{ChainComplexShape, DifferentialOperator, HomologyComputer};

/// The consonance path complex of `tensor` for gap bound `max_gap`.
pub fn path_complex(tensor: &GapTensor, max_gap: u32) -> DifferentialOperator {
    let primes: Vec<u32> = tensor.nodes().iter().filter(|n| n.is_prime()).map(|n| n.prime_val).collect();
    let edges: Vec<usize> = (0..primes.len().saturating_sub(1))
        .filter(|&k| primes[k].abs_diff(primes[k + 1]) <= max_gap)
        .collect();
    let mut diff = DifferentialOperator::new(ChainComplexShape::from_ranks(vec![(0, primes.len()), (1, edges.len())]));
    for (e, &k) in edges.iter().enumerate() {
        diff.set_generator_image(1, e, 0, vec![(k, -1), (k + 1, 1)]);
    }
    diff
}

/// Check `rank H₀ = 1 + #dissonances` and `H₁ = 0` for every tensor, using
/// gap bound `max_gap` for the complex (the invariant always uses
/// `SIGMA_GAP_MAX`).
pub fn check_dissonance_equals_path_components_with(family: &[GapTensor], max_gap: u32) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("dissonance_equals_path_components");
    for (i, tensor) in family.iter().enumerate() {
        let vertices = tensor.nodes().iter().filter(|n| n.is_prime()).count();
        let dissonances = check_tensor(tensor)
            .violations
            .iter()
            .filter(|v| matches!(v, Violation::Dissonance { .. }))
            .count();
        match HomologyComputer::compute_all(&path_complex(tensor, max_gap)) {
            Ok(h) => {
                let h0 = h.group_at(0).map_or(0, |g| g.rank);
                let h1_trivial = h.group_at(1).map_or(true, |g| g.is_trivial());
                let expected = if vertices == 0 { 0 } else { 1 + dissonances };
                report.check(h0 == expected && h1_trivial, || {
                    format!("tensor {i}: rank H₀ = {h0}, expected {expected}")
                });
            }
            Err(e) => report.error(format!("tensor {i}: {e}")),
        }
    }
    report
}

/// The real check (gap bound `SIGMA_GAP_MAX`).
pub fn check_dissonance_equals_path_components(family: &[GapTensor]) -> CorrespondenceReport {
    check_dissonance_equals_path_components_with(family, SIGMA_GAP_MAX)
}

#[cfg(test)]
mod tests {
    use super::*;
    use cross_layer_types::{standard_family, vector_state, GapTensorNode};

    #[test]
    fn path_complex_shape() {
        let t = vector_state(vec![
            GapTensorNode::new(2, 1, 1.0),
            GapTensorNode::NIL,
            GapTensorNode::new(3, 1, 1.0),
            GapTensorNode::new(13, 1, 1.0),
        ]);
        let d = path_complex(&t, SIGMA_GAP_MAX);
        assert_eq!((d.source_rank(0), d.source_rank(1)), (3, 1));
        let h = HomologyComputer::compute_all(&d).unwrap();
        assert_eq!(h.group_at(0).unwrap().rank, 2);
    }

    #[test]
    fn correspondence_holds_on_the_standard_family() {
        let report = check_dissonance_equals_path_components(&standard_family());
        assert!(report.holds(), "{:?}", report.failures);
        assert_eq!(report.cases_checked, 258);
    }

    #[test]
    fn wrong_gap_bound_is_caught() {
        assert!(!check_dissonance_equals_path_components_with(&standard_family(), 4).holds());
    }
}
