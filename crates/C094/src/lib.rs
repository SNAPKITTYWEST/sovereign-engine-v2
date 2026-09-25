//! prime_gap_correspondence
//!
//! Correspondence between the gap tensor's candidate primes (Tier 0) and the
//! prime/gap engine (Tier 2):
//!
//! * **candidate_gaps_match_engine**: the engine enumerates exactly the
//!   candidate primes up to the largest one, and the candidate gaps equal the
//!   engine's gaps as reported by the sieve, the gap candidate set and the
//!   prime-gap pairs;
//! * **gap_pairs_become_consonant_nodes**: every consecutive prime pair up to
//!   13, encoded as tensor nodes, passes every tensor invariant.

#![warn(missing_docs)]

use cross_layer_types::{check_tensor, prime_node, vector_state, CorrespondenceReport, CANDIDATE_PRIMES};
use gap_candidate_set::GapCandidateSet;
use prime_enumeration::primes_up_to;
use prime_gap_relationship::prime_gap_pairs;

/// Compare a candidate list with the engine.
pub fn check_candidate_gaps_match_engine_with(candidates: &[u32]) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("candidate_gaps_match_engine");
    let Some(&limit) = candidates.iter().max() else {
        report.error("empty candidate list");
        return report;
    };
    let limit = limit as u64;
    let candidates: Vec<u64> = candidates.iter().map(|&c| c as u64).collect();
    report.check(primes_up_to(limit) == candidates, || {
        format!("engine primes ≤ {limit} differ from candidates {candidates:?}")
    });
    let candidate_gaps: Vec<u64> = candidates.windows(2).map(|w| w[1] - w[0]).collect();
    report.check(GapCandidateSet::from_limit(limit).gaps() == candidate_gaps, || "gap candidate set disagrees".into());
    let pair_gaps: Vec<u64> = prime_gap_pairs(limit).iter().map(|p| p.gap).collect();
    report.check(pair_gaps == candidate_gaps, || "prime-gap pairs disagree".into());
    report
}

/// The real candidate check.
pub fn check_candidate_gaps_match_engine() -> CorrespondenceReport {
    check_candidate_gaps_match_engine_with(&CANDIDATE_PRIMES)
}

/// Encode every consecutive prime pair up to `limit` as tensor nodes and
/// check the tensor invariants.
pub fn check_gap_pairs_become_consonant_nodes_with(limit: u64) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("gap_pairs_become_consonant_nodes");
    for pair in prime_gap_pairs(limit) {
        match (prime_node(pair.prime), prime_node(pair.next_prime)) {
            (Some(a), Some(b)) => {
                let violations = check_tensor(&vector_state(vec![a, b])).violations;
                report.check(violations.is_empty(), || format!("({}, {}): {violations:?}", pair.prime, pair.next_prime));
            }
            _ => report.error(format!("({}, {}) does not fit a node", pair.prime, pair.next_prime)),
        }
    }
    report
}

/// The real pair check (primes up to 13).
pub fn check_gap_pairs_become_consonant_nodes() -> CorrespondenceReport {
    check_gap_pairs_become_consonant_nodes_with(13)
}

/// The three Tier 2 views of consecutive gaps agree up to `limit`.
pub fn check_engine_views_agree(limit: u64) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("engine_views_agree");
    let primes = primes_up_to(limit);
    let sieve_gaps: Vec<u64> = primes.windows(2).map(|w| w[1] - w[0]).collect();
    let set_gaps = GapCandidateSet::from_limit(limit).gaps();
    let pairs = prime_gap_pairs(limit);
    report.check(set_gaps == sieve_gaps, || "gap candidate set differs from the sieve".into());
    report.check(pairs.len() == sieve_gaps.len(), || "pair count differs".into());
    for (pair, (w, &g)) in pairs.iter().zip(primes.windows(2).zip(&sieve_gaps)) {
        report.check(pair.prime == w[0] && pair.next_prime == w[1] && pair.gap == g, || format!("pair at {}", w[0]));
    }
    report
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn correspondences_hold() {
        assert!(check_candidate_gaps_match_engine().holds());
        let pairs = check_gap_pairs_become_consonant_nodes();
        assert!(pairs.holds(), "{:?}", pairs.failures);
        assert_eq!(pairs.cases_checked, 5);
        assert!(check_engine_views_agree(10_000).holds());
    }

    #[test]
    fn wrong_inputs_are_caught() {
        assert!(!check_candidate_gaps_match_engine_with(&[2, 3, 5, 7, 11, 17]).holds());
        assert!(!check_candidate_gaps_match_engine_with(&[]).holds());
        assert!(!check_gap_pairs_become_consonant_nodes_with(17).holds());
    }
}
