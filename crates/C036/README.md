# `recursion_base_case` (C036)

Tier 3 — recursive solver. *Generated from the crate source; regenerate after API changes.*

Base case detection for recursive solver. Determines when recursion should
terminate, identifies terminal states, and validates completion conditions.

## Dependencies

- [C022 `prime_enumeration`](../C022/README.md)
- [C023 `gap_candidate_set`](../C023/README.md)
- [C029 `prime_gap_relationship`](../C029/README.md)
- [C031 `recursive_solver_state`](../C031/README.md)

## Public API

| Item | Description |
|---|---|
| `fn constraint_admits(constraint: &GapConstraint, pair: &PrimeGapPair) -> bool` | Does the consecutive prime pair satisfy the constraint? |
| `enum BaseCase` | Criteria for detecting a base case. |
| `struct BaseCaseValidator` | Validator for base case conditions. |
| `fn BaseCaseValidator::new(limit: u64) -> Self` | Create a new base case validator. |
| `fn BaseCaseValidator::with_terminal_prime(mut self, prime: u64) -> Self` | Set the terminal prime to look for. |
| `fn BaseCaseValidator::with_target_gap(mut self, gap: u64) -> Self` | Set the target gap pattern. |
| `fn BaseCaseValidator::check_all_constraints_satisfied(state: &RecursiveSolverState) -> bool` | Check if all constraints are satisfied. |
| `fn BaseCaseValidator::check_terminal_prime_reached(&self, state: &RecursiveSolverState) -> bool` | Check if terminal prime has been reached. |
| `fn BaseCaseValidator::check_max_depth_reached(state: &RecursiveSolverState, max_depth: u32) -> bool` | Check if max depth is exceeded. |
| `fn BaseCaseValidator::check_no_valid_moves(&self, state: &RecursiveSolverState, cursor_pos: usize) -> bool` | No valid move remains from `cursor_pos`: the state is contradictory, or no remaining prime pair satisfies any unsatisfied constraint (with no unsatisfied constraints, any remaining pair is a valid move). |
| `fn BaseCaseValidator::check_sequence_exhausted(cursor_pos: usize, total_gaps: usize) -> bool` | Check if sequence is exhausted. |
| `fn BaseCaseValidator::check_pattern_matched(&self, gap: u64) -> bool` | Check if target gap pattern is matched. |
| `fn BaseCaseValidator::is_base_case(&self, state: &RecursiveSolverState, cursor_pos: usize, total_gaps: usize, max_depth: u32, current_gap: u64) -> Option<BaseCase>` | Comprehensive base case check. |
| `fn BaseCaseValidator::gap_pairs(&self) -> &[PrimeGapPair]` | Get the gap pairs. |
| `struct BaseCaseStats` | Statistics about base case conditions. |
| `fn BaseCaseStats::new() -> Self` | Create empty stats. |
| `fn BaseCaseStats::record(&mut self, case: &BaseCase)` | Record a base case occurrence. |
| `fn BaseCaseStats::stats(&self) -> (&std::collections::BTreeMap<String, usize>, usize)` | Get statistics. |

## Tests

`cargo test -p recursion_base_case` runs 9 unit tests.
