# `spectrum_chains` (C066)

Tier 6 — Krull dimension. *Generated from the crate source; regenerate after API changes.*

Prime chains in a spectrum: totally ordered sequences of prime ideals.
Used to compute Krull dimension as length of longest chains.

## Dependencies

- [C064 `spectrum_definition`](../C064/README.md)
- [C065 `spectrum_order`](../C065/README.md)

## Public API

| Item | Description |
|---|---|
| `struct PrimeChain` | A chain in the spectrum: totally ordered sequence of primes |
| `fn PrimeChain::singleton(p: u64) -> Self` | Create a single-element chain |
| `fn PrimeChain::empty() -> Self` | Create empty chain |
| `fn PrimeChain::len(&self) -> usize` | Length of the chain |
| `fn PrimeChain::is_empty(&self) -> bool` | Check if chain is empty |
| `fn PrimeChain::elements(&self) -> &[u64]` | Get elements in chain |
| `fn PrimeChain::is_valid(&self, preorder: &SpecializationPreorder) -> bool` | Check if chain is valid (totally ordered) |
| `fn PrimeChain::extend(&self, p: u64, preorder: &SpecializationPreorder) -> Option<Self>` | Try to extend the chain with `p`. |
| `struct MaximalChains` | Maximal chains in a spectrum |
| `fn MaximalChains::find_all(spec: &Spectrum, preorder: &SpecializationPreorder) -> Self` | Find all maximal chains in spectrum |
| `fn MaximalChains::longest_length(&self) -> usize` | Length of longest chain |
| `fn MaximalChains::chains(&self) -> &[PrimeChain]` | Get all maximal chains |
| `fn MaximalChains::chains_of_length(&self, len: usize) -> Vec<&PrimeChain>` | Filter chains of given length |

## Tests

`cargo test -p spectrum_chains` runs 5 unit tests.
