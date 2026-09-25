//! recursive_solver_selection
//!
//! Select the next gap to process based on constraints and heuristic scoring.
//! Implements gap ranking, constraint satisfaction scoring, and selection strategies.

#![warn(missing_docs)]

use recursive_solver_cursor::RecursiveSolverCursor;

/// Scoring heuristics for gap selection.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SelectionStrategy {
    /// Select by gap size (ascending).
    SmallestFirst,
    /// Select by gap size (descending).
    LargestFirst,
    /// Select by frequency/multiplicity.
    MostCommon,
    /// Select least recently visited.
    LeastRecent,
    /// Combine multiple heuristics.
    Hybrid,
}

/// Score information for a gap candidate.
#[derive(Debug, Clone)]
pub struct GapSelectionScore {
    /// Index of the gap in the sequence.
    pub index: usize,
    /// The gap tuple (prime1, prime2, gap_size).
    pub gap: (u64, u64, u64),
    /// Overall score (higher = better).
    pub score: f64,
    /// Individual component scores.
    pub components: Vec<f64>,
}

/// Selector for choosing next gap during recursive solving.
#[derive(Debug, Clone)]
pub struct RecursiveSolverSelector {
    /// The cursor providing position info.
    cursor: RecursiveSolverCursor,
    /// Current selection strategy.
    strategy: SelectionStrategy,
    /// Selection history.
    history: Vec<usize>,
}

impl RecursiveSolverSelector {
    /// Create a new selector with a cursor and strategy.
    pub fn new(cursor: RecursiveSolverCursor, strategy: SelectionStrategy) -> Self {
        Self {
            cursor,
            strategy,
            history: Vec::new(),
        }
    }

    /// Change the selection strategy.
    pub fn set_strategy(&mut self, strategy: SelectionStrategy) {
        self.strategy = strategy;
    }

    /// Get the current strategy.
    pub fn strategy(&self) -> SelectionStrategy {
        self.strategy
    }

    /// Score a single gap based on the current strategy.
    fn score_gap(&self, index: usize, gap: (u64, u64, u64)) -> f64 {
        match self.strategy {
            SelectionStrategy::SmallestFirst => -(gap.2 as f64), // Negative so smaller gaps have higher score
            SelectionStrategy::LargestFirst => gap.2 as f64,
            SelectionStrategy::MostCommon => {
                // Frequency-based scoring
                let multiplicity = self.cursor.all_gaps().iter()
                    .filter(|&&(_, _, g)| g == gap.2)
                    .count() as f64;
                multiplicity * 10.0
            }
            SelectionStrategy::LeastRecent => {
                // Score based on how long since last visit
                let visits = self.history.iter()
                    .filter(|&&i| i == index)
                    .count() as f64;
                if visits == 0.0 { 1000.0 } else { 1.0 / visits }
            }
            SelectionStrategy::Hybrid => {
                // Combine: small gaps (weight 2), common gaps (weight 1), least recent (weight 0.5)
                let size_score = -(gap.2 as f64) * 2.0;
                let freq = self.cursor.all_gaps().iter()
                    .filter(|&&(_, _, g)| g == gap.2)
                    .count() as f64;
                let freq_score = freq * 1.0;
                let recency = self.history.iter()
                    .filter(|&&i| i == index)
                    .count() as f64;
                let recency_score = if recency == 0.0 { 500.0 } else { (1.0 / recency) * 0.5 };
                size_score + freq_score + recency_score
            }
        }
    }

    /// Score all unvisited gaps.
    pub fn score_candidates(&self) -> Vec<GapSelectionScore> {
        let unvisited = self.cursor.unvisited_positions();
        unvisited
            .into_iter()
            .filter_map(|idx| {
                if let Some(gap) = self.cursor.gap_at(idx) {
                    let score = self.score_gap(idx, gap);
                    Some(GapSelectionScore {
                        index: idx,
                        gap,
                        score,
                        components: vec![score],
                    })
                } else {
                    None
                }
            })
            .collect()
    }

    /// Select the best next gap based on scoring.
    pub fn select_next(&mut self) -> Option<(usize, (u64, u64, u64))> {
        let candidates = self.score_candidates();
        if candidates.is_empty() {
            return None;
        }
        let best = candidates.iter()
            .max_by(|a, b| a.score.partial_cmp(&b.score).unwrap_or(std::cmp::Ordering::Equal));
        if let Some(best_candidate) = best {
            self.history.push(best_candidate.index);
            Some((best_candidate.index, best_candidate.gap))
        } else {
            None
        }
    }

    /// Get the best N candidates.
    pub fn select_top_k(&self, k: usize) -> Vec<GapSelectionScore> {
        let mut candidates = self.score_candidates();
        candidates.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        candidates.truncate(k);
        candidates
    }

    /// Select based on constraint matching (gap size must satisfy constraints).
    pub fn select_by_constraint(&mut self, required_gap: u64) -> Option<(usize, (u64, u64, u64))> {
        let unvisited = self.cursor.unvisited_positions();
        for idx in unvisited {
            if let Some(gap) = self.cursor.gap_at(idx) {
                if gap.2 == required_gap {
                    self.history.push(idx);
                    return Some((idx, gap));
                }
            }
        }
        None
    }

    /// Get the selection history.
    pub fn history(&self) -> &[usize] {
        &self.history
    }

    /// Clear selection history.
    pub fn clear_history(&mut self) {
        self.history.clear();
    }

    /// Get a reference to the cursor.
    pub fn cursor(&self) -> &RecursiveSolverCursor {
        &self.cursor
    }

    /// Get a mutable reference to the cursor.
    pub fn cursor_mut(&mut self) -> &mut RecursiveSolverCursor {
        &mut self.cursor
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_selector() -> RecursiveSolverSelector {
        let cursor = RecursiveSolverCursor::from_gaps(vec![
            (2, 3, 1),
            (3, 5, 2),
            (5, 7, 2),
            (7, 11, 4),
            (11, 13, 2),
        ]);
        RecursiveSolverSelector::new(cursor, SelectionStrategy::SmallestFirst)
    }

    #[test]
    fn test_selector_creation() {
        let selector = create_test_selector();
        assert_eq!(selector.strategy(), SelectionStrategy::SmallestFirst);
        assert_eq!(selector.history().len(), 0);
    }

    #[test]
    fn test_score_candidates() {
        let selector = create_test_selector();
        let scores = selector.score_candidates();
        assert!(scores.len() > 0);
        assert!(scores.iter().all(|s| !s.score.is_nan()));
    }

    #[test]
    fn test_select_next() {
        let mut selector = create_test_selector();
        let selected = selector.select_next();
        assert!(selected.is_some());
        assert_eq!(selector.history().len(), 1);
    }

    #[test]
    fn test_select_top_k() {
        let selector = create_test_selector();
        let top = selector.select_top_k(2);
        assert!(top.len() <= 2);
    }

    #[test]
    fn test_select_by_constraint() {
        let mut selector = create_test_selector();
        let selected = selector.select_by_constraint(2);
        assert!(selected.is_some());
        let (_, gap) = selected.unwrap();
        assert_eq!(gap.2, 2);
    }

    #[test]
    fn test_strategy_change() {
        let mut selector = create_test_selector();
        selector.set_strategy(SelectionStrategy::LargestFirst);
        assert_eq!(selector.strategy(), SelectionStrategy::LargestFirst);
    }

    #[test]
    fn test_multiple_selections() {
        let mut selector = create_test_selector();
        selector.select_next();
        selector.select_next();
        selector.select_next();
        assert_eq!(selector.history().len(), 3);
    }
}

