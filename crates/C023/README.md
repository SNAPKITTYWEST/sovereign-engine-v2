# gap_candidate_set (C023)

Wraps a set of primes (`BTreeSet<u64>`) as `GapCandidateSet` and derives consecutive-prime gap statistics and gap-filtered candidate triples from it.

## Public API

- Re-exports `nth_prime`, `primes_up_to` from `prime_enumeration`.
- `GapCandidateSet::new(primes: Vec<u64>) -> Self` — dedupes/sorts primes into a `BTreeSet`, precomputes `min_gap` from consecutive differences.
- `GapCandidateSet::from_limit(limit: u64) -> Self` — convenience constructor via `primes_up_to`.
- `gaps() -> Vec<u64>` — all consecutive gap sizes, recomputed from the BTreeSet each call.
- `contains_gap(gap_size) -> bool`, `gap_count() -> usize` (distinct gap sizes), `min_gap()` (cached), `max_gap()` (recomputed each call), `len()`, `is_empty()`.
- `candidates_with_gap(self, min_size: u64) -> Vec<(u64, u64, u64)>` — **consumes `self`** (takes it by value), returns `(prime, next_prime, gap)` triples with `gap >= min_size`.

## Pipeline role

Depends on `prime_enumeration` (C022). This crate defines the `(u64, u64, u64)` "gap candidate tuple" convention — `(first_prime, second_prime, gap)` — that essentially every downstream Tier 2 crate (`gap_ordering`, `gap_multiplicity`, `gap_absolute_difference`, `gap_constraint_satisfaction`, `gap_verification`, `prime_gap_relationship`) consumes as its primary data shape, even though it's an untyped tuple rather than a named struct.

## Invariants / design notes

- `candidates_with_gap` takes `self` by value (not `&self`), so calling it consumes the `GapCandidateSet` — a caller who wants both the set and its filtered candidates must clone first (the struct does derive `Clone`).
- `min_gap` is computed once at construction and cached; `max_gap` and `gaps()` are recomputed from the `BTreeSet` on every call — an inconsistent caching strategy for what are structurally symmetric queries.
- The `(u64, u64, u64)` tuple convention shared across the whole Tier 2 family is implicit/positional (`prime, next_prime, gap`) rather than a named type — easy to get field order wrong when writing new consumers; no type alias exists to document the convention in code.

## Gaps / TODOs

- No validation that the input `Vec<u64>` to `new()` actually contains primes (or even that it's sorted before the BTreeSet reorders it) — the name promises primes but nothing enforces it.
- `gaps()` and `max_gap()` are O(n) recomputed on every call rather than cached like `min_gap`; a hot loop calling these repeatedly redoes the BTreeSet-to-Vec conversion each time.
