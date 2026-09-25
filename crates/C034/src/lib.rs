//! recursive_solver_selection
//!
//! Select the next gap to process based on constraints and heuristic scoring.
//! Implements gap ranking, constraint satisfaction scoring, and selection strategies.

#![warn(missing_docs)]

use gap_multiplicity::analyze_gaps;
use recursive_solver_cursor::RecursiveSolverCursor;
use std::collections::HashMap;

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
    /// Overall score (higher = better): the sum of `components`.
    pub score: f64,
    /// Individual component scores: `[size, frequency, recency]` for
    /// `Hybrid`, a single component for every other strategy.
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

    /// Component scores of one gap under the current strategy, given how
    /// often each gap size occurs in the whole sequence.
    fn score_components(
        &self,
        index: usize,
        gap: (u64, u64, u64),
        multiplicity: &HashMap<u64, usize>,
    ) -> Vec<f64> {
        let frequency = multiplicity.get(&gap.2).copied().unwrap_or(0) as f64;
        let visits = self.history.iter().filter(|&&i| i == index).count() as f64;
        match self.strategy {
            SelectionStrategy::SmallestFirst => vec![-(gap.2 as f64)], // Negative so smaller gaps have higher score
            SelectionStrategy::LargestFirst => vec![gap.2 as f64],
            SelectionStrategy::MostCommon => vec![frequency * 10.0],
            SelectionStrategy::LeastRecent => vec![if visits == 0.0 { 1000.0 } else { 1.0 / visits }],
            // Combine: small gaps (weight 2), common gaps (weight 1), least recent (weight 0.5)
            SelectionStrategy::Hybrid => vec![
                -(gap.2 as f64) * 2.0,
                frequency,
                if visits == 0.0 { 500.0 } else { 0.5 / visits },
            ],
        }
    }

    /// Score all unvisited gaps. Gap frequencies come from
    /// `gap_multiplicity::analyze_gaps` over the cursor's whole sequence,
    /// computed once per call.
    pub fn score_candidates(&self) -> Vec<GapSelectionScore> {
        let multiplicity: HashMap<u64, usize> = analyze_gaps(self.cursor.all_gaps())
            .into_iter()
            .map(|m| (m.gap_size, m.count))
            .collect();
        self.cursor
            .unvisited_positions()
            .into_iter()
            .filter_map(|idx| {
                let gap = self.cursor.gap_at(idx)?;
                let components = self.score_components(idx, gap, &multiplicity);
                Some(GapSelectionScore {
                    index: idx,
                    gap,
                    score: components.iter().sum(),
                    components,
                })
            })
            .collect()
    }

    /// Select the best next gap based on scoring. The choice is recorded in
    /// the selection history; the cursor's visited flags are left to the
    /// caller, which marks positions visited as it processes them.
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
    fn most_common_uses_gap_multiplicity() {
        let mut selector = create_test_selector();
        selector.set_strategy(SelectionStrategy::MostCommon);
        // Gap 2 occurs three times in the sequence, gaps 1 and 4 once each.
        let scores: Vec<f64> = selector.score_candidates().iter().map(|s| s.score).collect();
        assert_eq!(scores, vec![10.0, 30.0, 30.0, 10.0, 30.0]);
        let (_, gap) = selector.select_next().unwrap();
        assert_eq!(gap.2, 2);
    }

    #[test]
    fn hybrid_reports_its_components() {
        let mut selector = create_test_selector();
        selector.set_strategy(SelectionStrategy::Hybrid);
        let scores = selector.score_candidates();
        let gap_four = scores.iter().find(|s| s.index == 3).unwrap();
        assert_eq!(gap_four.components, vec![-8.0, 1.0, 500.0]);
        assert_eq!(gap_four.score, 493.0);
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

