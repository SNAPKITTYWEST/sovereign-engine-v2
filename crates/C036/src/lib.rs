//! recursion_base_case
//!
//! Base case detection for recursive solver. Determines when recursion should
//! terminate, identifies terminal states, and validates completion conditions.

#![warn(missing_docs)]

use prime_gap_relationship::{PrimeGapPair, prime_gap_pairs};
use recursive_solver_state::{GapConstraint, RecursiveSolverState};

/// Does the consecutive prime pair satisfy the constraint? The gap must
/// match and the lower prime must lie within the (optional) bounds.
pub fn constraint_admits(constraint: &GapConstraint, pair: &PrimeGapPair) -> bool {
    pair.gap == constraint.gap_size as u64
        && (constraint.min_prime == 0 || pair.prime >= constraint.min_prime as u64)
        && (constraint.max_prime == 0 || pair.prime <= constraint.max_prime as u64)
}

/// Criteria for detecting a base case.
#[derive(Debug, Clone)]
pub enum BaseCase {
    /// All constraints have been satisfied.
    AllConstraintsSatisfied,
    /// A terminal prime has been reached.
    TerminalPrimeReached(u64),
    /// Maximum depth reached.
    MaxDepthReached,
    /// No more valid moves available.
    NoValidMoves,
    /// Sequence is exhausted.
    SequenceExhausted,
    /// Specific gap pattern found.
    PatternMatched(u64),
}

/// Validator for base case conditions.
#[derive(Debug, Clone)]
pub struct BaseCaseValidator {
    /// Prime-gap relationships for validation.
    gap_pairs: Vec<PrimeGapPair>,
    /// Terminal prime to look for.
    terminal_prime: Option<u64>,
    /// Target gap pattern (if any).
    target_gap: Option<u64>,
}

impl BaseCaseValidator {
    /// Create a new base case validator.
    pub fn new(limit: u64) -> Self {
        let gap_pairs = prime_gap_pairs(limit);
        Self {
            gap_pairs,
            terminal_prime: None,
            target_gap: None,
        }
    }

    /// Set the terminal prime to look for.
    pub fn with_terminal_prime(mut self, prime: u64) -> Self {
        self.terminal_prime = Some(prime);
        self
    }

    /// Set the target gap pattern.
    pub fn with_target_gap(mut self, gap: u64) -> Self {
        self.target_gap = Some(gap);
        self
    }

    /// Check if all constraints are satisfied.
    pub fn check_all_constraints_satisfied(state: &RecursiveSolverState) -> bool {
        let unsatisfied = state.unsatisfied_constraint_count();
        unsatisfied == 0
    }

    /// Check if terminal prime has been reached.
    pub fn check_terminal_prime_reached(&self, state: &RecursiveSolverState) -> bool {
        if let Some(terminal) = self.terminal_prime {
            if let Some(node) = state.terminal_node() {
                return node.prime_val == terminal as u32;
            }
        }
        false
    }

    /// Check if max depth is exceeded.
    pub fn check_max_depth_reached(state: &RecursiveSolverState, max_depth: u32) -> bool {
        state.depth() >= max_depth
    }

    /// No valid move remains from `cursor_pos`: the state is contradictory,
    /// or no remaining prime pair satisfies any unsatisfied constraint (with
    /// no unsatisfied constraints, any remaining pair is a valid move).
    pub fn check_no_valid_moves(&self, state: &RecursiveSolverState, cursor_pos: usize) -> bool {
        if state.is_contradictory() {
            return true;
        }
        let remaining = self.gap_pairs.get(cursor_pos..).unwrap_or(&[]);
        let open: Vec<&GapConstraint> = state.constraints().iter().filter(|c| !c.is_satisfied).collect();
        if open.is_empty() {
            return remaining.is_empty();
        }
        !remaining
            .iter()
            .any(|pair| open.iter().any(|c| constraint_admits(c, pair)))
    }

    /// Check if sequence is exhausted.
    pub fn check_sequence_exhausted(cursor_pos: usize, total_gaps: usize) -> bool {
        cursor_pos >= total_gaps.saturating_sub(1)
    }

    /// Check if target gap pattern is matched.
    pub fn check_pattern_matched(&self, gap: u64) -> bool {
        if let Some(target) = self.target_gap {
            return gap == target;
        }
        false
    }

    /// Comprehensive base case check.
    pub fn is_base_case(
        &self,
        state: &RecursiveSolverState,
        cursor_pos: usize,
        total_gaps: usize,
        max_depth: u32,
        current_gap: u64,
    ) -> Option<BaseCase> {
        if Self::check_all_constraints_satisfied(state) {
            return Some(BaseCase::AllConstraintsSatisfied);
        }

        if self.check_terminal_prime_reached(state) {
            return Some(BaseCase::TerminalPrimeReached(
                self.terminal_prime.unwrap_or(0),
            ));
        }

        if Self::check_max_depth_reached(state, max_depth) {
            return Some(BaseCase::MaxDepthReached);
        }

        if Self::check_sequence_exhausted(cursor_pos, total_gaps) {
            return Some(BaseCase::SequenceExhausted);
        }

        if self.check_pattern_matched(current_gap) {
            return Some(BaseCase::PatternMatched(current_gap));
        }

        if self.check_no_valid_moves(state, cursor_pos) {
            return Some(BaseCase::NoValidMoves);
        }

        None
    }

    /// Get the gap pairs.
    pub fn gap_pairs(&self) -> &[PrimeGapPair] {
        &self.gap_pairs
    }
}

