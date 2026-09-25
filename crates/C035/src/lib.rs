//! recursive_solver_transition
//!
//! State transitions during recursive solving. Handles operator application,
//! constraint satisfaction checks, and state mutations.

#![warn(missing_docs)]

use gap_constraint_satisfaction::GapConstraint;
use recursive_solver_state::{RecursiveSolverState, GapConstraint as StateConstraint};
use recursion_depth_management::DepthManager;
use recursive_solver_cursor::RecursiveSolverCursor;
use gap_tensor_core::GapTensorNode;

/// Represents a transition operation between solver states.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransitionOperator {
    /// Advance to the next position.
    Advance,
    /// Retreat to previous position.
    Retreat,
    /// Apply constraint at current position.
    ApplyConstraint,
    /// Backtrack to last checkpoint.
    Backtrack,
    /// Mark position as terminal.
    Terminal,
}

/// A transition together with the data it needs.
#[derive(Debug, Clone)]
pub enum TransitionStep {
    /// Advance to the next position.
    Advance,
    /// Retreat to the previous position.
    Retreat,
    /// Apply this constraint to the gap at the current position.
    ApplyConstraint(GapConstraint),
    /// Backtrack to the last checkpoint.
    Backtrack,
    /// Mark the state terminal with this node.
    Terminal(GapTensorNode),
}

/// Result of a transition operation.
#[derive(Debug, Clone)]
pub struct TransitionResult {
    /// The operator that was applied.
    pub operator: TransitionOperator,
    /// Whether the transition was successful.
    pub success: bool,
    /// Message describing the result.
    pub message: String,
    /// New state after transition (if successful).
    pub new_cursor_pos: Option<usize>,
}

impl TransitionResult {
    /// Create a successful transition result.
    pub fn success(operator: TransitionOperator, message: String, new_pos: Option<usize>) -> Self {
        Self {
            operator,
            success: true,
            message,
            new_cursor_pos: new_pos,
        }
    }

    /// Create a failed transition result.
    pub fn failure(operator: TransitionOperator, message: String) -> Self {
        Self {
            operator,
            success: false,
            message,
            new_cursor_pos: None,
        }
    }
}

/// Manages state transitions during recursive solving.
#[derive(Debug, Clone)]
pub struct SolverTransitionEngine {
    /// Current solver state.
    state: RecursiveSolverState,
    /// Depth manager for recursion limits.
    depth_manager: DepthManager,
    /// Cursor for position tracking.
    cursor: RecursiveSolverCursor,
    /// Transition history.
    transitions: Vec<TransitionResult>,
}

impl SolverTransitionEngine {
    /// Create a new transition engine.
    pub fn new(
        state: RecursiveSolverState,
        depth_manager: DepthManager,
        cursor: RecursiveSolverCursor,
    ) -> Self {
        Self {
            state,
            depth_manager,
            cursor,
            transitions: Vec::new(),
        }
    }

    /// Apply an advance transition.
    pub fn transition_advance(&mut self) -> TransitionResult {
        if self.cursor.is_at_end() {
            return TransitionResult::failure(
                TransitionOperator::Advance,
                "Cannot advance: at end of sequence".to_string(),
            );
        }

        if self.cursor.advance() {
            self.state.advance_cursor();
            let result = TransitionResult::success(
                TransitionOperator::Advance,
                format!("Advanced to position {}", self.cursor.position()),
                Some(self.cursor.position()),
            );
            self.transitions.push(result.clone());
            result
        } else {
            TransitionResult::failure(
                TransitionOperator::Advance,
                "Advance failed".to_string(),
            )
        }
    }

    /// Apply a retreat transition.
    pub fn transition_retreat(&mut self) -> TransitionResult {
        if self.cursor.is_at_start() {
            return TransitionResult::failure(
                TransitionOperator::Retreat,
                "Cannot retreat: at start of sequence".to_string(),
            );
        }

        if self.cursor.retreat() {
            let result = TransitionResult::success(
                TransitionOperator::Retreat,
                format!("Retreated to position {}", self.cursor.position()),
                Some(self.cursor.position()),
            );
            self.transitions.push(result.clone());
            result
        } else {
            TransitionResult::failure(
                TransitionOperator::Retreat,
                "Retreat failed".to_string(),
            )
        }
    }

