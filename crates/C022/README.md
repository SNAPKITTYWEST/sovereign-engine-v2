# prime_enumeration (C022)

Sieve-based generation of prime sequences: all primes up to a limit, the n-th prime, and a prime-counting function.

## Public API

- Re-exports `is_prime`, `is_prime_candidate` from `prime_predicate`.
- `primes_up_to(limit: u64) -> Vec<u64>` — Sieve of Eratosthenes, O(n log log n).
- `nth_prime(n: usize) -> Option<u64>` — estimates an upper bound via the Prime Number Theorem (`n·(ln n + ln ln n)` for n < 1000, `n·ln n·1.3` beyond), sieves up to that estimate, then indexes into the result.
- `prime_count(limit: u64) -> usize` — π(n), implemented by materializing the whole sieve and taking its length (not a specialized counting sieve).

## Pipeline role

Depends on `prime_predicate` (C021). Feeds `gap_candidate_set` (C023), which calls `primes_up_to`/`nth_prime` to build candidate sets for gap analysis, and is re-exported further down the chain through `prime_gap_relationship` (C029) and `prime_gap_tests_integration` (C030).

## Invariants / design notes

- The sieve allocates a `Vec<bool>` of size `limit + 1` — memory scales linearly with `limit`, not with the prime count, so very large limits are memory-bound before they're compute-bound.
- `nth_prime`'s upper-bound estimate is a heuristic PNT-based bound, not a proven upper bound for all n; for adversarial or very large `n` it could theoretically underestimate and return `None` where a true nth prime exists (the `.get(n)` on the sieved vector would come back empty). No fallback/retry-with-larger-estimate logic exists.
- `prime_count` is O(limit) and re-sieves from scratch rather than reusing a cached sieve — fine for the test-scale limits (≤100) exercised here, but a hot path if called repeatedly on large limits.

## Gaps / TODOs

- No test exercises `nth_prime`'s underestimation edge case (very large `n`) or `prime_count`/`primes_up_to` at large scale — only small-limit correctness is verified.
- No caching/memoization between repeated calls; every call resieves from 0.
