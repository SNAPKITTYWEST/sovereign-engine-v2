//! gap_constraint_satisfaction
//!
//! Constraint satisfaction for prime gap verification.

#![warn(missing_docs)]

pub use gap_absolute_difference::gap_deviations;

/// A constraint on a gap.
#[derive(Clone, Debug)]
pub struct GapConstraint {
    /// Minimum allowed gap size
    pub min: u64,
    /// Maximum allowed gap size
    pub max: u64,
    /// Optional modular constraint (gap % modulus == residue)
    pub modulus: Option<(u64, u64)>,
}

impl GapConstraint {
    /// Create an unbounded constraint.
    pub fn unbounded() -> Self {
        Self {
            min: 0,
            max: u64::MAX,
            modulus: None,
        }
    }

    /// Create a range constraint.
    pub fn range(min: u64, max: u64) -> Self {
        Self {
            min,
            max,
            modulus: None,
        }
    }

    /// Add modular constraint.
    pub fn with_modulus(mut self, modulus: u64, residue: u64) -> Self {
        self.modulus = Some((modulus, residue));
        self
    }

    /// Check if a gap satisfies this constraint.
    pub fn satisfies(&self, gap: u64) -> bool {
        if gap < self.min || gap > self.max {
            return false;
        }
        if let Some((mod_val, residue)) = self.modulus {
            if gap % mod_val != residue {
                return false;
            }
        }
        true
    }
}

/// Verify gaps against a constraint.
pub fn verify_gaps(candidates: &[(u64, u64, u64)], constraint: &GapConstraint) -> Vec<bool> {
    candidates
        .iter()
        .map(|&(_, _, gap)| constraint.satisfies(gap))
        .collect()
}

/// Filter candidates that satisfy a constraint.
pub fn filter_by_constraint(
    candidates: Vec<(u64, u64, u64)>,
    constraint: &GapConstraint,
) -> Vec<(u64, u64, u64)> {
    candidates
        .into_iter()
        .filter(|&(_, _, gap)| constraint.satisfies(gap))
        .collect()
}

/// Count how many gaps satisfy the constraint.
pub fn count_satisfying(candidates: &[(u64, u64, u64)], constraint: &GapConstraint) -> usize {
    candidates.iter().filter(|&(_, _, gap)| constraint.satisfies(*gap)).count()
}

/// Create a "golden gap" constraint for primes following a specific pattern.
pub fn golden_gap_constraint(target_gap: u64, tolerance: u64) -> GapConstraint {
    GapConstraint::range(
        target_gap.saturating_sub(tolerance),
        target_gap.saturating_add(tolerance),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gap_constraint_unbounded() {
        let constraint = GapConstraint::unbounded();
        assert!(constraint.satisfies(1));
        assert!(constraint.satisfies(1000));
    }

    #[test]
    fn test_gap_constraint_range() {
        let constraint = GapConstraint::range(2, 6);
        assert!(!constraint.satisfies(1));
        assert!(constraint.satisfies(2));
        assert!(constraint.satisfies(4));
        assert!(!constraint.satisfies(7));
    }

    #[test]
    fn test_gap_constraint_modulus() {
        let constraint = GapConstraint::range(1, 10).with_modulus(2, 0);
        assert!(!constraint.satisfies(1)); // odd
        assert!(constraint.satisfies(2));  // even
        assert!(!constraint.satisfies(3)); // odd
        assert!(constraint.satisfies(4));  // even
    }

    #[test]
    fn test_verify_gaps() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let constraint = GapConstraint::range(1, 3);
        let results = verify_gaps(&candidates, &constraint);
        assert_eq!(results, vec![true, true, true, false]);
    }

    #[test]
    fn test_filter_by_constraint() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let constraint = GapConstraint::range(1, 2);
        let filtered = filter_by_constraint(candidates, &constraint);
        assert_eq!(filtered.len(), 3);
    }

    #[test]
    fn test_golden_gap_constraint() {
        let constraint = golden_gap_constraint(5, 2);
        assert!(constraint.satisfies(3));
        assert!(constraint.satisfies(5));
        assert!(constraint.satisfies(7));
        assert!(!constraint.satisfies(1));
        assert!(!constraint.satisfies(9));
    }
}
