# ideal_interface

Basic representation of an ideal in a commutative ring, restricted to ideals of
the integers (`u64` generators). Foundation for the Krull-dimension layer
(C061-C070).

## What it does

Provides `Ideal { generators: BTreeSet<u64>, is_zero: bool }` with
constructors and set-style operations. `Ideal::new` normalizes a generator
list by dropping zero, sorting, deduping, and then discarding any generator
that is a multiple of another generator already in the set — i.e. it reduces
to a minimal generating set under divisibility.

## Public API

- `Ideal::zero()`, `Ideal::principal(a)`, `Ideal::new(generators)`
- `num_generators`, `contains(x)`, `contains_ideal(other)`
- `gcd()` — gcd of all generators (1 for the zero ideal, by convention)
- `intersection(other)`, `sum(other)`

## Pipeline role

Depends only on `gap_tensor_core` (C001) for workspace wiring (not otherwise
used). Everything else in the Krull layer builds on this: `prime_ideal_predicate`
(C062) and `maximal_ideal_predicate` (C063) test primality/maximality of an
`Ideal`; `spectrum_definition` (C064) collects `Ideal`s into `Spec(R)`.

## Non-obvious design decisions

- This models ideals of **Z** only, via divisibility of `u64` generators —
  not a general commutative ring. `contains(x)` checks `x % g == 0` for some
  generator `g`, which is correct for principal ideals of Z but is a
  simplification, not a general ideal-membership test (no Groebner basis /
  module-theoretic machinery).
- `contains_ideal` and `intersection`/`sum` inherit this simplification, so
  the "commutative algebra" here is really "divisibility arithmetic on
  natural numbers" dressed in ring-theory vocabulary. Anyone extending this
  to non-principal rings needs to replace the representation, not just add
  methods.
