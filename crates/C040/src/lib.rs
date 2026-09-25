//! recursive_solver_trace
//!
//! Complete trace reconstruction for recursive solver execution.
//! Provides full execution logs, replay capability, and trace analysis.

#![warn(missing_docs)]

use recursive_solver_transition::TransitionResult;
use recursion_solution_path::SolutionPath;
use std::time::{SystemTime, UNIX_EPOCH};

/// An execution event in the solver trace.
#[derive(Debug, Clone)]
pub struct ExecutionEvent {
    /// Event sequence number.
    pub event_id: u64,
    /// Timestamp (milliseconds since epoch).
    pub timestamp_ms: u128,
    /// Type of event.
    pub event_type: EventType,
    /// Detailed message.
    pub message: String,
    /// Depth at time of event.
    pub depth: u32,
    /// Cursor position at time of event.
    pub cursor_position: usize,
}

/// Types of events in the execution trace.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EventType {
    /// Solver started.
    Start,
    /// Transition applied.
    Transition,
    /// Constraint checked.
    ConstraintCheck,
    /// Backtrack occurred.
    Backtrack,
    /// Solution found.
    Solution,
    /// Contradiction detected.
    Contradiction,
    /// Base case reached.
    BaseCase,
    /// Solver ended.
    End,
}

impl std::fmt::Display for EventType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Start => write!(f, "Start"),
            Self::Transition => write!(f, "Transition"),
            Self::ConstraintCheck => write!(f, "ConstraintCheck"),
            Self::Backtrack => write!(f, "Backtrack"),
            Self::Solution => write!(f, "Solution"),
            Self::Contradiction => write!(f, "Contradiction"),
            Self::BaseCase => write!(f, "BaseCase"),
            Self::End => write!(f, "End"),
        }
    }
}

/// Complete execution trace of solver.
#[derive(Debug, Clone)]
pub struct ExecutionTrace {
    /// Sequence of execution events.
    events: Vec<ExecutionEvent>,
    /// Event counter.
    event_counter: u64,
    /// Total execution time (ms).
    total_time_ms: u128,
    /// Solution paths found.
    solution_paths: Vec<SolutionPath>,
}

impl ExecutionTrace {
    /// Create a new execution trace.
    pub fn new() -> Self {
        Self {
            events: Vec::new(),
            event_counter: 0,
            total_time_ms: 0,
            solution_paths: Vec::new(),
        }
    }

    /// Record an execution event.
    pub fn record_event(
        &mut self,
        event_type: EventType,
        message: String,
        depth: u32,
        cursor_position: usize,
    ) {
        let timestamp_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis())
            .unwrap_or(0);

        let event = ExecutionEvent {
            event_id: self.event_counter,
            timestamp_ms,
            event_type,
            message,
            depth,
            cursor_position,
        };
        self.events.push(event);
        self.event_counter += 1;
    }

    /// Record a transition event from result.
    pub fn record_transition(&mut self, result: &TransitionResult, depth: u32, cursor: usize) {
        let message = format!(
            "{:?}: {}",
            result.operator,
            if result.success { "success" } else { "failed" }
        );
        self.record_event(EventType::Transition, message, depth, cursor);
    }

    /// Add a completed solution path.
    pub fn record_solution(&mut self, path: SolutionPath) {
        self.solution_paths.push(path);
        self.record_event(
            EventType::Solution,
            "Solution found".to_string(),
            0,
            0,
        );
    }

    /// Get all events in the trace.
    pub fn events(&self) -> &[ExecutionEvent] {
        &self.events
    }

    /// Get event count.
    pub fn event_count(&self) -> usize {
        self.events.len()
    }

    /// Get events of a specific type.
    pub fn events_by_type(&self, event_type: EventType) -> Vec<&ExecutionEvent> {
        self.events
            .iter()
            .filter(|e| e.event_type == event_type)
            .collect()
    }

    /// Get solution paths found.
    pub fn solution_paths(&self) -> &[SolutionPath] {
        &self.solution_paths
    }

    /// Set total execution time.
    pub fn set_total_time_ms(&mut self, time: u128) {
        self.total_time_ms = time;
    }

    /// Get total execution time.
    pub fn total_time_ms(&self) -> u128 {
        self.total_time_ms
    }

    /// Get trace statistics.
    pub fn stats(&self) -> TraceStats {
        let total_transitions = self
            .events
            .iter()
            .filter(|e| e.event_type == EventType::Transition)
            .count();
        let total_backtracks = self
            .events
            .iter()
            .filter(|e| e.event_type == EventType::Backtrack)
            .count();
        let total_contradictions = self
            .events
            .iter()
            .filter(|e| e.event_type == EventType::Contradiction)
            .count();
        let solutions_found = self.solution_paths.len();

        TraceStats {
            total_events: self.events.len(),
            total_transitions,
            total_backtracks,
            total_contradictions,
            solutions_found,
            total_time_ms: self.total_time_ms,
        }
    }

    /// Generate a formatted trace report.
    pub fn format_trace(&self) -> String {
        let mut result = String::new();
        result.push_str("=== EXECUTION TRACE ===\n\n");

        for event in &self.events {
            result.push_str(&format!(
                "[{:04}] @{:3}ms depth={} cursor={} | {}: {}\n",
                event.event_id,
                event.timestamp_ms % 1000,
                event.depth,
                event.cursor_position,
                event.event_type,
                event.message
            ));
        }

        result.push_str("\n=== SOLUTIONS ===\n\n");
        for (i, path) in self.solution_paths.iter().enumerate() {
            result.push_str(&format!("Solution {}:\n", i + 1));
            result.push_str(&path.format_path());
            result.push('\n');
        }

        result
    }

    /// Replay trace up to a specific event ID.
    pub fn replay_until(&self, event_id: u64) -> Vec<&ExecutionEvent> {
        self.events
            .iter()
            .filter(|e| e.event_id <= event_id)
            .collect()
    }

    /// Get events within a time range (milliseconds).
    pub fn events_in_time_range(&self, start_ms: u128, end_ms: u128) -> Vec<&ExecutionEvent> {
        self.events
            .iter()
            .filter(|e| e.timestamp_ms >= start_ms && e.timestamp_ms <= end_ms)
            .collect()
    }
}