    /// Apply a constraint at the current position.
    pub fn transition_apply_constraint(&mut self, constraint: &GapConstraint) -> TransitionResult {
        if let Some(gap) = self.cursor.current_gap() {
            if constraint.satisfies(gap.2) {
                // Constraint is satisfied
                let state_constraint = StateConstraint {
                    position: self.cursor.position(),
                    min_prime: 0,
                    max_prime: 0,
                    gap_size: gap.2 as u32,
                    is_satisfied: true,
                };
                self.state.add_constraint(state_constraint);
                self.state.increase_depth();

                let result = TransitionResult::success(
                    TransitionOperator::ApplyConstraint,
                    format!("Constraint satisfied at gap {}", gap.2),
                    Some(self.cursor.position()),
                );
                self.transitions.push(result.clone());
                result
            } else {
                // Constraint not satisfied
                self.cursor.mark_invalid(self.cursor.position());
                self.state.set_contradictory();
                TransitionResult::failure(
                    TransitionOperator::ApplyConstraint,
                    format!("Constraint not satisfied at gap {}", gap.2),
                )
            }
        } else {
            TransitionResult::failure(
                TransitionOperator::ApplyConstraint,
                "No gap at current position".to_string(),
            )
        }
    }

    /// Apply a backtrack transition.
    pub fn transition_backtrack(&mut self) -> TransitionResult {
        if let Some((cursor, depth, _node)) = self.state.pop_state() {
            self.cursor.set_position(cursor);
            self.state.clear_contradiction();
            let result = TransitionResult::success(
                TransitionOperator::Backtrack,
                format!("Backtracked to depth {}", depth),
                Some(cursor),
            );
            self.transitions.push(result.clone());
            result
        } else {
            TransitionResult::failure(
                TransitionOperator::Backtrack,
                "No state to backtrack to".to_string(),
            )
        }
    }

    /// Mark current position as terminal.
    pub fn transition_terminal(&mut self, node: GapTensorNode) -> TransitionResult {
        self.state.set_terminal_node(node);
        let result = TransitionResult::success(
            TransitionOperator::Terminal,
            format!("Terminal state reached at position {}", self.cursor.position()),
            Some(self.cursor.position()),
        );
        self.transitions.push(result.clone());
        result
    }

    /// Execute one step.
    pub fn execute_step(&mut self, step: &TransitionStep) -> TransitionResult {
        match step {
            TransitionStep::Advance => self.transition_advance(),
            TransitionStep::Retreat => self.transition_retreat(),
            TransitionStep::ApplyConstraint(constraint) => self.transition_apply_constraint(constraint),
            TransitionStep::Backtrack => self.transition_backtrack(),
            TransitionStep::Terminal(node) => self.transition_terminal(*node),
        }
    }

    /// Execute a sequence of steps, each carrying its own data.
    pub fn execute_steps(&mut self, steps: &[TransitionStep]) -> Vec<TransitionResult> {
        steps.iter().map(|step| self.execute_step(step)).collect()
    }

    /// Execute bare operators. Operators that need data take it from the
    /// state at the moment they run: `ApplyConstraint` applies the unbounded
    /// constraint (every gap satisfies it, so it records the current gap),
    /// and `Terminal` marks the node on top of the current path (Nil if the
    /// path is empty). Use [`Self::execute_steps`] to supply explicit data.
    pub fn execute_transitions(&mut self, ops: &[TransitionOperator]) -> Vec<TransitionResult> {
        ops.iter()
            .map(|&op| {
                let step = match op {
                    TransitionOperator::Advance => TransitionStep::Advance,
                    TransitionOperator::Retreat => TransitionStep::Retreat,
                    TransitionOperator::ApplyConstraint => TransitionStep::ApplyConstraint(GapConstraint::unbounded()),
                    TransitionOperator::Backtrack => TransitionStep::Backtrack,
                    TransitionOperator::Terminal => TransitionStep::Terminal(
                        self.state.peek_state().map_or(GapTensorNode::NIL, |&(_, _, node)| node),
                    ),
                };
                self.execute_step(&step)
            })
            .collect()
    }

