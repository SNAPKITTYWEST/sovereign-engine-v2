# spectrum_definition

`Spec(R)`: the set of prime ideals of the ring, represented here as a
`BTreeSet<u64>` of prime numbers (each standing in for its principal ideal).

## What it does

`Spectrum { primes: BTreeSet<u64> }`. `Spectrum::new(list)` filters the input
through `is_prime_ideal` (C062) so only genuine primes are retained.
Provides membership/insertion, conversion back to `Ideal`s
(`as_ideals`), a `specializes(p, q)` check (`p % q == 0 || p == q`, standing
in for `P ⊆ Q` inclusion), and `minimal_primes` / `maximal_primes` — the
primes with no other spectrum element dividing/dividing-into them
respectively.

## Public API

- `Spectrum::empty()`, `Spectrum::new(primes)`, `add_prime`, `len`,
  `is_empty`, `contains_prime`, `as_ideals`
- `specializes(p, q) -> bool`
- `minimal_primes() -> Vec<u64>`, `maximal_primes() -> Vec<u64>`

## Pipeline role

Depends on `ideal_interface` (C061) and `prime_ideal_predicate` (C062).
Feeds `spectrum_order` (C065, builds the specialization preorder from this
set), `spectrum_chains` (C066), and every downstream Krull-dimension crate —
this is the object whose "size" everything else measures.

## Non-obvious design decisions

- The spectrum is stored flat as prime *numbers*, not as `Ideal` structs,
  even though `as_ideals` can reconstruct them — a memory/simplicity
  tradeoff appropriate for Z but another spot that wouldn't generalize.
- `specializes` reuses plain divisibility as a proxy for ideal containment,
  consistent with `Ideal::contains`'s simplification in C061.
