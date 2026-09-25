//! recursion_backtracking
//!
//! Backtracking mechanisms for recursive solver. Manages backtrack stacks,
//! checkpoint saving, and state restoration during constraint satisfaction failures.

#![warn(missing_docs)]

use recursive_solver_state::RecursiveSolverState;
use recursion_depth_management::DepthManager;

/// A checkpoint that can be restored.
#[derive(Debug, Clone)]
pub struct Checkpoint {
    /// The solver state at this checkpoint.
    pub state: RecursiveSolverState,
    /// The depth at this checkpoint.
    pub depth: u32,
    /// Checkpoint ID for tracking.
    pub id: u64,
}

impl Checkpoint {
    /// Create a new checkpoint.
    pub fn new(state: RecursiveSolverState, depth: u32, id: u64) -> Self {
        Self { state, depth, id }
    }
}

/// Backtrack strategy for recovery.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BacktrackStrategy {
    /// Go back to the most recent checkpoint.
    LastCheckpoint,
    /// Go back to a specific depth.
    ToDepth(u32),
    /// Go back N steps.
    NSteps(usize),
    /// Go back to the root state.
    ToRoot,
}

/// Manages backtracking during recursive solving.
#[derive(Debug, Clone)]
pub struct BacktrackManager {
    /// Stack of checkpoints.
    checkpoints: Vec<Checkpoint>,
    /// Stack of failed branch attempts.
    failed_branches: Vec<(usize, String)>, // (checkpoint_id, reason)
    /// Current checkpoint counter.
    checkpoint_counter: u64,
}

impl BacktrackManager {
    /// Create a new backtrack manager.
    pub fn new() -> Self {
        Self {
            checkpoints: Vec::new(),
            failed_branches: Vec::new(),
            checkpoint_counter: 0,
        }
    }

    /// Save a checkpoint.
    pub fn save_checkpoint(&mut self, state: RecursiveSolverState, depth: u32) -> u64 {
        let id = self.checkpoint_counter;
        self.checkpoint_counter += 1;
        let checkpoint = Checkpoint::new(state, depth, id);
        self.checkpoints.push(checkpoint);
        id
    }

    /// Get the most recent checkpoint.
    pub fn last_checkpoint(&self) -> Option<&Checkpoint> {
        self.checkpoints.last()
    }

    /// Pop and return the most recent checkpoint.
    pub fn pop_checkpoint(&mut self) -> Option<Checkpoint> {
        self.checkpoints.pop()
    }

    /// Get a checkpoint by ID.
    pub fn checkpoint_by_id(&self, id: u64) -> Option<&Checkpoint> {
        self.checkpoints.iter().find(|cp| cp.id == id)
    }

    /// Get the number of checkpoints.
    pub fn checkpoint_count(&self) -> usize {
        self.checkpoints.len()
    }

    /// Record a failed branch.
    pub fn record_failed_branch(&mut self, checkpoint_id: u64, reason: String) {
        self.failed_branches.push((checkpoint_id as usize, reason));
    }

    /// Get failed branch records.
    pub fn failed_branches(&self) -> &[(usize, String)] {
        &self.failed_branches
    }

    /// Backtrack using a specific strategy.
    pub fn backtrack(&mut self, strategy: BacktrackStrategy) -> Option<Checkpoint> {
        match strategy {
            BacktrackStrategy::LastCheckpoint => self.pop_checkpoint(),
            BacktrackStrategy::ToDepth(target_depth) => {
                // Pop until we reach target depth
                while let Some(cp) = self.checkpoints.last() {
                    if cp.depth <= target_depth {
                        return self.pop_checkpoint();
                    }
                    self.checkpoints.pop();
                }
                None
            }
            BacktrackStrategy::NSteps(n) => {
                for _ in 0..n {
                    if self.checkpoints.is_empty() {
                        return None;
                    }
                    self.checkpoints.pop();
                }
                self.pop_checkpoint()
            }
            BacktrackStrategy::ToRoot => {
                // Keep only the first checkpoint
                if let Some(first) = self.checkpoints.first().cloned() {
                    self.checkpoints.clear();
                    self.checkpoints.push(first.clone());
                    Some(first)
                } else {
                    None
                }
            }
        }
    }

    /// Clear all checkpoints and failed branches.
    pub fn reset(&mut self) {
        self.checkpoints.clear();
        self.failed_branches.clear();
    }

    /// Get checkpoint stack depth.
    pub fn stack_depth(&self) -> usize {
        self.checkpoints.len()
    }

