//! recursive_solver_cursor
//!
//! Cursor management for gap sequence position tracking during recursive solving.
//! Validates positions against candidate gaps, tracks visited positions, and manages
//! forward/backward movement through the gap sequence.

#![warn(missing_docs)]

use gap_candidate_set::GapCandidateSet;

/// Represents a position in a gap sequence with validity information.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CursorPosition {
    /// The index in the gap sequence.
    pub index: usize,
    /// Whether this position has been visited.
    pub visited: bool,
    /// Whether this position is valid (in the candidate set).
    pub is_valid: bool,
}

impl CursorPosition {
    /// Create a new cursor position.
    pub fn new(index: usize, visited: bool, is_valid: bool) -> Self {
        Self {
            index,
            visited,
            is_valid,
        }
    }
}

/// Cursor for navigating through a gap sequence during recursive solving.
#[derive(Debug, Clone)]
pub struct RecursiveSolverCursor {
    /// The candidate set underlying this cursor.
    candidate_gaps: Vec<(u64, u64, u64)>, // (prime1, prime2, gap)
    /// Current cursor position (0-indexed).
    position: usize,
    /// Set of visited positions.
    visited: Vec<bool>,
    /// Set of valid positions (pre-validated against candidate set).
    valid: Vec<bool>,
}

impl RecursiveSolverCursor {
    /// A cursor over every consecutive-prime gap of the set (every gap is
    /// at least 1).
    pub fn new(gap_set: GapCandidateSet) -> Self {
        Self::with_min_gap(gap_set, 1)
    }

    /// A cursor over the consecutive-prime gaps of size at least `min_gap`.
    pub fn with_min_gap(gap_set: GapCandidateSet, min_gap: u64) -> Self {
        Self::from_gaps(gap_set.candidates_with_gap(min_gap))
    }

    /// Create a cursor from a pre-computed list of gaps.
    pub fn from_gaps(gaps: Vec<(u64, u64, u64)>) -> Self {
        let len = gaps.len();
        Self {
            candidate_gaps: gaps,
            position: 0,
            visited: vec![false; len],
            valid: vec![true; len],
        }
    }

    /// Get the current position.
    pub fn position(&self) -> usize {
        self.position
    }

    /// Set the position to an absolute index.
    pub fn set_position(&mut self, index: usize) -> bool {
        if index < self.candidate_gaps.len() {
            self.position = index;
            true
        } else {
            false
        }
    }

    /// Advance cursor by one position (if possible).
    pub fn advance(&mut self) -> bool {
        if self.position + 1 < self.candidate_gaps.len() {
            self.position += 1;
            self.mark_visited(self.position);
            true
        } else {
            false
        }
    }

    /// Retreat cursor by one position (if possible).
    pub fn retreat(&mut self) -> bool {
        if self.position > 0 {
            self.position -= 1;
            true
        } else {
            false
        }
    }

    /// Jump to the end of the sequence.
    pub fn jump_to_end(&mut self) {
        if !self.candidate_gaps.is_empty() {
            self.position = self.candidate_gaps.len() - 1;
            self.mark_visited(self.position);
        }
    }

    /// Jump to the beginning of the sequence.
    pub fn jump_to_start(&mut self) {
        self.position = 0;
        self.mark_visited(0);
    }

    /// Check if at the end of the sequence.
    pub fn is_at_end(&self) -> bool {
        self.position == self.candidate_gaps.len().saturating_sub(1)
    }

    /// Check if at the start of the sequence.
    pub fn is_at_start(&self) -> bool {
        self.position == 0
    }

    /// Get the current gap (prime1, prime2, gap_size).
    pub fn current_gap(&self) -> Option<(u64, u64, u64)> {
        if self.position < self.candidate_gaps.len() {
            Some(self.candidate_gaps[self.position])
        } else {
            None
        }
    }

    /// Get the gap at a specific position.
    pub fn gap_at(&self, index: usize) -> Option<(u64, u64, u64)> {
        if index < self.candidate_gaps.len() {
            Some(self.candidate_gaps[index])
        } else {
            None
        }
    }

    /// Get all gaps in the sequence.
    pub fn all_gaps(&self) -> &[(u64, u64, u64)] {
        &self.candidate_gaps
    }

    /// Get the total number of gaps.
    pub fn total_gaps(&self) -> usize {
        self.candidate_gaps.len()
    }

    /// Mark a position as visited.
    pub fn mark_visited(&mut self, index: usize) {
        if index < self.visited.len() {
            self.visited[index] = true;
        }
    }

    /// Check if a position has been visited.
    pub fn is_visited(&self, index: usize) -> bool {
        if index < self.visited.len() {
            self.visited[index]
        } else {
            false
        }
    }

    /// Get the number of visited positions.
    pub fn visited_count(&self) -> usize {
        self.visited.iter().filter(|&&v| v).count()
    }

