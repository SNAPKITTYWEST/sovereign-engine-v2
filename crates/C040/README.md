# recursive_solver_trace (C040)

## What it does
Full execution-trace recorder for the solver: timestamped `ExecutionEvent`s (8 event types), solution-path collection, replay-by-event-id, time-range queries, and derived statistics (success rate, contradiction rate, avg time/transition). Terminal crate of the recursive-solver sub-layer.

## Public API
- `ExecutionEvent { event_id, timestamp_ms, event_type, message, depth, cursor_position }`.
- `EventType` enum (8 variants: `Start`, `Transition`, `ConstraintCheck`, `Backtrack`, `Solution`, `Contradiction`, `BaseCase`, `End`) — implements `Display`.
- `ExecutionTrace::new()` — `record_event(...)`, `record_transition(&TransitionResult, depth, cursor)` (convenience wrapper), `record_solution(SolutionPath)`.
- `events()`, `event_count()`, `events_by_type(EventType)`, `solution_paths()`.
- `set_total_time_ms()`/`total_time_ms()`.
- `stats() -> TraceStats`, `format_trace() -> String` (full human-readable report with events + solutions section).
- `replay_until(event_id)`, `events_in_time_range(start_ms, end_ms)`.
- `TraceStats { total_events, total_transitions, total_backtracks, total_contradictions, solutions_found, total_time_ms }` with `success_rate()`, `contradiction_rate()`, `avg_time_per_transition()`.

## Pipeline position
Depends on `gap_tensor_trace` (C010, declared, unused), `recursive_solver_state` (C031, declared, unused), `recursive_solver_transition` (C035) for `TransitionResult`, and `recursion_solution_path` (C039) for `SolutionPath`. This is the terminal aggregation point of the recursive-solver layer (C031–C040) — nothing downstream in this range consumes it, so it's presumably read by the runtime-binding/certification layer (C0??, outside this range) to produce final certified traces.

## Notes / gaps
- **Note:** `timestamp_ms` uses `SystemTime::now()` (wall-clock), not a monotonic clock or logical step counter — traces are not reproducible/deterministic across runs purely from timestamps; `event_id` (a simple counter) is the actual reliable ordering key, and `format_trace()`'s printed `@{}ms` is `timestamp_ms % 1000`, i.e. only the sub-second component, which is fine for relative ordering within a run but would look nonsensical read out of context (e.g. two events an hour apart could print similar `@Xms` values).
- **Gap:** `success_rate()` divides `solutions_found` by `total_transitions`, not by total *attempts* or *base cases reached* — this is a debatable metric name; "success rate" here really measures solutions per transition step, not a win/loss ratio over recursion branches.
- Two dead dependencies (C010, C031).
- 6 unit tests, including one that hand-constructs a `TraceStats` to test the rate formulas directly (good — decouples stat-math testing from trace-building).
