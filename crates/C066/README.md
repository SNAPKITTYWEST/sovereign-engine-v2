# spectrum_chains

Totally-ordered chains of primes in a spectrum, and enumeration of maximal
chains — the direct input to Krull dimension.

## What it does

`PrimeChain` wraps a `Vec<u64>` representing a chain `P0 ⊆ P1 ⊆ ...` under
the specialization preorder; `is_valid` checks every pair is comparable via
`preorder.le`, and `extend(p, preorder)` appends `p` only if it's `≥` the
chain's current last element. `MaximalChains::find_all` does a
breadth-ish search (worklist of partial chains) from every prime in the
spectrum, building all extendable chains, then keeps only those not
strictly subsumed by another (`is_subchain`, an order-preserving subsequence
check), giving the maximal chains. `longest_length()` and
`chains_of_length(n)` expose the results.

## Public API

- `PrimeChain::singleton`, `empty`, `len`, `is_empty`, `elements`,
  `is_valid`, `extend` — plus `Ord`/`PartialOrd` by lexicographic `Vec` order
- `MaximalChains::find_all(&Spectrum, &SpecializationPreorder)`,
  `longest_length`, `chains()`, `chains_of_length(len)`

## Pipeline role

Depends on `spectrum_definition` (C064) and `spectrum_order` (C065). This is
the crate `krull_dimension_definition` (C067) calls directly to compute
`dim(R) = longest_chain_length - 1`.

## Non-obvious design decisions / gaps

- `find_all`'s de-duplication/subsumption pruning
  (`maximal.retain(...); maximal.push(chain)`) is an O(chains^2) pass run
  once per starting prime — a naive but workable approach for small
  spectra; there is no bound on chain-search blowup for larger inputs.
- `is_subchain` checks for an order-preserving embedding of one chain's
  elements into another, not a literal Vec prefix — this is what lets
  `find_all` discard chains subsumed by longer ones built from a different
  starting point.
- No test actually asserts a *specific* dimension value from a nontrivial
  spectrum (e.g. that `{2,4,6}` yields a chain of length 2); tests only
  check chains are non-empty or extend successfully.
