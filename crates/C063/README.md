# maximal_ideal_predicate

Maximality test for `Ideal`, plus a containment-comparison utility used to
order ideals.

## What it does

`is_maximal_ideal(&Ideal) -> bool`: false for the zero ideal; for a principal
ideal `(p)`, maximal iff `p` is prime; for multi-generator ideals, maximal
iff `gcd(generators)` is prime and `> 1`. Also defines `IdealComparison`
(StrictlyGreater/StrictlyLess/Equal/Incomparable) via `compare_ideals`, built
from `Ideal::contains_ideal` in both directions, and `is_strictly_between`
for testing whether one ideal sits strictly inside a chain of two others.

## Public API

- `is_maximal_ideal(&Ideal) -> bool`
- `IdealComparison` enum, `compare_ideals(left, right) -> IdealComparison`
- `is_strictly_between(lower, candidate, upper) -> bool`
- Re-exports `Ideal`, `is_prime_ideal`, `PrimePoint` from upstream crates

## Pipeline role

Depends on `ideal_interface` (C061) and `prime_ideal_predicate` (C062).
`compare_ideals` is the containment-order primitive that `spectrum_order`
(C065) generalizes into the specialization preorder over an entire spectrum.

## Gaps / weak spots

- In Z (a PID with dimension 1), maximal ideals coincide with nonzero prime
  ideals, so `is_maximal_ideal` largely duplicates `is_prime_ideal` plus a
  nonzero check — expected for this toy model, but would need real height
  computation for a general ring.
- Two tests (`test_compare_ideals_contained`, `test_is_strictly_between`)
  assert `cond || !cond`, which is a tautology and passes regardless of the
  actual comparison result — these do not verify correctness of
  `compare_ideals` on that input, only that it doesn't panic.
