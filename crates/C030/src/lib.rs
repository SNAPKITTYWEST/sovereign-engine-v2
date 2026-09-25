//! prime_gap_tests_integration
//!
//! End-to-end scenarios across the Tier 2 prime/gap engine (C021–C029),
//! checked against exact facts about the 25 primes up to 100: π(100) = 25,
//! gap counts {1: 1, 2: 8, 4: 7, 6: 7, 8: 1}, and gaps summing to
//! 97 − 2 = 95. [`run_prime_gap_integration`] returns a per-scenario report
//! so a failure says which scenario broke and why.

#![warn(missing_docs)]

pub use prime_predicate::is_prime;
pub use prime_enumeration::{primes_up_to, nth_prime, prime_count};
pub use gap_candidate_set::GapCandidateSet;
pub use gap_ordering::{order_gaps, GapOrdering};
pub use gap_multiplicity::analyze_gaps;
pub use gap_constraint_satisfaction::GapConstraint;
pub use gap_verification::{verify_all_gaps, VerificationResult};
pub use prime_gap_relationship::{prime_gap_pairs, maximal_gaps, PrimeGapPair};

use gap_absolute_difference::{
    absolute_gap_differences, gap_deviations, gap_differences, gap_sequence_distance, sequence_roughness,
};
use gap_constraint_satisfaction::{count_satisfying, filter_by_constraint, verify_gaps};
use gap_multiplicity::{average_gap, is_anomalous_gap, most_common_gaps};
use gap_ordering::{gap_histogram, top_k_gaps};
use gap_verification::{verify_gaps_around_primes, verify_gaps_comprehensive, verify_multi_constraint};
use prime_gap_relationship::{largest_gap_in_range, primes_with_gap};
use prime_predicate::is_prime_candidate;

/// Outcome of one scenario.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScenarioResult {
    /// Scenario name.
    pub name: &'static str,
    /// Error description, if the scenario failed.
    pub failure: Option<String>,
}

impl ScenarioResult {
    /// Did the scenario pass?
    pub fn passed(&self) -> bool {
        self.failure.is_none()
    }
}

/// Outcome of all scenarios.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IntegrationReport {
    /// Per-scenario results, in run order.
    pub scenarios: Vec<ScenarioResult>,
}

impl IntegrationReport {
    /// True iff every scenario passed.
    pub fn all_passed(&self) -> bool {
        self.scenarios.iter().all(ScenarioResult::passed)
    }

    /// The failed scenarios.
    pub fn failures(&self) -> Vec<&ScenarioResult> {
        self.scenarios.iter().filter(|s| !s.passed()).collect()
    }
}

type Scenario = fn() -> Result<(), String>;

fn ensure(condition: bool, message: &str) -> Result<(), String> {
    if condition {
        Ok(())
    } else {
        Err(message.to_string())
    }
}

/// Every scenario works over the primes up to this limit.
const LIMIT: u64 = 100;

/// The consecutive prime pairs up to [`LIMIT`], as `(p, q, q − p)`.
fn candidates() -> Vec<(u64, u64, u64)> {
    GapCandidateSet::from_limit(LIMIT).candidates_with_gap(1)
}

fn primes_are_enumerated_exactly() -> Result<(), String> {
    let primes = primes_up_to(LIMIT);
    ensure(primes.len() == 25 && prime_count(LIMIT) == 25, "pi(100) should be 25")?;
    ensure(primes.first() == Some(&2) && primes.last() == Some(&97), "primes up to 100 should run from 2 to 97")?;
    ensure(nth_prime(0) == Some(2) && nth_prime(24) == Some(97), "nth_prime is 0-indexed: 2 and 97")?;
    let from_predicate: Vec<u64> = (0..=LIMIT).filter(|&n| is_prime(n)).collect();
    ensure(primes == from_predicate, "the sieve and the predicate should agree up to 100")?;
    ensure(
        (0..10_000).all(|n| is_prime_candidate(n) == is_prime(n)),
        "both primality tests should agree below 10000",
    )
}

