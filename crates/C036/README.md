# recursion_base_case (C036)

## What it does
Detects when the recursive solver should stop: all constraints satisfied, terminal prime reached, max depth hit, sequence exhausted, target pattern matched, or no valid moves left. Also tracks base-case frequency statistics.

## Public API
- `BaseCase` enum: `AllConstraintsSatisfied`, `TerminalPrimeReached(u64)`, `MaxDepthReached`, `NoValidMoves`, `SequenceExhausted`, `PatternMatched(u64)`.
- `BaseCaseValidator::new(limit)` — builds internal `prime_gap_pairs(limit)` table; builder methods `with_terminal_prime()`, `with_target_gap()`.
- Individual checks (several are `Self::` associated fns, not requiring `&self`): `check_all_constraints_satisfied`, `check_terminal_prime_reached`, `check_max_depth_reached`, `check_no_valid_moves`, `check_sequence_exhausted`, `check_pattern_matched`.
- `is_base_case(state, cursor_pos, total_gaps, max_depth, current_gap) -> Option<BaseCase>` — runs all checks in a fixed priority order and returns the first match.
- `gap_pairs()` accessor.
- `BaseCaseStats` — records occurrences by name, tracks `most_common`.

## Pipeline position
Depends on `prime_gap_relationship` (C029) for `prime_gap_pairs`/`PrimeGapPair`, `prime_enumeration` (C022, declared, unused) and `gap_candidate_set` (C023, declared, unused), and `recursive_solver_state` (C031). Consumed conceptually by the solver's main loop (not itself a dependency of other crates in this range) to decide when to stop recursing.

## Notes / gaps
- **Gap:** `check_no_valid_moves` is a stub in spirit — its doc comment says "would need cursor info; for now, check if state is contradictory," i.e. it conflates "no valid moves" with "is_contradictory," which are semantically different conditions. This is an explicit, self-documented shortcut.
- `is_base_case`'s priority order (constraints-satisfied checked before terminal-prime, before max-depth, etc.) is a meaningful design decision with no comment justifying the ordering — worth understanding before reordering.
- `prime_enumeration` and `gap_candidate_set` are unused declared dependencies.
- 6 unit tests.