impl Default for ExecutionTrace {
    fn default() -> Self {
        Self::new()
    }
}

/// Statistics about the execution trace.
#[derive(Debug, Clone)]
pub struct TraceStats {
    /// Total events recorded.
    pub total_events: usize,
    /// Total transitions executed.
    pub total_transitions: usize,
    /// Total backtracks performed.
    pub total_backtracks: usize,
    /// Total contradictions found.
    pub total_contradictions: usize,
    /// Solutions found.
    pub solutions_found: usize,
    /// Total execution time (ms).
    pub total_time_ms: u128,
}

impl TraceStats {
    /// Get the success rate (solutions / transitions).
    pub fn success_rate(&self) -> f64 {
        if self.total_transitions == 0 {
            0.0
        } else {
            (self.solutions_found as f64) / (self.total_transitions as f64)
        }
    }

    /// Get the contradiction rate.
    pub fn contradiction_rate(&self) -> f64 {
        if self.total_events == 0 {
            0.0
        } else {
            (self.total_contradictions as f64) / (self.total_events as f64)
        }
    }

    /// Get average time per transition (ms).
    pub fn avg_time_per_transition(&self) -> f64 {
        if self.total_transitions == 0 {
            0.0
        } else {
            (self.total_time_ms as f64) / (self.total_transitions as f64)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_execution_event_creation() {
        let event = ExecutionEvent {
            event_id: 0,
            timestamp_ms: 1000,
            event_type: EventType::Start,
            message: "Solver started".to_string(),
            depth: 0,
            cursor_position: 0,
        };
        assert_eq!(event.event_id, 0);
        assert_eq!(event.event_type, EventType::Start);
    }

    #[test]
    fn test_trace_creation() {
        let trace = ExecutionTrace::new();
        assert_eq!(trace.event_count(), 0);
    }

    #[test]
    fn test_record_event() {
        let mut trace = ExecutionTrace::new();
        trace.record_event(
            EventType::Start,
            "Starting solver".to_string(),
            0,
            0,
        );
        assert_eq!(trace.event_count(), 1);
    }

    #[test]
    fn test_events_by_type() {
        let mut trace = ExecutionTrace::new();
        trace.record_event(EventType::Start, "Start".to_string(), 0, 0);
        trace.record_event(EventType::Transition, "Transition".to_string(), 1, 1);
        trace.record_event(EventType::Start, "Another start".to_string(), 0, 0);

        let starts = trace.events_by_type(EventType::Start);
        assert_eq!(starts.len(), 2);
    }

    #[test]
    fn test_trace_stats() {
        let mut trace = ExecutionTrace::new();
        trace.record_event(EventType::Start, "Start".to_string(), 0, 0);
        trace.record_event(EventType::Transition, "Trans".to_string(), 1, 1);
        trace.record_event(EventType::Backtrack, "Back".to_string(), 0, 0);
        trace.set_total_time_ms(100);

        let stats = trace.stats();
        assert_eq!(stats.total_events, 3);
        assert_eq!(stats.total_transitions, 1);
        assert_eq!(stats.total_backtracks, 1);
    }

    #[test]
    fn test_format_trace() {
        let mut trace = ExecutionTrace::new();
        trace.record_event(EventType::Start, "Starting".to_string(), 0, 0);
        let formatted = trace.format_trace();
        assert!(formatted.contains("EXECUTION TRACE"));
        assert!(formatted.contains("Starting"));
    }

    #[test]
    fn test_replay_until() {
        let mut trace = ExecutionTrace::new();
        trace.record_event(EventType::Start, "Start".to_string(), 0, 0);
        trace.record_event(EventType::Transition, "Trans".to_string(), 1, 1);
        trace.record_event(EventType::End, "End".to_string(), 0, 0);

        let replayed = trace.replay_until(1);
        assert_eq!(replayed.len(), 2);
    }

    #[test]
    fn test_trace_stats_rates() {
        let stats = TraceStats {
            total_events: 100,
            total_transitions: 10,
            total_backtracks: 2,
            total_contradictions: 5,
            solutions_found: 3,
            total_time_ms: 1000,
        };
        assert!((stats.success_rate() - 0.3).abs() < 0.01);
        assert!((stats.contradiction_rate() - 0.05).abs() < 0.01);
    }
}

