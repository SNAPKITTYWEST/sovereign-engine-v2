# `krull_lemmas_library` (C078)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Lemmas about Krull dimension of Spec(Z) and its subspaces (Tier 6).
 decides the finite lemmas by computing
dimensions, chains and certificates for every spectrum in a family
(evidence grade `Computed`). `dim Z = 1` for the whole (infinite)
spectrum is stated and left `Open`.

## Dependencies

- [C064 `spectrum_definition`](../C064/README.md)
- [C067 `krull_dimension_definition`](../C067/README.md)
- [C068 `dimension_upper_bounds`](../C068/README.md)
- [C069 `krull_certification`](../C069/README.md)
- [C071 `type_checking_interface`](../C071/README.md)

## Re-exports

- `type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError}`

## Public API

| Item | Description |
|---|---|
| `const DECIDED_BOUND: u64 = 200` | Largest prime bound covered by the decided lemmas. |
| `enum KrullLemmaStatus` | Status of a Krull dimension lemma |
| `struct KrullLemma` | A Krull dimension lemma |
| `fn KrullLemma::new(name: String, statement: LeanType) -> Self` | Create a new open lemma |
| `fn KrullLemma::with_dimension_bound(mut self, bound: usize) -> Self` | Set the dimension asserted |
| `fn KrullLemma::with_note(mut self, note: impl Into<String>) -> Self` | Attach a note |
| `fn KrullLemma::prove(&mut self, proof: ProofTerm) -> Result<(), TypeError>` | Close with a self-contained proof (checked in an empty context). |
| `fn KrullLemma::is_proven(&self) -> bool` | Check if lemma is proven |
| `fn KrullLemma::evidence(&self) -> Option<Evidence>` | Evidence grade, if proven |
| `struct KrullLemmasLibrary` | Library of Krull dimension lemmas |
| `fn KrullLemmasLibrary::new() -> Self` | Create an empty library |
| `fn KrullLemmasLibrary::standard() -> Self` | The Tier 6 lemma set, with every finite lemma decided. |
| `fn KrullLemmasLibrary::decide(&mut self, mut lemma: KrullLemma, procedure: &str, check: impl FnOnce() -> Result<u64, String>)` | Register `lemma` and run its decision procedure. |
| `fn KrullLemmasLibrary::prove_lemma(&mut self, name: &str, proof: ProofTerm) -> Result<(), TypeError>` | Close lemma `name` with `proof`, checked in this library's context. |
| `fn KrullLemmasLibrary::add_lemma(&mut self, lemma: KrullLemma)` | Add a lemma |
| `fn KrullLemmasLibrary::get_lemma(&self, name: &str) -> Option<&KrullLemma>` | Get a lemma by name |
| `fn KrullLemmasLibrary::get_lemma_mut(&mut self, name: &str) -> Option<&mut KrullLemma>` | Get mutable lemma |
| `fn KrullLemmasLibrary::count_proven(&self) -> usize` | Count proven lemmas |
| `fn KrullLemmasLibrary::count_open(&self) -> usize` | Count open lemmas |
| `fn KrullLemmasLibrary::count_failed(&self) -> usize` | Count refuted lemmas |
| `fn KrullLemmasLibrary::lemmas_for_dimension(&self, dim: usize) -> Vec<&KrullLemma>` | Lemmas asserting a given dimension |
| `fn KrullLemmasLibrary::min_dimension(&self) -> Option<usize>` | Smallest dimension asserted |
| `fn KrullLemmasLibrary::max_dimension(&self) -> Option<usize>` | Largest dimension asserted |

## Tests

`cargo test -p krull_lemmas_library` runs 2 unit tests.
