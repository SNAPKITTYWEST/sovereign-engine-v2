# `homological_lemmas_library` (C076)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Lemmas about chain complexes, homology and resolution certification
(Tier 4).  decides the finite lemmas
by running the Tier 4 code over every complex in an explicit family
(evidence grade `Computed`). Correctness of the Smith-normal-form homology
algorithm for *all* complexes is stated and left `Open`.

## Dependencies

- [C043 `differential_operator`](../C043/README.md)
- [C044 `differential_squared_zero`](../C044/README.md)
- [C047 `exactness_predicate`](../C047/README.md)
- [C048 `homology_computation`](../C048/README.md)
- [C049 `resolution_certification`](../C049/README.md)
- [C071 `type_checking_interface`](../C071/README.md)

## Re-exports

- `type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError}`

## Public API

| Item | Description |
|---|---|
| `enum HomologyLemmaStatus` | Status of a homology lemma |
| `struct HomologyLemma` | A homology or chain complex lemma |
| `fn HomologyLemma::new(name: String, statement: LeanType, lemma_type: String) -> Self` | Create a new open lemma |
| `fn HomologyLemma::with_note(mut self, note: impl Into<String>) -> Self` | Attach a note |
| `fn HomologyLemma::prove(&mut self, proof: ProofTerm) -> Result<(), TypeError>` | Close with a self-contained proof (checked in an empty context). |
| `fn HomologyLemma::is_proven(&self) -> bool` | Check if lemma is proven |
| `fn HomologyLemma::evidence(&self) -> Option<Evidence>` | Evidence grade, if proven |
| `struct HomologyLemmasLibrary` | Library of homology lemmas |
| `fn HomologyLemmasLibrary::new() -> Self` | Create an empty library |
| `fn HomologyLemmasLibrary::standard() -> Self` | The Tier 4 lemma set, with every finite lemma decided. |
| `fn HomologyLemmasLibrary::decide(&mut self, mut lemma: HomologyLemma, procedure: &str, check: impl FnOnce() -> Result<u64, String>)` | Register `lemma` and run its decision procedure. |
| `fn HomologyLemmasLibrary::prove_lemma(&mut self, name: &str, proof: ProofTerm) -> Result<(), TypeError>` | Close lemma `name` with `proof`, checked in this library's context. |
| `fn HomologyLemmasLibrary::add_lemma(&mut self, lemma: HomologyLemma)` | Add a lemma |
| `fn HomologyLemmasLibrary::get_lemma(&self, name: &str) -> Option<&HomologyLemma>` | Get a lemma by name |
| `fn HomologyLemmasLibrary::get_lemma_mut(&mut self, name: &str) -> Option<&mut HomologyLemma>` | Get mutable lemma |
| `fn HomologyLemmasLibrary::count_proven(&self) -> usize` | Count proven lemmas |
| `fn HomologyLemmasLibrary::count_open(&self) -> usize` | Count open lemmas |
| `fn HomologyLemmasLibrary::count_failed(&self) -> usize` | Count refuted lemmas |
| `fn HomologyLemmasLibrary::lemmas_by_type(&self, lemma_type: &str) -> Vec<&HomologyLemma>` | Lemmas of a kind |
| `fn HomologyLemmasLibrary::exactness_lemmas(&self) -> Vec<&HomologyLemma>` | Exactness lemmas |
| `fn HomologyLemmasLibrary::differential_lemmas(&self) -> Vec<&HomologyLemma>` | Differential lemmas |

## Tests

`cargo test -p homological_lemmas_library` runs 2 unit tests.