fn candidate_set_matches_consecutive_primes() -> Result<(), String> {
    let set = GapCandidateSet::from_limit(LIMIT);
    ensure(set.len() == 25 && set.gaps().len() == 24, "25 primes give 24 gaps")?;
    ensure(
        (set.min_gap(), set.max_gap(), set.gap_count()) == (1, 8, 5),
        "gaps up to 100 range over {1, 2, 4, 6, 8}",
    )?;
    ensure(set.contains_gap(6) && !set.contains_gap(3), "gap 6 occurs and odd gap 3 cannot")?;
    let candidates = set.candidates_with_gap(1);
    let primes = primes_up_to(LIMIT);
    ensure(
        candidates.len() == 24
            && candidates.iter().zip(primes.windows(2)).all(|(&(p, q, g), w)| p == w[0] && q == w[1] && g == q - p),
        "candidates should be the consecutive prime pairs",
    )?;
    ensure(GapCandidateSet::from_limit(LIMIT).candidates_with_gap(4).len() == 15, "15 gaps are at least 4")
}

fn gap_statistics_are_exact() -> Result<(), String> {
    let candidates = candidates();
    let counts: Vec<(u64, usize)> = analyze_gaps(&candidates).iter().map(|m| (m.gap_size, m.count)).collect();
    let expected = vec![(1, 1), (2, 8), (4, 7), (6, 7), (8, 1)];
    ensure(counts == expected, &format!("gap multiplicities should be {expected:?}, got {counts:?}"))?;
    ensure(
        gap_histogram(&candidates).into_iter().collect::<Vec<_>>() == expected,
        "the histogram should match the multiplicities",
    )?;
    let common = most_common_gaps(&candidates, 1);
    ensure(
        common.len() == 1 && common[0].gap_size == 2 && common[0].count == 8,
        "twin primes (gap 2) are the most common gap",
    )?;
    ensure(average_gap(&candidates) == 95.0 / 24.0, "gaps telescope to 97 - 2 = 95 over 24 gaps")?;
    // Sample sd ≈ 1.92, so mean + 2 sd ≈ 7.80: gap 8 is anomalous, gap 6 is not.
    ensure(
        is_anomalous_gap(8, &candidates) && !is_anomalous_gap(6, &candidates),
        "only gap 8 should exceed mean + 2 sd",
    )?;
    let top: Vec<u64> = top_k_gaps(candidates.clone(), 3).iter().map(|c| c.2).collect();
    ensure(top == vec![8, 6, 6], "the three largest gaps are 8, 6, 6")?;
    ensure(
        order_gaps(candidates, GapOrdering::SizeAscending)[0] == (2, 3, 1),
        "the smallest gap is 2 -> 3",
    )
}

fn gap_differences_telescope() -> Result<(), String> {
    let candidates = candidates();
    let diffs = gap_differences(&candidates);
    ensure(
        diffs.len() == 23 && diffs.iter().sum::<i64>() == 8 - 1,
        "consecutive gap differences telescope to last - first = 7",
    )?;
    let absolute = absolute_gap_differences(&candidates);
    ensure(
        absolute.len() == 23 && absolute.iter().zip(&diffs).all(|(&a, &d)| a == d.unsigned_abs()),
        "absolute differences should be |differences|",
    )?;
    let deviations = gap_deviations(&candidates, 2);
    ensure(
        deviations.iter().sum::<i64>() == 95 - 2 * 24 && deviations.iter().filter(|&&d| d == 0).count() == 8,
        "deviations from 2 sum to 47, with a zero for each of the 8 twin primes",
    )?;
    let gaps: Vec<u64> = candidates.iter().map(|c| c.2).collect();
    ensure(
        gap_sequence_distance(&gaps, &gaps) == 0.0 && gap_sequence_distance(&[1, 2], &[1, 4]) == 2.0,
        "L2 distance is 0 to itself and 2 between [1, 2] and [1, 4]",
    )?;
    ensure(
        sequence_roughness(&[(3, 5, 2), (5, 7, 2)]) == 0.0 && sequence_roughness(&candidates) > 0.0,
        "constant gaps have zero roughness and the real gaps do not",
    )
}

