# `memory_lemmas_library` (C074)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Lemmas about the multiplicity arena (Tier 1): layout partitioning, Nil
initialization, bump allocation, reset and rollback, and sealing.

 decides every lemma over a finite
family of configurations by running the Tier 1 code (evidence grade
`Computed`). Soundness of the `unsafe` blocks themselves is stated but left
`Open`: it needs a separation-logic proof, not testing.

## Dependencies

- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C012 `multiplicity_arena_layout`](../C012/README.md)
- [C013 `multiplicity_arena_allocation`](../C013/README.md)
- [C071 `type_checking_interface`](../C071/README.md)

## Re-exports

- `type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError}`

## Public API

| Item | Description |
|---|---|
| `enum MemoryLemmaStatus` | Status of a memory lemma |
| `struct MemoryLemma` | A memory safety lemma |
| `fn MemoryLemma::new(name: String, statement: LeanType, category: String) -> Self` | Create a new open lemma |
| `fn MemoryLemma::with_note(mut self, note: impl Into<String>) -> Self` | Attach a note |
| `fn MemoryLemma::prove(&mut self, proof: ProofTerm) -> Result<(), TypeError>` | Close with a self-contained proof (checked in an empty context). |
| `fn MemoryLemma::is_proven(&self) -> bool` | Check if lemma is proven |
| `fn MemoryLemma::evidence(&self) -> Option<Evidence>` | Evidence grade, if proven |
| `struct MemoryLemmasLibrary` | Library of memory lemmas |
| `fn MemoryLemmasLibrary::new() -> Self` | Create an empty library |
| `fn MemoryLemmasLibrary::standard() -> Self` | The Tier 1 lemma set, with every finite lemma decided. |
| `fn MemoryLemmasLibrary::decide(&mut self, mut lemma: MemoryLemma, procedure: &str, check: impl FnOnce() -> Result<u64, String>)` | Register `lemma` and run its decision procedure. |
| `fn MemoryLemmasLibrary::prove_lemma(&mut self, name: &str, proof: ProofTerm) -> Result<(), TypeError>` | Close lemma `name` with `proof`, checked in this library's context. |
| `fn MemoryLemmasLibrary::add_lemma(&mut self, lemma: MemoryLemma)` | Add a lemma |
| `fn MemoryLemmasLibrary::get_lemma(&self, name: &str) -> Option<&MemoryLemma>` | Get a lemma by name |
| `fn MemoryLemmasLibrary::get_lemma_mut(&mut self, name: &str) -> Option<&mut MemoryLemma>` | Get mutable lemma |
| `fn MemoryLemmasLibrary::count_proven(&self) -> usize` | Count proven lemmas |
| `fn MemoryLemmasLibrary::count_open(&self) -> usize` | Count open lemmas |
| `fn MemoryLemmasLibrary::count_failed(&self) -> usize` | Count refuted lemmas |
| `fn MemoryLemmasLibrary::lemmas_by_category(&self, category: &str) -> Vec<&MemoryLemma>` | Lemmas in a category |
| `fn MemoryLemmasLibrary::allocation_lemmas(&self) -> Vec<&MemoryLemma>` | Allocation lemmas |
| `fn MemoryLemmasLibrary::deallocation_lemmas(&self) -> Vec<&MemoryLemma>` | Deallocation lemmas |

## Tests

`cargo test -p memory_lemmas_library` runs 3 unit tests.
