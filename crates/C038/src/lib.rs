//! recursion_contradiction_detection
//!
//! Detect contradictions in gap constraints during recursive solving.
//! Identifies unsatisfiable constraints and marks branches as failed.

#![warn(missing_docs)]

use gap_constraint_satisfaction::GapConstraint;
use recursive_solver_state::RecursiveSolverState;
use recursive_solver_cursor::RecursiveSolverCursor;

/// A contradiction found during constraint analysis.
#[derive(Debug, Clone)]
pub struct Contradiction {
    /// Type of contradiction.
    pub contradiction_type: ContradictionType,
    /// Position in gap sequence where it occurred.
    pub position: usize,
    /// The gap value involved.
    pub gap_value: u64,
    /// Constraint that was violated.
    pub constraint: Option<String>,
}

/// Types of contradictions that can occur.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContradictionType {
    /// Constraint cannot be satisfied by any gap.
    UnsatisfiableConstraint,
    /// Gap value violates range constraint.
    RangeViolation,
    /// Gap value violates modular constraint.
    ModularViolation,
    /// Conflicting constraints on the same gap.
    ConflictingConstraints,
    /// No valid moves available from this state.
    DeadEnd,
    /// Inconsistent state detected.
    InconsistentState,
}

impl std::fmt::Display for ContradictionType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::UnsatisfiableConstraint => write!(f, "UnsatisfiableConstraint"),
            Self::RangeViolation => write!(f, "RangeViolation"),
            Self::ModularViolation => write!(f, "ModularViolation"),
            Self::ConflictingConstraints => write!(f, "ConflictingConstraints"),
            Self::DeadEnd => write!(f, "DeadEnd"),
            Self::InconsistentState => write!(f, "InconsistentState"),
        }
    }
}

/// Detects contradictions in the solving process.
#[derive(Debug, Clone)]
pub struct ContradictionDetector {
    /// Detected contradictions.
    contradictions: Vec<Contradiction>,
    /// Constraints to check against.
    constraints: Vec<GapConstraint>,
}

impl ContradictionDetector {
    /// Create a new contradiction detector.
    pub fn new() -> Self {
        Self {
            contradictions: Vec::new(),
            constraints: vec![GapConstraint::unbounded()],
        }
    }

    /// Add a constraint to check against.
    pub fn add_constraint(&mut self, constraint: GapConstraint) {
        self.constraints.push(constraint);
    }

    /// Check a gap against all constraints.
    pub fn check_gap(&mut self, position: usize, gap: u64) -> Option<Contradiction> {
        for constraint in &self.constraints {
            if !constraint.satisfies(gap) {
                // Determine the specific violation type
                let contradiction_type = if gap < constraint.min || gap > constraint.max {
                    ContradictionType::RangeViolation
                } else if let Some((modulus, _)) = constraint.modulus {
                    if gap % modulus != 0 {
                        ContradictionType::ModularViolation
                    } else {
                        ContradictionType::UnsatisfiableConstraint
                    }
                } else {
                    ContradictionType::UnsatisfiableConstraint
                };

                let contradiction = Contradiction {
                    contradiction_type,
                    position,
                    gap_value: gap,
                    constraint: Some(format!("min: {}, max: {}", constraint.min, constraint.max)),
                };

                self.contradictions.push(contradiction.clone());
                return Some(contradiction);
            }
        }
        None
    }

    /// Check for conflicting constraints within state.
    pub fn check_conflicting_constraints(
        state: &RecursiveSolverState,
    ) -> Option<Contradiction> {
        let constraints = state.constraints();
        if constraints.len() < 2 {
            return None;
        }

        // Check if any two constraints are mutually exclusive
        for i in 0..constraints.len() {
            for j in (i + 1)..constraints.len() {
                let c1 = &constraints[i];
                let c2 = &constraints[j];

                // Check for range conflicts
                if c1.position == c2.position {
                    if c1.gap_size != c2.gap_size {
                        return Some(Contradiction {
                            contradiction_type: ContradictionType::ConflictingConstraints,
                            position: c1.position,
                            gap_value: c1.gap_size as u64,
                            constraint: Some(format!(
                                "Conflicting gap sizes: {} vs {}",
                                c1.gap_size, c2.gap_size
                            )),
                        });
                    }
                }
            }
        }
        None
    }

    /// Check for dead ends (no valid moves).
    pub fn check_dead_end(
        cursor: &RecursiveSolverCursor,
        state: &RecursiveSolverState,
    ) -> Option<Contradiction> {
        let unvisited = cursor.unvisited_positions();
        if unvisited.is_empty() && state.unsatisfied_constraint_count() > 0 {
            return Some(Contradiction {
                contradiction_type: ContradictionType::DeadEnd,
                position: cursor.position(),
                gap_value: cursor.current_gap().map(|(_, _, g)| g).unwrap_or(0),
                constraint: None,
            });
        }
        None
    }

