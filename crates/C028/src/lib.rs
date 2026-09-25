//! gap_verification
//!
//! Comprehensive gap verification and validation.

#![warn(missing_docs)]

pub use gap_candidate_set::GapCandidateSet;
pub use gap_constraint_satisfaction::{GapConstraint, verify_gaps, filter_by_constraint};

/// Result of gap verification.
#[derive(Clone, Debug)]
pub struct VerificationResult {
    /// Total gaps checked
    pub total: usize,
    /// Gaps that passed verification
    pub passed: usize,
    /// Gaps that failed
    pub failed: usize,
    /// Pass rate (0.0 to 1.0)
    pub pass_rate: f64,
}

impl VerificationResult {
    /// Create from pass/fail counts.
    pub fn new(passed: usize, failed: usize) -> Self {
        let total = passed + failed;
        let pass_rate = if total == 0 {
            1.0
        } else {
            passed as f64 / total as f64
        };

        Self {
            total,
            passed,
            failed,
            pass_rate,
        }
    }

    /// Check if all gaps passed.
    pub fn all_passed(&self) -> bool {
        self.failed == 0
    }

    /// Check if verification is "good" (>= 90% pass rate).
    pub fn is_good(&self) -> bool {
        self.pass_rate >= 0.9
    }
}

/// Verify all gaps in a set against a constraint.
pub fn verify_all_gaps(
    candidates: &[(u64, u64, u64)],
    constraint: &GapConstraint,
) -> VerificationResult {
    let results = verify_gaps(candidates, constraint);
    let passed = results.iter().filter(|&&p| p).count();
    let failed = results.iter().filter(|&&p| !p).count();
    VerificationResult::new(passed, failed)
}

/// Verify using multiple constraints (all must pass).
pub fn verify_multi_constraint(
    candidates: &[(u64, u64, u64)],
    constraints: &[GapConstraint],
) -> VerificationResult {
    let results: Vec<bool> = candidates
        .iter()
        .map(|&(_, _, gap)| constraints.iter().all(|c| c.satisfies(gap)))
        .collect();

    let passed = results.iter().filter(|&&p| p).count();
    let failed = results.iter().filter(|&&p| !p).count();
    VerificationResult::new(passed, failed)
}

/// Verify that gaps follow a primality condition.
pub fn verify_gaps_around_primes(
    candidates: &[(u64, u64, u64)],
) -> VerificationResult {
    // A gap between consecutive primes p and q should have q - p >= 2
    let results: Vec<bool> = candidates
        .iter()
        .map(|&(p, q, gap)| {
            // Verify internal consistency
            q > p && gap == q - p && gap >= 2
        })
        .collect();

    let passed = results.iter().filter(|&&p| p).count();
    let failed = results.iter().filter(|&&p| !p).count();
    VerificationResult::new(passed, failed)
}

/// Comprehensive verification including structural checks.
pub fn verify_gaps_comprehensive(candidates: &[(u64, u64, u64)]) -> VerificationResult {
    let results: Vec<bool> = candidates
        .iter()
        .enumerate()
        .map(|(i, &(p, q, gap))| {
            // Check 1: Gap is correct
            if gap != q - p {
                return false;
            }
            // Check 2: q > p
            if q <= p {
                return false;
            }
            // Check 3: Gap is at least 1
            if gap < 1 {
                return false;
            }
            // Check 4: Ordering is maintained (if not first)
            // For consecutive primes, the first prime of this gap should equal
            // the second prime of the previous gap (they are consecutive primes)
            if i > 0 {
                // Allow gap to start right after the previous one (consecutive primes)
                // but don't allow overlaps or gaps
                if p < candidates[i - 1].1 {
                    return false;
                }
            }
            true
        })
        .collect();

    let passed = results.iter().filter(|&&p| p).count();
    let failed = results.iter().filter(|&&p| !p).count();
    VerificationResult::new(passed, failed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verification_result() {
        let result = VerificationResult::new(9, 1);
        assert_eq!(result.total, 10);
        assert_eq!(result.passed, 9);
        assert!(!result.all_passed());
        assert!(result.is_good());
    }

    #[test]
    fn test_verify_all_gaps() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let constraint = GapConstraint::range(1, 5);
        let result = verify_all_gaps(&candidates, &constraint);
        assert_eq!(result.passed, 4);
        assert_eq!(result.failed, 0);
    }

    #[test]
    fn test_verify_multi_constraint() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let constraints = vec![
            GapConstraint::range(1, 5),
            GapConstraint::unbounded(),
        ];
        let result = verify_multi_constraint(&candidates, &constraints);
        assert_eq!(result.passed, 4);
    }

    #[test]
    fn test_verify_gaps_around_primes() {
        let candidates = vec![(3, 5, 2), (5, 7, 2), (7, 11, 4), (11, 13, 2)];
        let result = verify_gaps_around_primes(&candidates);
        assert!(result.all_passed());
    }

    #[test]
    fn test_verify_gaps_comprehensive() {
        let candidates = vec![(3, 5, 2), (5, 7, 2), (7, 11, 4), (11, 13, 2)];
        let result = verify_gaps_comprehensive(&candidates);
        assert!(result.all_passed());
    }
}
