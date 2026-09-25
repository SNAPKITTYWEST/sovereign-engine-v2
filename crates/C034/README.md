# recursive_solver_selection (C034)

## What it does
Chooses the next gap to process out of the unvisited candidates in a `RecursiveSolverCursor`, using one of five scoring strategies (`SmallestFirst`, `LargestFirst`, `MostCommon`, `LeastRecent`, `Hybrid`).

## Public API
- `SelectionStrategy` enum (5 variants, see above).
- `GapSelectionScore { index, gap, score, components }`.
- `RecursiveSolverSelector::new(cursor, strategy)`, `set_strategy()`, `strategy()`.
- `score_candidates() -> Vec<GapSelectionScore>` — scores all unvisited positions.
- `select_next() -> Option<(usize, gap)>` — picks the max-scoring candidate, appends to history.
- `select_top_k(k)` — sorted top-k without mutating history.
- `select_by_constraint(required_gap)` — first unvisited gap matching an exact gap size (bypasses scoring).
- `history()`, `clear_history()`, `cursor()`, `cursor_mut()`.

## Pipeline position
Declares dependencies on `gap_candidate_set` (C023), `gap_ordering` (C024), `gap_multiplicity` (C025), `gap_absolute_difference` (C026) but only actually imports `recursive_solver_cursor` (C033) — the four gap-analytics crates are unused in `lib.rs`. `MostCommon`/`Hybrid` scoring reimplements a frequency count locally (`cursor.all_gaps().iter().filter(...)`) rather than calling into `gap_multiplicity`, which is presumably what that crate is for.

## Notes / gaps
- **Novelty:** `Hybrid` strategy is a hand-tuned weighted sum (size weight 2.0, frequency weight 1.0, recency weight 0.5) — worth flagging since the weights are magic numbers with no comment explaining the tuning rationale.
- **Gap:** four declared dependencies (C023, C024, C025, C026) are unused — likely intended to back the scoring functions but never wired in; the crate reimplements frequency counting by hand instead. Candidates for either removal or actual integration.
- `select_next` uses `partial_cmp(...).unwrap_or(Equal)` — silently treats NaN scores as equal rather than erroring, could mask a scoring bug.
- 6 unit tests covering strategy switching and selection behavior.
