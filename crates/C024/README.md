# gap_ordering (C024)

Sorting, top-k, range-filtering, and histogramming operations over `(prime, next_prime, gap)` candidate tuples.

## Public API

- Re-exports `GapCandidateSet` from `gap_candidate_set`.
- `GapOrdering` enum — `SizeAscending`, `SizeDescending`, `PrimeAscending`, `PrimeDescending`.
- `order_gaps(candidates, ordering) -> Vec<(u64,u64,u64)>` — sorts by the chosen key.
- `top_k_gaps(candidates, k) -> Vec<(u64,u64,u64)>` — sorts descending by gap size and truncates (always re-sorts internally regardless of any prior ordering).
- `gaps_in_range(candidates, min, max) -> Vec<(u64,u64,u64)>` — inclusive-range filter on gap size.
- `gap_histogram(candidates: &[...]) -> BTreeMap<u64, usize>` — count of occurrences per gap size.

## Pipeline role

Depends on `gap_candidate_set` (C023). Consumed by `gap_multiplicity` (C025, re-exports `order_gaps`/`GapOrdering`), `gap_absolute_difference` (C026, re-exports `order_gaps`), and `prime_gap_tests_integration` (C030) for the Tier 2 integration test.

## Invariants / design notes

- All four functions operate on plain `Vec<(u64,u64,u64)>`/slices rather than on `GapCandidateSet` directly — this crate treats the tuple convention from C023 as the real interchange type, using `GapCandidateSet` only as a re-export convenience, not as an actual parameter type anywhere in this crate's own functions.
- `top_k_gaps` ignores the caller's chosen `GapOrdering` entirely and always sorts by descending gap size internally — it does not compose with `order_gaps`; if a caller wanted "top k by prime value" there is no way to express that with this function.
- `GapOrdering` derives `PartialEq, Eq` but the enum is otherwise only consumed by `order_gaps`'s match — no `Ord`/comparison between variants is defined or needed.

## Gaps / TODOs

- No test covers `PrimeAscending`/`PrimeDescending` variants of `order_gaps` — only `SizeAscending` is exercised in this crate's tests.
- `top_k_gaps`'s disconnect from the `GapOrdering` type (see above) is a minor API inconsistency a newcomer could easily trip over, expecting it to respect a passed-in ordering.
