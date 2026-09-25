# `recursion_lemmas_library` (C075)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Lemmas about the recursive solver's depth control and backtracking
(Tier 3).  decides the bounded
lemmas by running the Tier 3 code over every case (evidence grade
`Computed`). Termination of the solver on arbitrary inputs is stated and
left `Open`: it needs a termination measure proven in Lean.

## Dependencies

- [C031 `recursive_solver_state`](../C031/README.md)
- [C032 `recursion_depth_management`](../C032/README.md)
- [C036 `recursion_base_case`](../C036/README.md)
- [C037 `recursion_backtracking`](../C037/README.md)
- [C071 `type_checking_interface`](../C071/README.md)

## Re-exports

- `type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError}`

## Public API

| Item | Description |
|---|---|
| `const DECIDED_DEPTH: usize = 20` | Largest depth bound covered by the decided lemmas. |
| `enum RecursionLemmaStatus` | Status of a recursion lemma |
| `struct RecursionLemma` | A recursion termination or depth lemma |
| `fn RecursionLemma::new(name: String, statement: LeanType) -> Self` | Create a new open lemma |
| `fn RecursionLemma::with_max_depth(mut self, depth: usize) -> Self` | Set the largest depth covered |
| `fn RecursionLemma::with_note(mut self, note: impl Into<String>) -> Self` | Attach a note |
| `fn RecursionLemma::prove(&mut self, proof: ProofTerm) -> Result<(), TypeError>` | Close with a self-contained proof (checked in an empty context). |
| `fn RecursionLemma::is_proven(&self) -> bool` | Check if lemma is proven |
| `fn RecursionLemma::evidence(&self) -> Option<Evidence>` | Evidence grade, if proven |
| `struct RecursionLemmasLibrary` | Library of recursion lemmas |
| `fn RecursionLemmasLibrary::new() -> Self` | Create an empty library |
| `fn RecursionLemmasLibrary::standard() -> Self` | The Tier 3 lemma set, with every bounded lemma decided. |
| `fn RecursionLemmasLibrary::decide(&mut self, mut lemma: RecursionLemma, procedure: &str, check: impl FnOnce() -> Result<u64, String>)` | Register `lemma` and run its decision procedure. |
| `fn RecursionLemmasLibrary::prove_lemma(&mut self, name: &str, proof: ProofTerm) -> Result<(), TypeError>` | Close lemma `name` with `proof`, checked in this library's context. |
| `fn RecursionLemmasLibrary::add_lemma(&mut self, lemma: RecursionLemma)` | Add a lemma |
| `fn RecursionLemmasLibrary::get_lemma(&self, name: &str) -> Option<&RecursionLemma>` | Get a lemma by name |
| `fn RecursionLemmasLibrary::get_lemma_mut(&mut self, name: &str) -> Option<&mut RecursionLemma>` | Get mutable lemma |
| `fn RecursionLemmasLibrary::count_proven(&self) -> usize` | Count proven lemmas |
| `fn RecursionLemmasLibrary::count_open(&self) -> usize` | Count open lemmas |
| `fn RecursionLemmasLibrary::count_failed(&self) -> usize` | Count refuted lemmas |
| `fn RecursionLemmasLibrary::lemmas_for_depth(&self, depth: usize) -> Vec<&RecursionLemma>` | Lemmas that cover `depth` (unbounded lemmas cover every depth) |
| `fn RecursionLemmasLibrary::max_covered_depth(&self) -> Option<usize>` | Largest bounded depth covered by any lemma |

## Tests

`cargo test -p recursion_lemmas_library` runs 2 unit tests.