    /// Get unvisited positions.
    pub fn unvisited_positions(&self) -> Vec<usize> {
        self.visited
            .iter()
            .enumerate()
            .filter_map(|(i, &v)| if !v { Some(i) } else { None })
            .collect()
    }

    /// Check if a position is valid.
    pub fn is_position_valid(&self, index: usize) -> bool {
        if index < self.valid.len() {
            self.valid[index]
        } else {
            false
        }
    }

    /// Mark a position as invalid.
    pub fn mark_invalid(&mut self, index: usize) {
        if index < self.valid.len() {
            self.valid[index] = false;
        }
    }

    /// Get the number of valid positions.
    pub fn valid_count(&self) -> usize {
        self.valid.iter().filter(|&&v| v).count()
    }

    /// Get the current cursor position info.
    pub fn current_position_info(&self) -> CursorPosition {
        CursorPosition::new(
            self.position,
            self.is_visited(self.position),
            self.is_position_valid(self.position),
        )
    }

    /// Reset cursor to start and clear visited/valid states.
    pub fn reset(&mut self) {
        self.position = 0;
        self.visited.fill(false);
        self.valid.fill(true);
    }

    /// Get the closest unvisited position going forward.
    pub fn next_unvisited(&self) -> Option<usize> {
        for i in self.position + 1..self.candidate_gaps.len() {
            if !self.visited[i] && self.valid[i] {
                return Some(i);
            }
        }
        None
    }

    /// Get the closest unvisited position going backward.
    pub fn prev_unvisited(&self) -> Option<usize> {
        if self.position == 0 {
            return None;
        }
        for i in (0..self.position).rev() {
            if !self.visited[i] && self.valid[i] {
                return Some(i);
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_cursor() -> RecursiveSolverCursor {
        RecursiveSolverCursor::from_gaps(vec![
            (2, 3, 1),
            (3, 5, 2),
            (5, 7, 2),
            (7, 11, 4),
            (11, 13, 2),
        ])
    }

    #[test]
    fn test_cursor_creation() {
        let cursor = create_test_cursor();
        assert_eq!(cursor.position(), 0);
        assert_eq!(cursor.total_gaps(), 5);
        assert!(cursor.is_at_start());
    }

    #[test]
    fn test_advance() {
        let mut cursor = create_test_cursor();
        assert!(cursor.advance());
        assert_eq!(cursor.position(), 1);
        assert!(cursor.is_visited(1));
    }

    #[test]
    fn test_retreat() {
        let mut cursor = create_test_cursor();
        cursor.advance();
        assert!(cursor.retreat());
        assert_eq!(cursor.position(), 0);
    }

    #[test]
    fn test_current_gap() {
        let cursor = create_test_cursor();
        let gap = cursor.current_gap();
        assert_eq!(gap, Some((2, 3, 1)));
    }

    #[test]
    fn test_gap_at() {
        let cursor = create_test_cursor();
        let gap = cursor.gap_at(2);
        assert_eq!(gap, Some((5, 7, 2)));
    }

    #[test]
    fn test_visited_tracking() {
        let mut cursor = create_test_cursor();
        assert!(!cursor.is_visited(0));
        cursor.mark_visited(0);
        assert!(cursor.is_visited(0));
    }

    #[test]
    fn test_validity_tracking() {
        let mut cursor = create_test_cursor();
        assert!(cursor.is_position_valid(2));
        cursor.mark_invalid(2);
        assert!(!cursor.is_position_valid(2));
    }

    #[test]
    fn test_jump_to_end() {
        let mut cursor = create_test_cursor();
        cursor.jump_to_end();
        assert!(cursor.is_at_end());
        assert_eq!(cursor.position(), 4);
    }

    #[test]
    fn test_next_unvisited() {
        let mut cursor = create_test_cursor();
        cursor.mark_visited(0);
        cursor.mark_visited(1);
        let next = cursor.next_unvisited();
        assert_eq!(next, Some(2));
    }

    #[test]
    fn test_prev_unvisited() {
        let mut cursor = create_test_cursor();
        cursor.advance();
        cursor.advance();
        cursor.mark_visited(1);
        let prev = cursor.prev_unvisited();
        assert_eq!(prev, Some(0));
    }

    #[test]
    fn test_unvisited_positions() {
        let mut cursor = create_test_cursor();
        cursor.mark_visited(0);
        cursor.mark_visited(2);
        let unvisited = cursor.unvisited_positions();
        assert_eq!(unvisited, vec![1, 3, 4]);
    }

    #[test]
    fn test_reset() {
        let mut cursor = create_test_cursor();
        cursor.advance();
        cursor.mark_visited(2);
        cursor.mark_invalid(1);
        cursor.reset();
        assert_eq!(cursor.position(), 0);
        assert!(!cursor.is_visited(2));
        assert!(cursor.is_position_valid(1));
    }
}