/// Statistics about base case conditions.
#[derive(Debug, Clone)]
pub struct BaseCaseStats {
    /// Number of times each base case was encountered.
    pub case_counts: std::collections::BTreeMap<String, usize>,
    /// Total base cases encountered.
    pub total_base_cases: usize,
    /// Most common base case.
    pub most_common: Option<String>,
}

impl BaseCaseStats {
    /// Create empty stats.
    pub fn new() -> Self {
        Self {
            case_counts: std::collections::BTreeMap::new(),
            total_base_cases: 0,
            most_common: None,
        }
    }

    /// Record a base case occurrence.
    pub fn record(&mut self, case: &BaseCase) {
        let case_name = match case {
            BaseCase::AllConstraintsSatisfied => "AllConstraintsSatisfied".to_string(),
            BaseCase::TerminalPrimeReached(p) => format!("TerminalPrimeReached({})", p),
            BaseCase::MaxDepthReached => "MaxDepthReached".to_string(),
            BaseCase::NoValidMoves => "NoValidMoves".to_string(),
            BaseCase::SequenceExhausted => "SequenceExhausted".to_string(),
            BaseCase::PatternMatched(g) => format!("PatternMatched({})", g),
        };

        *self.case_counts.entry(case_name.clone()).or_insert(0) += 1;
        self.total_base_cases += 1;

        // Update most common
        let max_count = self.case_counts.values().max().copied().unwrap_or(0);
        self.most_common = self
            .case_counts
            .iter()
            .find(|(_, &c)| c == max_count)
            .map(|(name, _)| name.clone());
    }

    /// Get statistics.
    pub fn stats(&self) -> (&std::collections::BTreeMap<String, usize>, usize) {
        (&self.case_counts, self.total_base_cases)
    }
}

impl Default for BaseCaseStats {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_base_case_validator_creation() {
        let validator = BaseCaseValidator::new(100);
        assert!(!validator.gap_pairs().is_empty());
    }

    #[test]
    fn test_with_terminal_prime() {
        let validator = BaseCaseValidator::new(100).with_terminal_prime(13);
        assert_eq!(validator.terminal_prime, Some(13));
    }

    #[test]
    fn test_with_target_gap() {
        let validator = BaseCaseValidator::new(100).with_target_gap(4);
        assert_eq!(validator.target_gap, Some(4));
    }

    #[test]
    fn test_check_sequence_exhausted() {
        assert!(!BaseCaseValidator::check_sequence_exhausted(0, 10));
        assert!(!BaseCaseValidator::check_sequence_exhausted(5, 10));
        assert!(BaseCaseValidator::check_sequence_exhausted(9, 10));
    }

    #[test]
    fn test_check_max_depth_reached() {
        let state = RecursiveSolverState::new();
        assert!(!BaseCaseValidator::check_max_depth_reached(&state, 100));
    }

    #[test]
    fn test_base_case_stats() {
        let mut stats = BaseCaseStats::new();
        stats.record(&BaseCase::SequenceExhausted);
        stats.record(&BaseCase::MaxDepthReached);
        stats.record(&BaseCase::SequenceExhausted);
        assert_eq!(stats.total_base_cases, 3);
        assert_eq!(
            stats.case_counts.get("SequenceExhausted"),
            Some(&2)
        );
    }

    fn constraint(gap_size: u32, min_prime: u32, max_prime: u32) -> GapConstraint {
        GapConstraint {
            position: 0,
            min_prime,
            max_prime,
            gap_size,
            is_satisfied: false,
        }
    }

    #[test]
    fn valid_moves_follow_constraints() {
        let v = BaseCaseValidator::new(100);
        let idx_89 = v.gap_pairs().iter().position(|p| p.prime == 89).unwrap();

        let mut state = RecursiveSolverState::new();
        state.add_constraint(constraint(8, 0, 0));
        assert!(!v.check_no_valid_moves(&state, 0), "89 → 97 has gap 8");
        assert!(!v.check_no_valid_moves(&state, idx_89));
        assert!(v.check_no_valid_moves(&state, idx_89 + 1), "no gap 8 after 89 below 100");

        let mut impossible = RecursiveSolverState::new();
        impossible.add_constraint(constraint(14, 0, 0));
        assert!(v.check_no_valid_moves(&impossible, 0), "first gap 14 is 113 → 127");

        let mut bounded = RecursiveSolverState::new();
        bounded.add_constraint(constraint(2, 50, 60));
        assert!(!v.check_no_valid_moves(&bounded, 0), "59 → 61");
        let mut out_of_range = RecursiveSolverState::new();
        out_of_range.add_constraint(constraint(2, 20, 28));
        assert!(v.check_no_valid_moves(&out_of_range, 0), "no twin primes with 20 ≤ p ≤ 28");
    }

    #[test]
    fn contradictions_and_unconstrained_states() {
        let v = BaseCaseValidator::new(30);
        let mut state = RecursiveSolverState::new();
        assert!(!v.check_no_valid_moves(&state, 0));
        assert!(v.check_no_valid_moves(&state, v.gap_pairs().len()));
        state.set_contradictory();
        assert!(v.check_no_valid_moves(&state, 0));
        let mut satisfied = RecursiveSolverState::new();
        satisfied.add_constraint(constraint(4, 0, 0));
        satisfied.mark_constraint_satisfied(0);
        assert!(!v.check_no_valid_moves(&satisfied, 0));
    }

    #[test]
    fn test_check_pattern_matched() {
        let validator = BaseCaseValidator::new(100).with_target_gap(4);
        assert!(validator.check_pattern_matched(4));
        assert!(!validator.check_pattern_matched(2));
    }
}

