//! gap_tensor_ordering
//!
//! A lawful total order on gap tensor nodes and ordering utilities built on
//! it.
//!
//! `GapTensorNode`'s own `Ord` treats incomparable spectral weights (NaN) as
//! equal, which is not a total order. [`canonical_cmp`] instead compares
//! weights with `f32::total_cmp`, so it is total and agrees exactly with
//! `EqualityMode::Exact`.

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;
use gap_tensor_equality::{nodes_equal, EqualityMode};
use std::cmp::Ordering;

/// Total order: prime, then multiplicity, then weight by IEEE total order.
pub fn canonical_cmp(a: &GapTensorNode, b: &GapTensorNode) -> Ordering {
    a.prime_val
        .cmp(&b.prime_val)
        .then(a.multiplicity.cmp(&b.multiplicity))
        .then(a.spectral_weight.total_cmp(&b.spectral_weight))
}

/// Order by resonance (IEEE total order), falling back to [`canonical_cmp`].
pub fn resonance_cmp(a: &GapTensorNode, b: &GapTensorNode) -> Ordering {
    a.resonance()
        .total_cmp(&b.resonance())
        .then_with(|| canonical_cmp(a, b))
}

/// Sort nodes into canonical order.
pub fn sort_canonical(nodes: &mut [GapTensorNode]) {
    nodes.sort_by(canonical_cmp);
}

/// True iff `nodes` is in non-decreasing canonical order.
pub fn is_sorted_canonical(nodes: &[GapTensorNode]) -> bool {
    nodes
        .windows(2)
        .all(|w| canonical_cmp(&w[0], &w[1]) != Ordering::Greater)
}

/// Indices of `nodes` ordered by descending resonance; ties keep canonical
/// order.
pub fn rank_by_resonance(nodes: &[GapTensorNode]) -> Vec<usize> {
    let mut indices: Vec<usize> = (0..nodes.len()).collect();
    indices.sort_by(|&i, &j| {
        nodes[j]
            .resonance()
            .total_cmp(&nodes[i].resonance())
            .then_with(|| canonical_cmp(&nodes[i], &nodes[j]))
            .then(i.cmp(&j))
    });
    indices
}

/// Remove consecutive exact duplicates. On a canonically sorted vector this
/// removes all exact duplicates.
pub fn dedup_exact(nodes: &mut Vec<GapTensorNode>) {
    nodes.dedup_by(|a, b| nodes_equal(a, b, EqualityMode::Exact));
}

/// Merge two canonically sorted slices into one sorted vector.
pub fn merge_sorted(a: &[GapTensorNode], b: &[GapTensorNode]) -> Vec<GapTensorNode> {
    let mut out = Vec::with_capacity(a.len() + b.len());
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {
        if canonical_cmp(&a[i], &b[j]) != Ordering::Greater {
            out.push(a[i]);
            i += 1;
        } else {
            out.push(b[j]);
            j += 1;
        }
    }
    out.extend_from_slice(&a[i..]);
    out.extend_from_slice(&b[j..]);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_order_is_total_and_matches_exact_equality() {
        let nan = GapTensorNode::new(3, 1, f32::NAN);
        assert_eq!(canonical_cmp(&nan, &nan), Ordering::Equal);
        let pos = GapTensorNode::new(3, 1, 0.0);
        let neg = GapTensorNode::new(3, 1, -0.0);
        assert_eq!(canonical_cmp(&neg, &pos), Ordering::Less);
        assert!(!nodes_equal(&neg, &pos, EqualityMode::Exact));
        assert_eq!(
            canonical_cmp(&GapTensorNode::new(2, 9, 9.0), &GapTensorNode::new(3, 1, 0.0)),
            Ordering::Less
        );
    }

    #[test]
    fn sort_and_check() {
        let mut nodes = vec![
            GapTensorNode::new(5, 1, 1.0),
            GapTensorNode::new(2, 2, 1.0),
            GapTensorNode::new(2, 1, 3.0),
            GapTensorNode::new(2, 1, f32::NAN),
        ];
        assert!(!is_sorted_canonical(&nodes));
        sort_canonical(&mut nodes);
        assert!(is_sorted_canonical(&nodes));
        assert_eq!(nodes[0], GapTensorNode::new(2, 1, 3.0));
        assert!(nodes[1].spectral_weight.is_nan());
        assert_eq!(nodes[3].prime_val, 5);
    }

    #[test]
    fn resonance_ranking() {
        let nodes = [
            GapTensorNode::new(2, 1, 1.0),
            GapTensorNode::new(3, 4, 1.0),
            GapTensorNode::new(5, 2, 1.0),
            GapTensorNode::new(7, 2, 1.0),
        ];
        assert_eq!(rank_by_resonance(&nodes), vec![1, 2, 3, 0]);
        assert_eq!(resonance_cmp(&nodes[0], &nodes[1]), Ordering::Less);
    }

    #[test]
    fn dedup_and_merge() {
        let mut nodes = vec![
            GapTensorNode::new(2, 1, 1.0),
            GapTensorNode::new(2, 1, 1.0),
            GapTensorNode::new(3, 1, 0.0),
            GapTensorNode::new(3, 1, -0.0),
        ];
        sort_canonical(&mut nodes);
        dedup_exact(&mut nodes);
        assert_eq!(nodes.len(), 3);

        let a = [GapTensorNode::new(2, 1, 1.0), GapTensorNode::new(7, 1, 1.0)];
        let b = [GapTensorNode::new(3, 1, 1.0), GapTensorNode::new(11, 1, 1.0)];
        let merged = merge_sorted(&a, &b);
        assert!(is_sorted_canonical(&merged));
        assert_eq!(merged.len(), 4);
    }
}
