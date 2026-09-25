# `recursive_solver_trace` (C040)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Complete trace reconstruction for recursive solver execution.
Provides full execution logs, replay capability, and trace analysis.

## Dependencies

- [C010 `gap_tensor_trace`](../C010/README.md)
- [C031 `recursive_solver_state`](../C031/README.md)
- [C035 `recursive_solver_transition`](../C035/README.md)
- [C039 `recursion_solution_path`](../C039/README.md)

## Public API

| Item | Description |
|---|---|
| `struct ExecutionEvent` | An execution event in the solver trace. |
| `enum EventType` | Types of events in the execution trace. |
| `struct ExecutionTrace` | Complete execution trace of solver. |
| `fn ExecutionTrace::new() -> Self` | Create a new execution trace. |
| `fn ExecutionTrace::record_event(&mut self, event_type: EventType, message: String, depth: u32, cursor_position: usize)` | Record an execution event. |
| `fn ExecutionTrace::record_transition(&mut self, result: &TransitionResult, depth: u32, cursor: usize)` | Record a transition event from result. |
| `fn ExecutionTrace::record_solution(&mut self, path: SolutionPath)` | Add a completed solution path, recording a Solution event at the path's final depth and position (0 and 0 for an empty path). |
| `fn ExecutionTrace::events(&self) -> &[ExecutionEvent]` | Get all events in the trace. |
| `fn ExecutionTrace::event_count(&self) -> usize` | Get event count. |
| `fn ExecutionTrace::events_by_type(&self, event_type: EventType) -> Vec<&ExecutionEvent>` | Get events of a specific type. |
| `fn ExecutionTrace::solution_paths(&self) -> &[SolutionPath]` | Get solution paths found. |
| `fn ExecutionTrace::set_total_time_ms(&mut self, time: u128)` | Set total execution time. |
| `fn ExecutionTrace::total_time_ms(&self) -> u128` | Get total execution time. |
| `fn ExecutionTrace::stats(&self) -> TraceStats` | Get trace statistics. |
| `fn ExecutionTrace::format_trace(&self) -> String` | Generate a formatted trace report. |
| `fn ExecutionTrace::replay_until(&self, event_id: u64) -> Vec<&ExecutionEvent>` | Replay trace up to a specific event ID. |
| `fn ExecutionTrace::events_in_time_range(&self, start_ms: u128, end_ms: u128) -> Vec<&ExecutionEvent>` | Get events within a time range (milliseconds). |
| `struct TraceStats` | Statistics about the execution trace. |
| `fn TraceStats::success_rate(&self) -> f64` | Get the success rate (solutions / transitions). |
| `fn TraceStats::contradiction_rate(&self) -> f64` | Get the contradiction rate. |
| `fn TraceStats::avg_time_per_transition(&self) -> f64` | Get average time per transition (ms). |

## Tests

`cargo test -p recursive_solver_trace` runs 10 unit tests.
