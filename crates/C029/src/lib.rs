//! prime_gap_relationship
//!
//! Relate prime numbers to their gaps and establish relationships.

#![warn(missing_docs)]

pub use prime_predicate::is_prime;
pub use prime_enumeration::{primes_up_to, nth_prime};
pub use gap_candidate_set::GapCandidateSet;

/// Information about a prime and its surrounding gap.
#[derive(Clone, Debug)]
pub struct PrimeGapPair {
    /// The prime number
    pub prime: u64,
    /// The next prime
    pub next_prime: u64,
    /// Gap between prime and next_prime
    pub gap: u64,
}

impl PrimeGapPair {
    /// Is this the first pair (smallest prime) in `pairs` with this gap?
    pub fn is_first_occurrence(&self, pairs: &[PrimeGapPair]) -> bool {
        !pairs.iter().any(|q| q.prime < self.prime && q.gap == self.gap)
    }

    /// Gap normalized by `ln(prime)`, the average gap size near `prime`.
    pub fn normalized_gap(&self) -> f64 {
        self.gap as f64 / (self.prime as f64).ln()
    }
}

/// Construct prime-gap relationships for all primes up to limit.
pub fn prime_gap_pairs(limit: u64) -> Vec<PrimeGapPair> {
    let primes = primes_up_to(limit);
    primes
        .windows(2)
        .map(|w| PrimeGapPair {
            prime: w[0],
            next_prime: w[1],
            gap: w[1] - w[0],
        })
        .collect()
}

/// Find all primes with a specific gap size.
pub fn primes_with_gap(pairs: &[PrimeGapPair], gap_size: u64) -> Vec<u64> {
    pairs
        .iter()
        .filter(|p| p.gap == gap_size)
        .map(|p| p.prime)
        .collect()
}

/// Find the largest gap in a range.
pub fn largest_gap_in_range(pairs: &[PrimeGapPair], start: u64, end: u64) -> Option<PrimeGapPair> {
    pairs
        .iter()
        .filter(|p| p.prime >= start && p.prime <= end)
        .max_by_key(|p| p.gap)
        .cloned()
}

/// Get the maximal gap (first gap of each size).
pub fn maximal_gaps(pairs: &[PrimeGapPair]) -> Vec<PrimeGapPair> {
    let mut seen_gaps = std::collections::BTreeSet::new();
    pairs
        .iter()
        .filter(|p| {
            if seen_gaps.contains(&p.gap) {
                false
            } else {
                seen_gaps.insert(p.gap);
                true
            }
        })
        .cloned()
        .collect()
}

/// Compute the ratio of gap to log(prime).
pub fn gap_ratios(pairs: &[PrimeGapPair]) -> Vec<f64> {
    pairs
        .iter()
        .map(|p| p.gap as f64 / (p.prime as f64).ln())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_prime_gap_pair_normalized() {
        let pair = PrimeGapPair {
            prime: 100,
            next_prime: 104,
            gap: 4,
        };
        let normalized = pair.normalized_gap();
        assert!(normalized > 0.0);
    }

    #[test]
    fn first_occurrence_of_gaps() {
        let pairs = prime_gap_pairs(100);
        let find = |p: u64| pairs.iter().find(|x| x.prime == p).unwrap().clone();
        assert!(find(2).is_first_occurrence(&pairs));
        assert!(find(3).is_first_occurrence(&pairs));
        assert!(!find(5).is_first_occurrence(&pairs));
        assert!(find(7).is_first_occurrence(&pairs));
        assert!(!find(13).is_first_occurrence(&pairs));
        assert!(find(23).is_first_occurrence(&pairs));
        assert!(find(89).is_first_occurrence(&pairs));
    }

    #[test]
    fn test_prime_gap_pairs() {
        let pairs = prime_gap_pairs(30);
        assert!(pairs.len() > 0);
        for pair in &pairs {
            assert!(pair.next_prime > pair.prime);
            assert_eq!(pair.gap, pair.next_prime - pair.prime);
        }
    }

    #[test]
    fn test_primes_with_gap() {
        let pairs = prime_gap_pairs(30);
        let primes_with_gap_2 = primes_with_gap(&pairs, 2);
        assert!(!primes_with_gap_2.is_empty());
    }

    #[test]
    fn test_largest_gap_in_range() {
        let pairs = prime_gap_pairs(30);
        let largest = largest_gap_in_range(&pairs, 5, 20);
        assert!(largest.is_some());
    }

    #[test]
    fn test_maximal_gaps() {
        let pairs = prime_gap_pairs(30);
        let maximal = maximal_gaps(&pairs);
        // Each gap size should appear only once
        let mut gaps = maximal.iter().map(|p| p.gap).collect::<Vec<_>>();
        gaps.sort();
        gaps.dedup();
        assert_eq!(gaps.len(), maximal.len());
    }

    #[test]
    fn test_gap_ratios() {
        let pairs = prime_gap_pairs(30);
        let ratios = gap_ratios(&pairs);
        assert_eq!(ratios.len(), pairs.len());
        assert!(ratios.iter().all(|&r| r >= 0.0));
    }
}
