//! gap_candidate_set
//!
//! Manage candidate sets of primes for gap analysis.

#![warn(missing_docs)]

use std::collections::BTreeSet;
pub use prime_enumeration::{nth_prime, primes_up_to};

/// A set of candidate gap positions.
#[derive(Clone, Debug)]
pub struct GapCandidateSet {
    primes: BTreeSet<u64>,
}

impl GapCandidateSet {
    /// Create a new candidate set from a list of primes (in any order;
    /// duplicates are dropped).
    pub fn new(primes: Vec<u64>) -> Self {
        Self {
            primes: primes.into_iter().collect(),
        }
    }

    /// Create candidate set from primes up to limit.
    pub fn from_limit(limit: u64) -> Self {
        Self::new(primes_up_to(limit))
    }

    /// Get all gaps between consecutive primes.
    pub fn gaps(&self) -> Vec<u64> {
        let primes: Vec<_> = self.primes.iter().copied().collect();
        primes.windows(2).map(|w| w[1] - w[0]).collect()
    }

    /// Check if a gap size appears in the set.
    pub fn contains_gap(&self, gap_size: u64) -> bool {
        let gaps = self.gaps();
        gaps.contains(&gap_size)
    }

    /// Get candidates with gap >= min_size.
    pub fn candidates_with_gap(self, min_size: u64) -> Vec<(u64, u64, u64)> {
        let primes: Vec<_> = self.primes.iter().copied().collect();
        primes
            .windows(2)
            .filter_map(|w| {
                let gap = w[1] - w[0];
                if gap >= min_size {
                    Some((w[0], w[1], gap))
                } else {
                    None
                }
            })
            .collect()
    }

    /// Count distinct gap sizes.
    pub fn gap_count(&self) -> usize {
        let mut gaps = self.gaps();
        gaps.sort();
        gaps.dedup();
        gaps.len()
    }

    /// Get minimum gap size (0 when there are fewer than two primes).
    pub fn min_gap(&self) -> u64 {
        self.gaps().into_iter().min().unwrap_or(0)
    }

    /// Get maximum gap size (0 when there are fewer than two primes).
    pub fn max_gap(&self) -> u64 {
        self.gaps().into_iter().max().unwrap_or(0)
    }

    /// Number of primes in the set.
    pub fn len(&self) -> usize {
        self.primes.len()
    }

    /// Check if set is empty.
    pub fn is_empty(&self) -> bool {
        self.primes.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gap_candidate_set_creation() {
        let set = GapCandidateSet::new(vec![2, 3, 5, 7, 11]);
        assert_eq!(set.len(), 5);
        assert!(!set.is_empty());
    }

    #[test]
    fn test_gaps() {
        let set = GapCandidateSet::new(vec![2, 3, 5, 7, 11, 13]);
        let gaps = set.gaps();
        assert_eq!(gaps, vec![1, 2, 2, 4, 2]);
    }

    #[test]
    fn test_contains_gap() {
        let set = GapCandidateSet::new(vec![2, 3, 5, 7, 11, 13]);
        assert!(set.contains_gap(1));
        assert!(set.contains_gap(2));
        assert!(set.contains_gap(4));
        assert!(!set.contains_gap(5));
    }

    #[test]
    fn test_min_max_gap() {
        let set = GapCandidateSet::new(vec![2, 3, 5, 7, 11, 13]);
        assert_eq!(set.min_gap(), 1);
        assert_eq!(set.max_gap(), 4);
    }

    #[test]
    fn gaps_use_the_sorted_set() {
        let set = GapCandidateSet::new(vec![7, 3, 5, 3, 2]);
        assert_eq!(set.gaps(), vec![1, 2, 2]);
        assert_eq!((set.min_gap(), set.max_gap()), (1, 2));
        let single = GapCandidateSet::new(vec![7]);
        assert_eq!((single.min_gap(), single.max_gap()), (0, 0));
    }

    #[test]
    fn test_candidates_with_gap() {
        let set = GapCandidateSet::new(vec![2, 3, 5, 7, 11, 13]);
        let candidates = set.candidates_with_gap(2);
        assert!(candidates.len() > 0);
        for (_, _, gap) in &candidates {
            assert!(*gap >= 2);
        }
    }
}
