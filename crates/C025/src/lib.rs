//! gap_multiplicity
//!
//! Analyze frequency and multiplicity of prime gaps.

#![warn(missing_docs)]

use std::collections::BTreeMap;
pub use gap_candidate_set::GapCandidateSet;
pub use gap_ordering::{order_gaps, GapOrdering};

/// Multiplicity information for a gap size.
#[derive(Clone, Debug)]
pub struct GapMultiplicity {
    /// Gap size
    pub gap_size: u64,
    /// Number of occurrences
    pub count: usize,
    /// Positions where this gap occurs (as first prime)
    pub positions: Vec<u64>,
}

/// Analyze gap multiplicity in a candidate set.
pub fn analyze_gaps(candidates: &[(u64, u64, u64)]) -> Vec<GapMultiplicity> {
    let mut gap_map: BTreeMap<u64, Vec<u64>> = BTreeMap::new();

    for &(p, _, gap) in candidates {
        gap_map.entry(gap).or_insert_with(Vec::new).push(p);
    }

    gap_map
        .into_iter()
        .map(|(gap_size, positions)| GapMultiplicity {
            gap_size,
            count: positions.len(),
            positions,
        })
        .collect()
}

/// Get the most common gap sizes.
pub fn most_common_gaps(candidates: &[(u64, u64, u64)], k: usize) -> Vec<GapMultiplicity> {
    let mut multiplicities = analyze_gaps(candidates);
    multiplicities.sort_by(|a, b| b.count.cmp(&a.count));
    multiplicities.truncate(k);
    multiplicities
}

/// Calculate average gap size.
pub fn average_gap(candidates: &[(u64, u64, u64)]) -> f64 {
    if candidates.is_empty() {
        return 0.0;
    }
    let sum: u64 = candidates.iter().map(|&(_, _, g)| g).sum();
    sum as f64 / candidates.len() as f64
}

/// Calculate standard deviation of gap sizes.
pub fn gap_std_dev(candidates: &[(u64, u64, u64)]) -> f64 {
    if candidates.len() < 2 {
        return 0.0;
    }
    let avg = average_gap(candidates);
    let variance: f64 = candidates
        .iter()
        .map(|&(_, _, g)| {
            let diff = g as f64 - avg;
            diff * diff
        })
        .sum::<f64>()
        / (candidates.len() - 1) as f64;
    variance.sqrt()
}

/// Check if a gap is anomalous (> mean + 2*std_dev).
pub fn is_anomalous_gap(gap: u64, candidates: &[(u64, u64, u64)]) -> bool {
    let mean = average_gap(candidates);
    let std_dev = gap_std_dev(candidates);
    (gap as f64) > mean + 2.0 * std_dev
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_analyze_gaps() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let multiplicities = analyze_gaps(&candidates);
        assert!(multiplicities.len() > 0);
        // Gap size 2 should appear twice
        let gap_2 = multiplicities.iter().find(|m| m.gap_size == 2).unwrap();
        assert_eq!(gap_2.count, 2);
    }

    #[test]
    fn test_most_common_gaps() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let common = most_common_gaps(&candidates, 2);
        assert_eq!(common.len(), 2);
        assert!(common[0].count >= common[1].count);
    }

    #[test]
    fn test_average_gap() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let avg = average_gap(&candidates);
        assert!(avg > 0.0 && avg < 5.0);
    }

    #[test]
    fn test_gap_std_dev() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let std_dev = gap_std_dev(&candidates);
        assert!(std_dev >= 0.0);
    }
}
