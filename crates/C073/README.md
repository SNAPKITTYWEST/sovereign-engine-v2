# `gap_lemmas_library` (C073)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Lemmas about primes and prime gaps that the Tier 2 engine relies on.

 registers each lemma with a precise
statement. Lemmas over a finite domain are *decided*: a decision procedure
runs the real Tier 2 code over every case and the lemma is closed with a
 (evidence grade `Computed`), or marked `Failed`
with the counterexample. Unbounded statements stay `Open` — they need a
Lean proof, which this crate does not claim.

## Dependencies

- [C021 `prime_predicate`](../C021/README.md)
- [C022 `prime_enumeration`](../C022/README.md)
- [C023 `gap_candidate_set`](../C023/README.md)
- [C028 `gap_verification`](../C028/README.md)
- [C029 `prime_gap_relationship`](../C029/README.md)
- [C071 `type_checking_interface`](../C071/README.md)

## Re-exports

- `type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError}`

## Public API

| Item | Description |
|---|---|
| `const DECIDED_LIMIT: u64 = 10_000` | Upper bound of the decided prime lemmas. |
| `enum LemmaStatus` | Status of a lemma proof |
| `struct GapLemma` | A gap lemma statement and its proof |
| `fn GapLemma::new(name: String, statement: LeanType) -> Self` | Create a new open lemma |
| `fn GapLemma::with_gap_size(mut self, size: usize) -> Self` | Set the gap size this lemma applies to |
| `fn GapLemma::with_note(mut self, note: impl Into<String>) -> Self` | Attach a note |
| `fn GapLemma::prove(&mut self, proof: ProofTerm) -> Result<(), TypeError>` | Close with a self-contained proof (checked in an empty context). |
| `fn GapLemma::is_proven(&self) -> bool` | Check if lemma is proven |
| `fn GapLemma::evidence(&self) -> Option<Evidence>` | Evidence grade, if proven |
| `struct GapLemmasLibrary` | Library of gap lemmas |
| `fn GapLemmasLibrary::new() -> Self` | Create an empty library |
| `fn GapLemmasLibrary::standard() -> Self` | The Tier 2 lemma set, with every finite lemma decided. |
| `fn GapLemmasLibrary::decide(&mut self, mut lemma: GapLemma, procedure: &str, check: impl FnOnce() -> Result<u64, String>)` | Register `lemma` and run its decision procedure: closed with a certificate on success, marked failed with the counterexample otherwise. |
| `fn GapLemmasLibrary::prove_lemma(&mut self, name: &str, proof: ProofTerm) -> Result<(), TypeError>` | Close lemma `name` with `proof`, checked in this library's context. |
| `fn GapLemmasLibrary::add_lemma(&mut self, lemma: GapLemma)` | Add a lemma to the library |
| `fn GapLemmasLibrary::get_lemma(&self, name: &str) -> Option<&GapLemma>` | Get a lemma by name |
| `fn GapLemmasLibrary::get_lemma_mut(&mut self, name: &str) -> Option<&mut GapLemma>` | Get mutable lemma |
| `fn GapLemmasLibrary::count_proven(&self) -> usize` | Count proven lemmas |
| `fn GapLemmasLibrary::count_open(&self) -> usize` | Count open lemmas |
| `fn GapLemmasLibrary::count_failed(&self) -> usize` | Count refuted lemmas |
| `fn GapLemmasLibrary::lemmas_for_gap(&self, size: usize) -> Vec<&GapLemma>` | Get all lemmas for a specific gap size |

## Tests

`cargo test -p gap_lemmas_library` runs 4 unit tests.
