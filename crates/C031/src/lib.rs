//! recursive_solver_state
//!
//! Core state machine for recursive solver. Tracks the current state during
//! gap sequence resolution: cursor position, recursion depth, path history,
//! and accumulated constraints.

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;

/// Maximum recursion depth allowed before backtracking.
pub const MAX_RECURSION_DEPTH: u32 = 100;

/// Represents the recursive state during gap solving.
/// Maintains cursor position, depth stack, path history, and constraint accumulation.
#[derive(Debug, Clone)]
pub struct RecursiveSolverState {
    /// Current position in the gap sequence (0-indexed).
    current_cursor: usize,
    /// Current recursion depth (0 = top level).
    current_depth: u32,
    /// Stack of (cursor, depth, node) tuples for backtracking.
    path_stack: Vec<(usize, u32, GapTensorNode)>,
    /// Accumulated constraints from gap analysis.
    constraints: Vec<GapConstraint>,
    /// Terminal node reached (if any).
    terminal_node: Option<GapTensorNode>,
    /// Whether the solver is in a contradiction state.
    is_contradictory: bool,
}

/// A gap constraint: a prime must satisfy certain properties at this position.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct GapConstraint {
    /// Position in gap sequence this constraint applies to.
    pub position: usize,
    /// Required minimum prime value (0 = no minimum).
    pub min_prime: u32,
    /// Required maximum prime value (0 = no maximum).
    pub max_prime: u32,
    /// Gap size at this position.
    pub gap_size: u32,
    /// Whether the gap has been satisfied.
    pub is_satisfied: bool,
}

impl RecursiveSolverState {
    /// Create a new recursive solver state starting at position 0, depth 0.
    pub fn new() -> Self {
        Self {
            current_cursor: 0,
            current_depth: 0,
            path_stack: Vec::new(),
            constraints: Vec::new(),
            terminal_node: None,
            is_contradictory: false,
        }
    }

    /// Get the current cursor position.
    pub fn cursor(&self) -> usize {
        self.current_cursor
    }

    /// Get the current recursion depth.
    pub fn depth(&self) -> u32 {
        self.current_depth
    }

    /// Set cursor to a new position.
    pub fn set_cursor(&mut self, position: usize) {
        self.current_cursor = position;
    }

    /// Increment cursor by 1.
    pub fn advance_cursor(&mut self) {
        self.current_cursor += 1;
    }

    /// Increment recursion depth.
    pub fn increase_depth(&mut self) {
        self.current_depth += 1;
    }

    /// Decrement recursion depth.
    pub fn decrease_depth(&mut self) {
        if self.current_depth > 0 {
            self.current_depth -= 1;
        }
    }

    /// Check if we've exceeded maximum recursion depth.
    pub fn exceeds_max_depth(&self) -> bool {
        self.current_depth >= MAX_RECURSION_DEPTH
    }

    /// Push the current state (cursor, depth, node) onto the path stack.
    pub fn push_state(&mut self, node: GapTensorNode) {
        self.path_stack
            .push((self.current_cursor, self.current_depth, node));
    }

    /// Pop the most recent state from the path stack and restore it.
    pub fn pop_state(&mut self) -> Option<(usize, u32, GapTensorNode)> {
        if let Some((cursor, depth, node)) = self.path_stack.pop() {
            self.current_cursor = cursor;
            self.current_depth = depth;
            Some((cursor, depth, node))
        } else {
            None
        }
    }

    /// Peek at the top of the path stack without removing it.
    pub fn peek_state(&self) -> Option<&(usize, u32, GapTensorNode)> {
        self.path_stack.last()
    }

    /// Get the path stack length.
    pub fn path_depth(&self) -> usize {
        self.path_stack.len()
    }

    /// Add a constraint to the accumulated constraints.
    pub fn add_constraint(&mut self, constraint: GapConstraint) {
        self.constraints.push(constraint);
    }

    /// Get all accumulated constraints.
    pub fn constraints(&self) -> &[GapConstraint] {
        &self.constraints
    }

    /// Mark a constraint as satisfied.
    pub fn mark_constraint_satisfied(&mut self, idx: usize) {
        if idx < self.constraints.len() {
            self.constraints[idx].is_satisfied = true;
        }
    }

    /// Count unsatisfied constraints.
    pub fn unsatisfied_constraint_count(&self) -> usize {
        self.constraints.iter().filter(|c| !c.is_satisfied).count()
    }

    /// Set the terminal node reached during solving.
    pub fn set_terminal_node(&mut self, node: GapTensorNode) {
        self.terminal_node = Some(node);
    }

