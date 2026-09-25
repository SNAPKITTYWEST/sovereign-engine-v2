//! gap_ordering
//!
//! Ordering and sorting operations for prime gaps.

#![warn(missing_docs)]

pub use gap_candidate_set::{GapCandidateSet};

/// Different orderings for gaps.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GapOrdering {
    /// Sort by gap size ascending
    SizeAscending,
    /// Sort by gap size descending
    SizeDescending,
    /// Sort by first prime ascending
    PrimeAscending,
    /// Sort by first prime descending
    PrimeDescending,
}

/// Order a set of gap candidates.
pub fn order_gaps(
    candidates: Vec<(u64, u64, u64)>,
    ordering: GapOrdering,
) -> Vec<(u64, u64, u64)> {
    let mut sorted = candidates;
    match ordering {
        GapOrdering::SizeAscending => sorted.sort_by_key(|&(_, _, gap)| gap),
        GapOrdering::SizeDescending => sorted.sort_by(|a, b| b.2.cmp(&a.2)),
        GapOrdering::PrimeAscending => sorted.sort_by_key(|&(p, _, _)| p),
        GapOrdering::PrimeDescending => sorted.sort_by(|a, b| b.0.cmp(&a.0)),
    }
    sorted
}

/// Get the k-largest gaps.
pub fn top_k_gaps(candidates: Vec<(u64, u64, u64)>, k: usize) -> Vec<(u64, u64, u64)> {
    let mut sorted = candidates;
    sorted.sort_by(|a, b| b.2.cmp(&a.2));
    sorted.truncate(k);
    sorted
}

/// Get gaps in a specific range.
pub fn gaps_in_range(
    candidates: Vec<(u64, u64, u64)>,
    min: u64,
    max: u64,
) -> Vec<(u64, u64, u64)> {
    candidates
        .into_iter()
        .filter(|&(_, _, gap)| gap >= min && gap <= max)
        .collect()
}

/// Create a histogram of gap sizes.
pub fn gap_histogram(candidates: &[(u64, u64, u64)]) -> std::collections::BTreeMap<u64, usize> {
    let mut hist = std::collections::BTreeMap::new();
    for &(_, _, gap) in candidates {
        *hist.entry(gap).or_insert(0) += 1;
    }
    hist
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_order_gaps_by_size() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let ordered = order_gaps(candidates.clone(), GapOrdering::SizeAscending);
        assert_eq!(ordered[0].2, 1);
        assert_eq!(ordered[ordered.len() - 1].2, 4);
    }

    #[test]
    fn test_top_k_gaps() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let top = top_k_gaps(candidates, 2);
        assert_eq!(top.len(), 2);
        assert_eq!(top[0].2, 4);
    }

    #[test]
    fn test_gaps_in_range() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let filtered = gaps_in_range(candidates, 2, 3);
        assert!(filtered.iter().all(|&(_, _, gap)| gap >= 2 && gap <= 3));
    }

    #[test]
    fn test_gap_histogram() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let hist = gap_histogram(&candidates);
        assert_eq!(hist[&1], 1);
        assert_eq!(hist[&2], 2);
        assert_eq!(hist[&4], 1);
    }
}
