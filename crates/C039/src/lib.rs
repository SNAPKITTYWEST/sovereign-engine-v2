//! recursion_solution_path
//!
//! Records and manages the solution path during recursive solving.
//! Captures each transition as part of the final solution sequence.

#![warn(missing_docs)]

use recursive_solver_transition::TransitionOperator;

/// A step in a solution path.
#[derive(Debug, Clone)]
pub struct SolutionStep {
    /// Step sequence number.
    pub step_number: usize,
    /// The operator applied at this step.
    pub operator: TransitionOperator,
    /// Position in gap sequence before this step.
    pub from_position: usize,
    /// Position in gap sequence after this step.
    pub to_position: usize,
    /// Depth before this step.
    pub from_depth: u32,
    /// Depth after this step.
    pub to_depth: u32,
    /// Gap value involved (if applicable).
    pub gap_value: Option<u64>,
    /// Whether the step led to a solution branch.
    pub is_solution_branch: bool,
}

impl SolutionStep {
    /// Create a new solution step.
    pub fn new(
        step_number: usize,
        operator: TransitionOperator,
        from_pos: usize,
        to_pos: usize,
        from_d: u32,
        to_d: u32,
    ) -> Self {
        Self {
            step_number,
            operator,
            from_position: from_pos,
            to_position: to_pos,
            from_depth: from_d,
            to_depth: to_d,
            gap_value: None,
            is_solution_branch: false,
        }
    }

    /// Add gap value to the step.
    pub fn with_gap(mut self, gap: u64) -> Self {
        self.gap_value = Some(gap);
        self
    }

    /// Mark as a solution branch.
    pub fn mark_solution(mut self) -> Self {
        self.is_solution_branch = true;
        self
    }
}

/// A complete solution path consisting of multiple steps.
#[derive(Debug, Clone)]
pub struct SolutionPath {
    /// Sequence of steps.
    steps: Vec<SolutionStep>,
    /// Whether this path leads to a complete solution.
    complete: bool,
    /// Cost/depth of the solution.
    cost: usize,
    /// Constraints satisfied by this path.
    constraints_satisfied: usize,
}

impl SolutionPath {
    /// Create a new empty solution path.
    pub fn new() -> Self {
        Self {
            steps: Vec::new(),
            complete: false,
            cost: 0,
            constraints_satisfied: 0,
        }
    }

    /// Add a step to the path.
    pub fn add_step(&mut self, step: SolutionStep) {
        self.cost = step.to_depth as usize;
        self.steps.push(step);
    }

    /// Get all steps in the path.
    pub fn steps(&self) -> &[SolutionStep] {
        &self.steps
    }

    /// Get the number of steps.
    pub fn step_count(&self) -> usize {
        self.steps.len()
    }

    /// Mark path as complete (solution found).
    pub fn mark_complete(&mut self) {
        self.complete = true;
    }

    /// Check if this is a complete solution.
    pub fn is_complete(&self) -> bool {
        self.complete
    }

    /// Get the cost (depth) of this path.
    pub fn cost(&self) -> usize {
        self.cost
    }

    /// Set the number of constraints satisfied.
    pub fn set_constraints_satisfied(&mut self, count: usize) {
        self.constraints_satisfied = count;
    }

    /// Get constraints satisfied.
    pub fn constraints_satisfied(&self) -> usize {
        self.constraints_satisfied
    }

    /// Get the final position reached.
    pub fn final_position(&self) -> Option<usize> {
        self.steps.last().map(|s| s.to_position)
    }

    /// Get the final depth reached.
    pub fn final_depth(&self) -> Option<u32> {
        self.steps.last().map(|s| s.to_depth)
    }

    /// Create a formatted string representation.
    pub fn format_path(&self) -> String {
        let mut result = String::new();
        result.push_str(&format!(
            "Path ({} steps, complete: {})\n",
            self.steps.len(),
            self.complete
        ));
        for step in &self.steps {
            result.push_str(&format!(
                "  Step {}: {:?} (pos {} -> {}, depth {} -> {})",
                step.step_number,
                step.operator,
                step.from_position,
                step.to_position,
                step.from_depth,
                step.to_depth
            ));
            if let Some(gap) = step.gap_value {
                result.push_str(&format!(" [gap: {}]", gap));
            }
            result.push('\n');
        }
        result
    }
}

impl Default for SolutionPath {
    fn default() -> Self {
        Self::new()
    }
}

/// Records and manages solution paths during solving.
#[derive(Debug, Clone)]
pub struct SolutionPathRecorder {
    /// Current path being built.
    current_path: SolutionPath,
    /// Completed solution paths.
    completed_paths: Vec<SolutionPath>,
    /// Pruned paths (dead ends).
    pruned_paths: Vec<SolutionPath>,
}

impl SolutionPathRecorder {
    /// Create a new recorder.
    pub fn new() -> Self {
        Self {
            current_path: SolutionPath::new(),
            completed_paths: Vec::new(),
            pruned_paths: Vec::new(),
        }
    }