    /// Get the current state.
    pub fn state(&self) -> &RecursiveSolverState {
        &self.state
    }

    /// Get the current cursor.
    pub fn cursor(&self) -> &RecursiveSolverCursor {
        &self.cursor
    }

    /// Get a mutable reference to the cursor.
    pub fn cursor_mut(&mut self) -> &mut RecursiveSolverCursor {
        &mut self.cursor
    }

    /// Get transition history.
    pub fn transitions(&self) -> &[TransitionResult] {
        &self.transitions
    }

    /// Get the depth manager.
    pub fn depth_manager(&self) -> &DepthManager {
        &self.depth_manager
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_engine() -> SolverTransitionEngine {
        let state = RecursiveSolverState::new();
        let depth_manager = DepthManager::new();
        let cursor = RecursiveSolverCursor::from_gaps(vec![
            (2, 3, 1),
            (3, 5, 2),
            (5, 7, 2),
            (7, 11, 4),
        ]);
        SolverTransitionEngine::new(state, depth_manager, cursor)
    }

    #[test]
    fn steps_carry_their_data() {
        let mut engine = create_test_engine();
        let results = engine.execute_steps(&[
            TransitionStep::ApplyConstraint(GapConstraint::range(2, 2)),
            TransitionStep::Advance,
            TransitionStep::ApplyConstraint(GapConstraint::range(2, 2)),
            TransitionStep::Terminal(GapTensorNode::new(5, 1, 1.0)),
        ]);
        assert!(!results[0].success, "gap 1 at position 0 violates [2, 2]");
        assert!(results[2].success, "gap 2 at position 1 satisfies [2, 2]");
        assert_eq!(engine.state().terminal_node().unwrap().prime_val, 5);
    }

    #[test]
    fn bare_terminal_uses_the_current_path() {
        let mut engine = create_test_engine();
        engine.execute_transitions(&[TransitionOperator::Terminal]);
        assert!(engine.state().terminal_node().unwrap().is_nil());
        let mut state = RecursiveSolverState::new();
        state.push_state(GapTensorNode::new(7, 1, 1.0));
        let cursor = RecursiveSolverCursor::from_gaps(vec![(2, 3, 1)]);
        let mut engine = SolverTransitionEngine::new(state, DepthManager::new(), cursor);
        engine.execute_transitions(&[TransitionOperator::Terminal]);
        assert_eq!(engine.state().terminal_node().unwrap().prime_val, 7);
    }

    #[test]
    fn test_engine_creation() {
        let engine = create_test_engine();
        assert_eq!(engine.cursor().position(), 0);
        assert!(engine.transitions().is_empty());
    }

    #[test]
    fn test_transition_advance() {
        let mut engine = create_test_engine();
        let result = engine.transition_advance();
        assert!(result.success);
        assert_eq!(result.operator, TransitionOperator::Advance);
        assert_eq!(engine.cursor().position(), 1);
    }

    #[test]
    fn test_transition_retreat() {
        let mut engine = create_test_engine();
        engine.transition_advance();
        let result = engine.transition_retreat();
        assert!(result.success);
        assert_eq!(engine.cursor().position(), 0);
    }

    #[test]
    fn test_transition_apply_constraint() {
        let mut engine = create_test_engine();
        let constraint = GapConstraint::range(1, 4);
        let result = engine.transition_apply_constraint(&constraint);
        assert!(result.success);
    }

    #[test]
    fn test_transition_terminal() {
        let mut engine = create_test_engine();
        let node = GapTensorNode::new(2, 1, 1.0);
        let result = engine.transition_terminal(node);
        assert!(result.success);
        assert!(engine.state().terminal_node().is_some());
    }

    #[test]
    fn test_advance_at_end() {
        let mut engine = create_test_engine();
        engine.cursor_mut().jump_to_end();
        let result = engine.transition_advance();
        assert!(!result.success);
    }

    #[test]
    fn test_transition_history() {
        let mut engine = create_test_engine();
        engine.transition_advance();
        engine.transition_advance();
        assert_eq!(engine.transitions().len(), 2);
    }
}

