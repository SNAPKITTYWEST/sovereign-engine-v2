//! prime_gap_tests_integration
//!
//! Integration tests for Tier 2 prime/gap engine.

#![warn(missing_docs)]

pub use prime_predicate::is_prime;
pub use prime_enumeration::{primes_up_to, nth_prime, prime_count};
pub use gap_candidate_set::GapCandidateSet;
pub use gap_ordering::{order_gaps, GapOrdering};
pub use gap_multiplicity::analyze_gaps;
pub use gap_constraint_satisfaction::GapConstraint;
pub use gap_verification::{verify_all_gaps, VerificationResult};
pub use prime_gap_relationship::{prime_gap_pairs, maximal_gaps, PrimeGapPair};

/// Run a complete Tier 2 integration test.
pub fn tier2_integration_test() -> bool {
    // 1. Generate primes
    let primes = primes_up_to(100);
    if primes.len() < 10 {
        return false;
    }

    // 2. Create candidate set
    let candidate_set = GapCandidateSet::from_limit(100);
    let candidates = candidate_set.candidates_with_gap(1);
    if candidates.is_empty() {
        return false;
    }

    // 3. Verify gaps
    let constraint = GapConstraint::range(1, 10);
    let verification = verify_all_gaps(&candidates, &constraint);
    if !verification.is_good() {
        return false;
    }

    // 4. Analyze multiplicity
    let multiplicities = analyze_gaps(&candidates);
    if multiplicities.is_empty() {
        return false;
    }

    // 5. Check prime-gap relationships
    let pairs = prime_gap_pairs(100);
    if pairs.len() < candidates.len() {
        return false;
    }

    // 6. Get maximal gaps
    let _maximal = maximal_gaps(&pairs);

    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tier2_primes_generated() {
        let primes = primes_up_to(50);
        assert!(primes.len() > 0);
        assert!(primes.iter().all(|&p| is_prime(p)));
    }

    #[test]
    fn test_tier2_candidate_set() {
        let set = GapCandidateSet::from_limit(50);
        assert!(!set.is_empty());
        let gaps = set.gaps();
        assert!(!gaps.is_empty());
    }

    #[test]
    fn test_tier2_gap_ordering() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let ordered = order_gaps(candidates, GapOrdering::SizeDescending);
        assert_eq!(ordered[0].2, 4);
    }

    #[test]
    fn test_tier2_gap_multiplicity() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let mults = analyze_gaps(&candidates);
        let gap_2 = mults.iter().find(|m| m.gap_size == 2).unwrap();
        assert_eq!(gap_2.count, 2);
    }

    #[test]
    fn test_tier2_verification() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let constraint = GapConstraint::range(1, 5);
        let result = verify_all_gaps(&candidates, &constraint);
        assert!(result.all_passed());
    }

    #[test]
    fn test_tier2_prime_gap_pairs() {
        let pairs = prime_gap_pairs(50);
        assert!(!pairs.is_empty());
        for pair in &pairs {
            assert!(is_prime(pair.prime));
            assert!(is_prime(pair.next_prime));
        }
    }

    #[test]
    fn test_tier2_integration() {
        assert!(tier2_integration_test());
    }
}
