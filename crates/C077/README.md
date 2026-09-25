# `tor_resolution_lemmas_library` (C077)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Lemmas about Tor over Z (Tier 5).  decides
the finite lemmas by computing Tor for every pair of cyclic groups in a
range and comparing against the known answer
`Tor_0(Z/m, Z/n) = Tor_1(Z/m, Z/n) = Z/gcd(m, n)` (evidence grade
`Computed`). Independence of Tor from the chosen resolutions is stated
and left `Open`.

## Dependencies

- [C051 `tor_functor_definition`](../C051/README.md)
- [C054 `derived_homology`](../C054/README.md)
- [C055 `tor_zero_structure`](../C055/README.md)
- [C056 `tor_higher_degrees`](../C056/README.md)
- [C057 `functoriality_of_tor`](../C057/README.md)
- [C071 `type_checking_interface`](../C071/README.md)

## Re-exports

- `type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError}`

## Public API

| Item | Description |
|---|---|
| `const DECIDED_ORDER: i64 = 24` | Largest cyclic order covered by the decided lemmas. |
| `enum TorLemmaStatus` | Status of a Tor lemma |
| `struct TorLemma` | A Tor functor or resolution lemma |
| `fn TorLemma::new(name: String, statement: LeanType) -> Self` | Create a new open lemma |
| `fn TorLemma::with_tor_degree(mut self, degree: usize) -> Self` | Set the Tor degree |
| `fn TorLemma::with_note(mut self, note: impl Into<String>) -> Self` | Attach a note |
| `fn TorLemma::prove(&mut self, proof: ProofTerm) -> Result<(), TypeError>` | Close with a self-contained proof (checked in an empty context). |
| `fn TorLemma::is_proven(&self) -> bool` | Check if lemma is proven |
| `fn TorLemma::evidence(&self) -> Option<Evidence>` | Evidence grade, if proven |
| `struct TorLemmasLibrary` | Library of Tor lemmas |
| `fn TorLemmasLibrary::new() -> Self` | Create an empty library |
| `fn TorLemmasLibrary::standard() -> Self` | The Tier 5 lemma set, with every finite lemma decided. |
| `fn TorLemmasLibrary::decide(&mut self, mut lemma: TorLemma, procedure: &str, check: impl FnOnce() -> Result<u64, String>)` | Register `lemma` and run its decision procedure. |
| `fn TorLemmasLibrary::prove_lemma(&mut self, name: &str, proof: ProofTerm) -> Result<(), TypeError>` | Close lemma `name` with `proof`, checked in this library's context. |
| `fn TorLemmasLibrary::add_lemma(&mut self, lemma: TorLemma)` | Add a lemma |
| `fn TorLemmasLibrary::get_lemma(&self, name: &str) -> Option<&TorLemma>` | Get a lemma by name |
| `fn TorLemmasLibrary::get_lemma_mut(&mut self, name: &str) -> Option<&mut TorLemma>` | Get mutable lemma |
| `fn TorLemmasLibrary::count_proven(&self) -> usize` | Count proven lemmas |
| `fn TorLemmasLibrary::count_open(&self) -> usize` | Count open lemmas |
| `fn TorLemmasLibrary::count_failed(&self) -> usize` | Count refuted lemmas |
| `fn TorLemmasLibrary::lemmas_for_degree(&self, degree: usize) -> Vec<&TorLemma>` | Lemmas about Tor in a given degree |
| `fn TorLemmasLibrary::max_degree(&self) -> Option<usize>` | Highest degree with a lemma |

## Tests

`cargo test -p tor_resolution_lemmas_library` runs 2 unit tests.