    /// Get the terminal node (if set).
    pub fn terminal_node(&self) -> Option<GapTensorNode> {
        self.terminal_node
    }

    /// Mark the state as contradictory.
    pub fn set_contradictory(&mut self) {
        self.is_contradictory = true;
    }

    /// Check if the state is contradictory.
    pub fn is_contradictory(&self) -> bool {
        self.is_contradictory
    }

    /// Clear contradictory state (e.g., after backtracking).
    pub fn clear_contradiction(&mut self) {
        self.is_contradictory = false;
    }

    /// Get a snapshot of the current state for inspection.
    pub fn snapshot(&self) -> SolverStateSnapshot {
        SolverStateSnapshot {
            cursor: self.current_cursor,
            depth: self.current_depth,
            path_depth: self.path_stack.len(),
            constraint_count: self.constraints.len(),
            unsatisfied_count: self.unsatisfied_constraint_count(),
            is_contradictory: self.is_contradictory,
            has_terminal: self.terminal_node.is_some(),
        }
    }
}

impl Default for RecursiveSolverState {
    fn default() -> Self {
        Self::new()
    }
}

/// A snapshot of the recursive solver state for inspection/logging.
#[derive(Debug, Clone)]
pub struct SolverStateSnapshot {
    /// Current cursor position.
    pub cursor: usize,
    /// Current recursion depth.
    pub depth: u32,
    /// Depth of path stack.
    pub path_depth: usize,
    /// Total constraint count.
    pub constraint_count: usize,
    /// Unsatisfied constraint count.
    pub unsatisfied_count: usize,
    /// Whether in contradiction state.
    pub is_contradictory: bool,
    /// Whether a terminal node has been set.
    pub has_terminal: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_state() {
        let state = RecursiveSolverState::new();
        assert_eq!(state.cursor(), 0);
        assert_eq!(state.depth(), 0);
        assert_eq!(state.path_depth(), 0);
        assert!(!state.is_contradictory());
    }

    #[test]
    fn test_cursor_operations() {
        let mut state = RecursiveSolverState::new();
        state.advance_cursor();
        assert_eq!(state.cursor(), 1);
        state.set_cursor(5);
        assert_eq!(state.cursor(), 5);
    }

    #[test]
    fn test_depth_operations() {
        let mut state = RecursiveSolverState::new();
        state.increase_depth();
        assert_eq!(state.depth(), 1);
        state.increase_depth();
        assert_eq!(state.depth(), 2);
        state.decrease_depth();
        assert_eq!(state.depth(), 1);
    }

    #[test]
    fn test_max_depth_check() {
        let mut state = RecursiveSolverState::new();
        for _ in 0..MAX_RECURSION_DEPTH {
            state.increase_depth();
        }
        assert!(state.exceeds_max_depth());
    }

    #[test]
    fn test_path_stack_operations() {
        let mut state = RecursiveSolverState::new();
        let node = GapTensorNode::new(2, 1, 1.0);
        state.push_state(node);
        assert_eq!(state.path_depth(), 1);
        let popped = state.pop_state();
        assert!(popped.is_some());
        assert_eq!(state.path_depth(), 0);
    }

    #[test]
    fn test_constraint_management() {
        let mut state = RecursiveSolverState::new();
        let constraint = GapConstraint {
            position: 0,
            min_prime: 2,
            max_prime: 13,
            gap_size: 4,
            is_satisfied: false,
        };
        state.add_constraint(constraint);
        assert_eq!(state.constraints().len(), 1);
        assert_eq!(state.unsatisfied_constraint_count(), 1);
        state.mark_constraint_satisfied(0);
        assert_eq!(state.unsatisfied_constraint_count(), 0);
    }

    #[test]
    fn test_terminal_node() {
        let mut state = RecursiveSolverState::new();
        let node = GapTensorNode::new(13, 1, 1.0);
        state.set_terminal_node(node);
        assert_eq!(state.terminal_node().unwrap().prime_val, 13);
    }

    #[test]
    fn test_contradiction_state() {
        let mut state = RecursiveSolverState::new();
        assert!(!state.is_contradictory());
        state.set_contradictory();
        assert!(state.is_contradictory());
        state.clear_contradiction();
        assert!(!state.is_contradictory());
    }

    #[test]
    fn test_snapshot() {
        let mut state = RecursiveSolverState::new();
        state.advance_cursor();
        state.increase_depth();
        let snapshot = state.snapshot();
        assert_eq!(snapshot.cursor, 1);
        assert_eq!(snapshot.depth, 1);
        assert!(!snapshot.is_contradictory);
    }
}