fn constraints_select_exactly() -> Result<(), String> {
    let candidates = candidates();
    let even_small = GapConstraint::range(2, 8).with_modulus(2, 0);
    ensure(count_satisfying(&candidates, &even_small) == 23, "every gap after 2 -> 3 is even and at most 8")?;
    let sixes = filter_by_constraint(candidates.clone(), &GapConstraint::range(6, 6));
    ensure(sixes.len() == 7 && sixes.iter().all(|c| c.2 == 6), "there are seven gaps of exactly 6")?;
    let flags = verify_gaps(&candidates, &GapConstraint::range(1, 6));
    let rejected: Vec<usize> = flags.iter().enumerate().filter(|(_, &ok)| !ok).map(|(i, _)| i).collect();
    ensure(rejected == vec![23], "only the last gap, 89 -> 97 = 8, exceeds 6")
}

fn verification_rejects_forgeries() -> Result<(), String> {
    let candidates = candidates();
    ensure(
        verify_gaps_around_primes(&candidates).all_passed() && verify_gaps_comprehensive(&candidates).all_passed(),
        "real consecutive primes should verify",
    )?;
    ensure(verify_gaps_comprehensive(&[(7, 11, 3)]).failed == 1, "a misstated gap should fail")?;
    ensure(verify_gaps_around_primes(&[(7, 10, 3)]).failed == 1, "an odd gap after 2 should fail")?;
    let capped = verify_all_gaps(&candidates, &GapConstraint::range(1, 6));
    ensure(
        (capped.passed, capped.failed) == (23, 1) && capped.is_good() && !capped.all_passed(),
        "23 of 24 clears the 90% bar without all passing",
    )?;
    let both = verify_multi_constraint(
        &candidates,
        &[GapConstraint::range(2, 8), GapConstraint::unbounded().with_modulus(2, 0)],
    );
    ensure(both.passed == 23 && both.failed == 1, "gap 1 is the only one that is not even and at least 2")
}

fn prime_gap_pairs_agree_with_candidates() -> Result<(), String> {
    let pairs = prime_gap_pairs(LIMIT);
    let candidates = candidates();
    ensure(
        pairs.len() == candidates.len()
            && pairs.iter().zip(&candidates).all(|(p, &c)| (p.prime, p.next_prime, p.gap) == c),
        "prime_gap_pairs should list the candidate gaps",
    )?;
    ensure(primes_with_gap(&pairs, 2) == vec![3, 5, 11, 17, 29, 41, 59, 71], "twin primes below 100")?;
    let firsts: Vec<(u64, u64)> = maximal_gaps(&pairs).iter().map(|p| (p.prime, p.gap)).collect();
    ensure(firsts == vec![(2, 1), (3, 2), (7, 4), (23, 6), (89, 8)], "first occurrence of each gap size")?;
    ensure(
        pairs.iter().filter(|p| p.is_first_occurrence(&pairs)).count() == 5,
        "exactly one first occurrence per gap size",
    )?;
    ensure(
        largest_gap_in_range(&pairs, 0, LIMIT).map(|p| p.prime) == Some(89),
        "the largest gap below 100 starts at 89",
    )
}

/// Run every scenario.
pub fn run_prime_gap_integration() -> IntegrationReport {
    let scenarios: [(&'static str, Scenario); 7] = [
        ("primes_are_enumerated_exactly", primes_are_enumerated_exactly),
        ("candidate_set_matches_consecutive_primes", candidate_set_matches_consecutive_primes),
        ("gap_statistics_are_exact", gap_statistics_are_exact),
        ("gap_differences_telescope", gap_differences_telescope),
        ("constraints_select_exactly", constraints_select_exactly),
        ("verification_rejects_forgeries", verification_rejects_forgeries),
        ("prime_gap_pairs_agree_with_candidates", prime_gap_pairs_agree_with_candidates),
    ];
    IntegrationReport {
        scenarios: scenarios
            .iter()
            .map(|&(name, run)| ScenarioResult {
                name,
                failure: run().err(),
            })
            .collect(),
    }
}

/// True iff every scenario of [`run_prime_gap_integration`] passes.
pub fn tier2_integration_test() -> bool {
    run_prime_gap_integration().all_passed()
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
    fn every_scenario_passes() {
        let report = run_prime_gap_integration();
        assert_eq!(report.scenarios.len(), 7);
        assert!(report.all_passed(), "failures: {:?}", report.failures());
        assert!(tier2_integration_test());
    }
}