    /// Add a step to the current path.
    pub fn record_step(&mut self, step: SolutionStep) {
        self.current_path.add_step(step);
    }

    /// Complete the current path.
    pub fn complete_path(&mut self, constraints_satisfied: usize) {
        self.current_path.mark_complete();
        self.current_path.set_constraints_satisfied(constraints_satisfied);
        self.completed_paths.push(self.current_path.clone());
        self.current_path = SolutionPath::new();
    }

    /// Prune the current path (dead end).
    pub fn prune_path(&mut self) {
        self.pruned_paths.push(self.current_path.clone());
        self.current_path = SolutionPath::new();
    }

    /// Get the current path.
    pub fn current_path(&self) -> &SolutionPath {
        &self.current_path
    }

    /// Get completed solution paths.
    pub fn completed_paths(&self) -> &[SolutionPath] {
        &self.completed_paths
    }

    /// Get pruned paths.
    pub fn pruned_paths(&self) -> &[SolutionPath] {
        &self.pruned_paths
    }

    /// Get the best completed path (shortest cost).
    pub fn best_path(&self) -> Option<&SolutionPath> {
        self.completed_paths
            .iter()
            .min_by_key(|p| p.cost)
    }

    /// Get solution statistics.
    pub fn stats(&self) -> SolutionStats {
        let total_completed = self.completed_paths.len();
        let total_pruned = self.pruned_paths.len();
        let best_cost = self.best_path().map(|p| p.cost);
        let total_steps: usize = self.completed_paths.iter().map(|p| p.step_count()).sum();

        SolutionStats {
            completed_paths: total_completed,
            pruned_paths: total_pruned,
            best_cost,
            average_steps: if total_completed > 0 {
                total_steps as f64 / total_completed as f64
            } else {
                0.0
            },
        }
    }

    /// Reset the recorder.
    pub fn reset(&mut self) {
        self.current_path = SolutionPath::new();
        self.completed_paths.clear();
        self.pruned_paths.clear();
    }
}

impl Default for SolutionPathRecorder {
    fn default() -> Self {
        Self::new()
    }
}

/// Statistics about solution paths found.
#[derive(Debug, Clone)]
pub struct SolutionStats {
    /// Number of completed solution paths.
    pub completed_paths: usize,
    /// Number of pruned paths.
    pub pruned_paths: usize,
    /// Best solution cost found (if any).
    pub best_cost: Option<usize>,
    /// Average steps per completed path.
    pub average_steps: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_solution_step_creation() {
        let step = SolutionStep::new(0, TransitionOperator::Advance, 0, 1, 0, 1);
        assert_eq!(step.step_number, 0);
        assert_eq!(step.to_position, 1);
    }

    #[test]
    fn test_solution_step_with_gap() {
        let step = SolutionStep::new(0, TransitionOperator::Advance, 0, 1, 0, 1)
            .with_gap(2);
        assert_eq!(step.gap_value, Some(2));
    }

    #[test]
    fn test_solution_path_creation() {
        let path = SolutionPath::new();
        assert!(!path.is_complete());
        assert_eq!(path.step_count(), 0);
    }

    #[test]
    fn test_solution_path_add_step() {
        let mut path = SolutionPath::new();
        let step = SolutionStep::new(0, TransitionOperator::Advance, 0, 1, 0, 1);
        path.add_step(step);
        assert_eq!(path.step_count(), 1);
    }

    #[test]
    fn test_solution_path_complete() {
        let mut path = SolutionPath::new();
        path.mark_complete();
        assert!(path.is_complete());
    }

    #[test]
    fn test_recorder_creation() {
        let recorder = SolutionPathRecorder::new();
        assert_eq!(recorder.completed_paths().len(), 0);
        assert_eq!(recorder.pruned_paths().len(), 0);
    }

    #[test]
    fn test_recorder_record_step() {
        let mut recorder = SolutionPathRecorder::new();
        let step = SolutionStep::new(0, TransitionOperator::Advance, 0, 1, 0, 1);
        recorder.record_step(step);
        assert_eq!(recorder.current_path().step_count(), 1);
    }

    #[test]
    fn test_recorder_complete_path() {
        let mut recorder = SolutionPathRecorder::new();
        let step = SolutionStep::new(0, TransitionOperator::Advance, 0, 1, 0, 1);
        recorder.record_step(step);
        recorder.complete_path(1);
        assert_eq!(recorder.completed_paths().len(), 1);
    }

    #[test]
    fn test_recorder_prune_path() {
        let mut recorder = SolutionPathRecorder::new();
        let step = SolutionStep::new(0, TransitionOperator::Advance, 0, 1, 0, 1);
        recorder.record_step(step);
        recorder.prune_path();
        assert_eq!(recorder.pruned_paths().len(), 1);
    }

    #[test]
    fn test_solution_stats() {
        let mut recorder = SolutionPathRecorder::new();
        recorder.record_step(SolutionStep::new(0, TransitionOperator::Advance, 0, 1, 0, 1));
        recorder.complete_path(1);
        let stats = recorder.stats();
        assert_eq!(stats.completed_paths, 1);
    }
}