    /// Check if there are saved checkpoints to backtrack to.
    pub fn can_backtrack(&self) -> bool {
        self.checkpoints.len() > 1
    }
}

impl Default for BacktrackManager {
    fn default() -> Self {
        Self::new()
    }
}

/// Combines backtracking with depth management.
#[derive(Debug, Clone)]
pub struct BacktrackContext {
    /// The backtrack manager.
    backtrack: BacktrackManager,
    /// The depth manager.
    depth_mgr: DepthManager,
    /// Total backtrack operations performed.
    backtrack_count: usize,
}

impl BacktrackContext {
    /// Create a new backtrack context.
    pub fn new(backtrack: BacktrackManager, depth_mgr: DepthManager) -> Self {
        Self {
            backtrack,
            depth_mgr,
            backtrack_count: 0,
        }
    }

    /// Save the current state.
    pub fn save(&mut self, state: RecursiveSolverState) -> u64 {
        self.backtrack.save_checkpoint(state, self.depth_mgr.current_depth())
    }

    /// Perform a backtrack operation.
    pub fn backtrack(&mut self, strategy: BacktrackStrategy) -> Option<Checkpoint> {
        let result = self.backtrack.backtrack(strategy);
        if result.is_some() {
            self.backtrack_count += 1;
        }
        result
    }

    /// Get total backtrack operations.
    pub fn total_backtracks(&self) -> usize {
        self.backtrack_count
    }

    /// Get the backtrack manager.
    pub fn backtrack_manager(&self) -> &BacktrackManager {
        &self.backtrack
    }

    /// Get the depth manager.
    pub fn depth_manager(&self) -> &DepthManager {
        &self.depth_mgr
    }
}

impl Default for BacktrackContext {
    fn default() -> Self {
        Self::new(BacktrackManager::new(), DepthManager::new())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_checkpoint_creation() {
        let state = RecursiveSolverState::new();
        let checkpoint = Checkpoint::new(state, 0, 1);
        assert_eq!(checkpoint.depth, 0);
        assert_eq!(checkpoint.id, 1);
    }

    #[test]
    fn test_backtrack_manager_creation() {
        let manager = BacktrackManager::new();
        assert_eq!(manager.checkpoint_count(), 0);
        assert!(!manager.can_backtrack());
    }

    #[test]
    fn test_save_checkpoint() {
        let mut manager = BacktrackManager::new();
        let state = RecursiveSolverState::new();
        let id = manager.save_checkpoint(state, 0);
        assert_eq!(manager.checkpoint_count(), 1);
        assert_eq!(id, 0);
    }

    #[test]
    fn test_pop_checkpoint() {
        let mut manager = BacktrackManager::new();
        let state = RecursiveSolverState::new();
        manager.save_checkpoint(state, 0);
        let popped = manager.pop_checkpoint();
        assert!(popped.is_some());
        assert_eq!(manager.checkpoint_count(), 0);
    }

    #[test]
    fn test_backtrack_last_checkpoint() {
        let mut manager = BacktrackManager::new();
        let state = RecursiveSolverState::new();
        manager.save_checkpoint(state.clone(), 0);
        manager.save_checkpoint(state, 1);
        let backtracked = manager.backtrack(BacktrackStrategy::LastCheckpoint);
        assert!(backtracked.is_some());
        assert_eq!(manager.checkpoint_count(), 1);
    }

    #[test]
    fn test_backtrack_to_depth() {
        let mut manager = BacktrackManager::new();
        let state = RecursiveSolverState::new();
        manager.save_checkpoint(state.clone(), 0);
        manager.save_checkpoint(state.clone(), 1);
        manager.save_checkpoint(state.clone(), 2);
        manager.backtrack(BacktrackStrategy::ToDepth(1));
        let last = manager.last_checkpoint();
        assert!(last.is_some());
    }

    #[test]
    fn test_record_failed_branch() {
        let mut manager = BacktrackManager::new();
        manager.record_failed_branch(0, "Constraint violation".to_string());
        assert_eq!(manager.failed_branches().len(), 1);
    }

    #[test]
    fn test_backtrack_context() {
        let mut ctx = BacktrackContext::default();
        let state = RecursiveSolverState::new();
        ctx.save(state);
        assert_eq!(ctx.total_backtracks(), 0);
    }

    #[test]
    fn test_reset() {
        let mut manager = BacktrackManager::new();
        let state = RecursiveSolverState::new();
        manager.save_checkpoint(state, 0);
        manager.record_failed_branch(0, "test".to_string());
        manager.reset();
        assert_eq!(manager.checkpoint_count(), 0);
        assert!(manager.failed_branches().is_empty());
    }
}

