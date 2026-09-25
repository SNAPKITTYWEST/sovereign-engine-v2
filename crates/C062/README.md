# prime_ideal_predicate

Primality test for `Ideal` (C061), under the integer-divisibility model.

## What it does

`is_prime_ideal(&Ideal) -> bool`: the zero ideal is prime; a principal ideal
`(p)` is prime iff `p` is a prime number (trial division up to `sqrt(p)`);
a multi-generator ideal is treated as prime iff `gcd(generators)` is prime.
Also provides `is_weakly_prime` (gcd is 1 or prime) and `to_prime_point`,
which wraps a prime `Ideal` into a `PrimePoint { ideal, height: 1 }` — note
`height` is hardcoded to 1, not actually computed.

## Public API

- `is_prime_ideal(&Ideal) -> bool`
- `is_weakly_prime(&Ideal) -> bool`
- `to_prime_point(&Ideal) -> Option<PrimePoint>`
- `PrimePoint { ideal, height }` with `contains(&other) -> bool`

## Pipeline role

Depends on `ideal_interface` (C061). Consumed by `maximal_ideal_predicate`
(C063), `spectrum_definition` (C064, filters candidate primes when building
`Spec(R)`), and the Lean-side `krull_lemmas_library` (C078) as the informal
counterpart to a Lean primality lemma.

## Non-obvious design decisions / gaps

- `gcd` reduction for multi-generator ideals as a primality check is an
  approximation: `(6, 10)` has gcd 2 (prime), but the ideal `(6,10) = (2)` in
  Z, so this happens to be correct here, though only because Z is a PID —
  the shortcut would not generalize.
- `PrimePoint.height` is always `1` regardless of actual chain length; real
  height computation lives downstream in `spectrum_chains` (C066) /
  `krull_dimension_definition` (C067). A reader should not treat this field
  as meaningful outside trivial cases.
