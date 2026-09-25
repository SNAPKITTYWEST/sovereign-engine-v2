//! recursion_depth_management
//!
//! Manage recursion depth stack, backtrack points, and depth limits.
//! Provides a stack of depth markers and allows efficient depth-based backtracking.

#![warn(missing_docs)]

use recursive_solver_state::MAX_RECURSION_DEPTH;

/// A marker for a backtrack point at a specific depth.
#[derive(Debug, Clone, Copy)]
pub struct DepthMarker {
    /// The depth level of this marker.
    pub depth: u32,
    /// Index in the depth stack.
    pub stack_index: usize,
}

/// Manages recursion depth and backtrack points.
#[derive(Debug, Clone)]
pub struct DepthManager {
    /// Stack of depth levels traversed.
    depth_stack: Vec<u32>,
    /// Stack of backtrack points (depth, cursor position pairs).
    backtrack_points: Vec<(u32, usize)>,
    /// Current maximum allowed depth.
    max_allowed_depth: u32,
}

impl DepthManager {
    /// Create a new depth manager.
    pub fn new() -> Self {
        Self {
            depth_stack: vec![0], // Start at depth 0
            backtrack_points: Vec::new(),
            max_allowed_depth: MAX_RECURSION_DEPTH,
        }
    }

    /// Create with a custom maximum depth.
    pub fn with_max_depth(max_depth: u32) -> Self {
        Self {
            depth_stack: vec![0],
            backtrack_points: Vec::new(),
            max_allowed_depth: max_depth,
        }
    }

    /// Get the current depth.
    pub fn current_depth(&self) -> u32 {
        *self.depth_stack.last().unwrap_or(&0)
    }

    /// Get the maximum allowed depth.
    pub fn max_allowed_depth(&self) -> u32 {
        self.max_allowed_depth
    }

    /// Check if we can increase depth.
    pub fn can_increase_depth(&self) -> bool {
        self.current_depth() < self.max_allowed_depth
    }

    /// Increase depth and return the new depth.
    pub fn increase_depth(&mut self) -> Option<u32> {
        if self.can_increase_depth() {
            let new_depth = self.current_depth() + 1;
            self.depth_stack.push(new_depth);
            Some(new_depth)
        } else {
            None
        }
    }

    /// Decrease depth and return the previous depth.
    pub fn decrease_depth(&mut self) -> Option<u32> {
        if self.depth_stack.len() > 1 {
            Some(self.depth_stack.pop().unwrap())
        } else {
            None
        }
    }

    /// Mark a backtrack point at the current depth.
    pub fn mark_backtrack_point(&mut self, cursor: usize) {
        self.backtrack_points
            .push((self.current_depth(), cursor));
    }

    /// Get the most recent backtrack point.
    pub fn last_backtrack_point(&self) -> Option<(u32, usize)> {
        self.backtrack_points.last().copied()
    }

    /// Pop and return the most recent backtrack point.
    pub fn pop_backtrack_point(&mut self) -> Option<(u32, usize)> {
        self.backtrack_points.pop()
    }

    /// Get all backtrack points at or above a given depth.
    pub fn backtrack_points_at_depth(&self, depth: u32) -> Vec<(u32, usize)> {
        self.backtrack_points
            .iter()
            .filter(|(d, _)| *d >= depth)
            .copied()
            .collect()
    }

    /// Clear all backtrack points at or above a given depth.
    pub fn clear_backtrack_points_at_depth(&mut self, depth: u32) {
        self.backtrack_points.retain(|(d, _)| *d < depth);
    }

    /// Get the full depth stack.
    pub fn depth_stack(&self) -> &[u32] {
        &self.depth_stack
    }

    /// Get the depth stack length.
    pub fn depth_stack_len(&self) -> usize {
        self.depth_stack.len()
    }

    /// Check if we're at depth 0 (top level).
    pub fn is_top_level(&self) -> bool {
        self.current_depth() == 0
    }

    /// Reset to depth 0 and clear backtrack points.
    pub fn reset(&mut self) {
        self.depth_stack.clear();
        self.depth_stack.push(0);
        self.backtrack_points.clear();
    }

    /// Get the path from top-level to current depth.
    pub fn depth_path(&self) -> Vec<u32> {
        self.depth_stack.clone()
    }

    /// Check if a specific depth has been visited.
    pub fn has_visited_depth(&self, depth: u32) -> bool {
        self.depth_stack.contains(&depth)
    }
}

impl Default for DepthManager {
    fn default() -> Self {
        Self::new()
    }
}

