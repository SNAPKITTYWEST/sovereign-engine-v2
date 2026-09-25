# prime_gap_relationship (C029)

Ties primes to their gaps as a first-class `PrimeGapPair` type (rather than the anonymous tuple convention used elsewhere in Tier 2) and adds a "normalized gap" metric based on the prime-number-theorem-style expectation that gaps grow like `ln(p)`.

## Public API

- Re-exports `is_prime` (from `prime_predicate`), `primes_up_to`/`nth_prime` (from `prime_enumeration`), `GapCandidateSet` (from `gap_candidate_set`).
- `PrimeGapPair { prime, next_prime, gap }` (`Clone, Debug`).
  - `is_first_occurrence(&self, all_gaps: &[u64]) -> bool` — true if `self.gap` doesn't appear earlier in `all_gaps` than... itself (see design notes — this logic is subtle/likely buggy).
  - `normalized_gap(&self) -> f64` — `gap / ln(prime)`.
- `prime_gap_pairs(limit: u64) -> Vec<PrimeGapPair>` — the `(u64,u64,u64)`-tuple convention re-expressed as this named struct.
- `primes_with_gap(pairs, gap_size) -> Vec<u64>`.
- `largest_gap_in_range(pairs, start, end) -> Option<PrimeGapPair>`.
- `maximal_gaps(pairs) -> Vec<PrimeGapPair>` — first occurrence of each distinct gap size, in input order.
- `gap_ratios(pairs) -> Vec<f64>` — same computation as `normalized_gap`, but as a free function over a slice.

## Pipeline role

Depends on `prime_predicate`, `prime_enumeration`, `gap_candidate_set` (C021, C022, C023). Re-exported wholesale by `prime_gap_tests_integration` (C030), which is the last crate in the Tier 2 chain.

## Invariants / design notes

- **`normalized_gap` and `gap_ratios` duplicate the same formula** (`gap / ln(prime)`) in two places — one as a method, one as a free function over a slice. Any future change to the normalization formula (e.g. switching to `ln(ln(prime))` corrections per the actual prime gap conjectures) needs to be made in both places or they'll silently diverge.
- `maximal_gaps` is a "first occurrence per gap size" filter (like `distinct-by`), not actually "the maximal (largest) gaps" as the name might suggest to a newcomer — it doesn't select for large gap values at all, just uniqueness in appearance order. This naming is a likely source of confusion versus `gap_ordering::top_k_gaps`, which *does* select by size.
- `PrimeGapPair::is_first_occurrence`'s implementation (`all_gaps.iter().take_while(|&&g| g != self.gap).all(|&g| g != self.gap)`) is logically equivalent to just `!all_gaps.contains(&self.gap)` combined with taking only the prefix before the first match — but since `take_while` stops at the first match and then checks the remaining prefix (which by construction contains no matches), this **always evaluates true** unless the slice is somehow inconsistent; it does not actually check "is *this* occurrence the first one" positionally, it only checks whether `self.gap` appears anywhere at all in a way that's tautologically satisfied for the sliced prefix. This method is untested (no test exists for it) and its logic should be re-derived.

## Gaps / TODOs

- `is_first_occurrence` has no test coverage and its logic (see above) looks like dead/tautological code rather than a genuine positional check — this needs a fix or at minimum a design review before anyone relies on it.
- Formula duplication between `normalized_gap` and `gap_ratios` (see above) — candidate for consolidation.
- The `maximal_gaps` naming mismatch (uniqueness filter, not size-maximal) is worth a rename or a doc clarification.