    /// Check for inconsistent state.
    pub fn check_inconsistent_state(state: &RecursiveSolverState) -> Option<Contradiction> {
        if state.is_contradictory()
            && state.terminal_node().is_some()
            && state.unsatisfied_constraint_count() > 0
        {
            return Some(Contradiction {
                contradiction_type: ContradictionType::InconsistentState,
                position: state.cursor(),
                gap_value: 0,
                constraint: Some("State is contradictory with unsatisfied constraints".to_string()),
            });
        }
        None
    }

    /// Get all detected contradictions.
    pub fn contradictions(&self) -> &[Contradiction] {
        &self.contradictions
    }

    /// Get contradiction count.
    pub fn contradiction_count(&self) -> usize {
        self.contradictions.len()
    }

    /// Clear all detected contradictions.
    pub fn clear(&mut self) {
        self.contradictions.clear();
    }

    /// Comprehensive contradiction check.
    pub fn full_check(
        &mut self,
        state: &RecursiveSolverState,
        cursor: &RecursiveSolverCursor,
    ) -> Vec<Contradiction> {
        let mut detected = Vec::new();

        // Check for conflicting constraints
        if let Some(contradiction) = Self::check_conflicting_constraints(state) {
            detected.push(contradiction);
        }

        // Check for dead ends
        if let Some(contradiction) = Self::check_dead_end(cursor, state) {
            detected.push(contradiction);
        }

        // Check for inconsistent state
        if let Some(contradiction) = Self::check_inconsistent_state(state) {
            detected.push(contradiction);
        }

        detected
    }

    /// Check if any contradiction exists.
    pub fn has_contradiction(&self) -> bool {
        !self.contradictions.is_empty()
    }
}

impl Default for ContradictionDetector {
    fn default() -> Self {
        Self::new()
    }
}

/// Statistics about contradictions.
#[derive(Debug, Clone)]
pub struct ContradictionStats {
    /// Count by contradiction type.
    pub type_counts: std::collections::BTreeMap<String, usize>,
    /// Total contradictions.
    pub total: usize,
    /// Most common type.
    pub most_common_type: Option<String>,
}

impl ContradictionStats {
    /// Create empty stats.
    pub fn new() -> Self {
        Self {
            type_counts: std::collections::BTreeMap::new(),
            total: 0,
            most_common_type: None,
        }
    }

    /// Record a contradiction.
    pub fn record(&mut self, contradiction: &Contradiction) {
        let type_name = contradiction.contradiction_type.to_string();
        *self.type_counts.entry(type_name.clone()).or_insert(0) += 1;
        self.total += 1;

        let max_count = self.type_counts.values().max().copied().unwrap_or(0);
        self.most_common_type = self
            .type_counts
            .iter()
            .find(|(_, &c)| c == max_count)
            .map(|(name, _)| name.clone());
    }
}

impl Default for ContradictionStats {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_contradiction_creation() {
        let contradiction = Contradiction {
            contradiction_type: ContradictionType::RangeViolation,
            position: 0,
            gap_value: 100,
            constraint: Some("Range: 1-4".to_string()),
        };
        assert_eq!(contradiction.gap_value, 100);
    }

    #[test]
    fn test_detector_creation() {
        let detector = ContradictionDetector::new();
        assert_eq!(detector.contradiction_count(), 0);
        assert!(!detector.has_contradiction());
    }

    #[test]
    fn test_check_gap_valid() {
        let mut detector = ContradictionDetector::new();
        let result = detector.check_gap(0, 2);
        assert!(result.is_none());
    }

    #[test]
    fn test_check_gap_invalid() {
        let mut detector = ContradictionDetector::new();
        detector.add_constraint(GapConstraint::range(1, 4));
        let result = detector.check_gap(0, 100);
        assert!(result.is_some());
    }

    #[test]
    fn test_contradiction_detection_on_state() {
        let state = RecursiveSolverState::new();
        let result = ContradictionDetector::check_inconsistent_state(&state);
        // Non-contradictory state should return None
        assert!(result.is_none());
    }

    #[test]
    fn test_contradiction_stats() {
        let mut stats = ContradictionStats::new();
        let contradiction = Contradiction {
            contradiction_type: ContradictionType::RangeViolation,
            position: 0,
            gap_value: 10,
            constraint: None,
        };
        stats.record(&contradiction);
        assert_eq!(stats.total, 1);
    }
}