/// Utility to manage nested recursion with automatic depth tracking.
#[derive(Debug, Clone)]
pub struct RecursionContext {
    /// The depth manager.
    manager: DepthManager,
    /// Context ID for tracking.
    context_id: u64,
}

impl RecursionContext {
    /// Create a new recursion context.
    pub fn new() -> Self {
        Self {
            manager: DepthManager::new(),
            context_id: 0,
        }
    }

    /// Enter a new recursion level, returning the depth context.
    pub fn enter(&mut self) -> Option<RecursionDepthGuard> {
        if let Some(depth) = self.manager.increase_depth() {
            Some(RecursionDepthGuard {
                context_id: self.context_id,
                depth,
            })
        } else {
            None
        }
    }

    /// Get the current manager.
    pub fn manager(&self) -> &DepthManager {
        &self.manager
    }

    /// Get a mutable reference to the manager.
    pub fn manager_mut(&mut self) -> &mut DepthManager {
        &mut self.manager
    }
}

impl Default for RecursionContext {
    fn default() -> Self {
        Self::new()
    }
}

/// RAII guard for managing depth on exit of a scope.
#[derive(Debug)]
pub struct RecursionDepthGuard {
    #[allow(dead_code)]
    context_id: u64,
    depth: u32,
}

impl RecursionDepthGuard {
    /// Get the depth of this guard.
    pub fn depth(&self) -> u32 {
        self.depth
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_depth_manager_creation() {
        let manager = DepthManager::new();
        assert_eq!(manager.current_depth(), 0);
        assert!(manager.is_top_level());
    }

    #[test]
    fn test_increase_depth() {
        let mut manager = DepthManager::new();
        let depth = manager.increase_depth();
        assert_eq!(depth, Some(1));
        assert_eq!(manager.current_depth(), 1);
        assert!(!manager.is_top_level());
    }

    #[test]
    fn test_decrease_depth() {
        let mut manager = DepthManager::new();
        manager.increase_depth();
        manager.increase_depth();
        let prev = manager.decrease_depth();
        assert_eq!(prev, Some(2));
        assert_eq!(manager.current_depth(), 1);
    }

    #[test]
    fn test_max_depth_limit() {
        let mut manager = DepthManager::with_max_depth(2);
        assert!(manager.increase_depth().is_some());
        assert_eq!(manager.current_depth(), 1);
        assert!(manager.increase_depth().is_some());
        assert_eq!(manager.current_depth(), 2);
        assert!(manager.increase_depth().is_none());
        assert_eq!(manager.current_depth(), 2);
    }

    #[test]
    fn test_backtrack_points() {
        let mut manager = DepthManager::new();
        manager.increase_depth();
        manager.mark_backtrack_point(10);
        assert_eq!(manager.last_backtrack_point(), Some((1, 10)));
        let popped = manager.pop_backtrack_point();
        assert_eq!(popped, Some((1, 10)));
        assert!(manager.pop_backtrack_point().is_none());
    }

    #[test]
    fn test_backtrack_points_at_depth() {
        let mut manager = DepthManager::new();
        manager.increase_depth();
        manager.mark_backtrack_point(5);
        manager.increase_depth();
        manager.mark_backtrack_point(10);
        let points = manager.backtrack_points_at_depth(1);
        assert_eq!(points.len(), 2);
    }

    #[test]
    fn test_clear_backtrack_points_at_depth() {
        let mut manager = DepthManager::new();
        manager.mark_backtrack_point(1);
        manager.increase_depth();
        manager.mark_backtrack_point(5);
        manager.increase_depth();
        manager.mark_backtrack_point(10);
        manager.clear_backtrack_points_at_depth(2);
        assert_eq!(manager.last_backtrack_point(), Some((1, 5)));
    }

    #[test]
    fn test_depth_path() {
        let mut manager = DepthManager::new();
        manager.increase_depth();
        manager.increase_depth();
        let path = manager.depth_path();
        assert_eq!(path, vec![0, 1, 2]);
    }

    #[test]
    fn test_has_visited_depth() {
        let mut manager = DepthManager::new();
        assert!(manager.has_visited_depth(0));
        manager.increase_depth();
        assert!(manager.has_visited_depth(1));
        assert!(!manager.has_visited_depth(5));
    }

    #[test]
    fn test_reset() {
        let mut manager = DepthManager::new();
        manager.increase_depth();
        manager.increase_depth();
        manager.mark_backtrack_point(5);
        manager.reset();
        assert_eq!(manager.current_depth(), 0);
        assert!(manager.pop_backtrack_point().is_none());
    }
}

