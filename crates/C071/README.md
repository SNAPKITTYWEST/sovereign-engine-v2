# `type_checking_interface` (C071)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

A small proof checker for proof obligations, modelled on the implicational
fragment of Lean's kernel. Statements are s; the checker
decides whether a  proves a statement in a :

* `Trivial` proves `True` and nothing else;
* `Reference(n)` proves the type recorded for `n` in the context — a
  hypothesis, a theorem, or an axiom;
* `Axiom(n)` proves the type of a declared axiom;
* `App(f, x)` is modus ponens: from `f : A → B` and `x : A`, conclude `B`;
* `Decided(cert)` proves the statement recorded in a
  , which can only be obtained by running its
  decision procedure to success over a stated finite domain.

This crate does not run Lean. Every proof carries an  grade so
reports can separate constructive proofs, exhaustive computation,
references to theorems proven elsewhere, and bare assumptions.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C003 `gap_tensor_spectral`](../C003/README.md)

## Public API

| Item | Description |
|---|---|
| `enum LeanType` | A Lean type or proposition |
| `fn LeanType::prop() -> Self` | The sort `Prop` |
| `fn LeanType::type_u(u: usize) -> Self` | Create a type at universe level u |
| `fn LeanType::arrow(from: LeanType, to: LeanType) -> Self` | Implication / function type `from → to` |
| `fn LeanType::atom(name: impl Into<String>) -> Self` | A named proposition. |
| `fn LeanType::truth() -> Self` | The proposition `True`, proven by `Trivial`. |
| `fn LeanType::to_string(&self) -> String` | Get string representation |
| `struct DecisionCertificate` | Record of a decision procedure that ran to success. |
| `fn DecisionCertificate::run(statement: LeanType, procedure: impl Into<String>, check: impl FnOnce() -> Result<u64, String>) -> Result<Self, String>` | Run `check`, which must examine every case of the finite domain named in `statement` and return how many cases it checked, or describe a counterexample. |
| `fn DecisionCertificate::statement(&self) -> &LeanType` | The statement decided. |
| `fn DecisionCertificate::procedure(&self) -> &str` | Name of the decision procedure. |
| `fn DecisionCertificate::cases_checked(&self) -> u64` | Number of cases examined. |
| `enum Evidence` | Strength of the evidence behind a proof, weakest first. |
| `enum ProofTerm` | A proof term. |
| `fn ProofTerm::axiom(name: &str) -> Self` | Use of the axiom `name`. |
| `fn ProofTerm::reference(name: &str) -> Self` | Reference to `name`. |
| `fn ProofTerm::app(f: ProofTerm, x: ProofTerm) -> Self` | Modus ponens. |
| `fn ProofTerm::is_complete(&self) -> bool` | Structurally complete (no holes). |
| `fn ProofTerm::evidence(&self) -> Evidence` | Weakest evidence the proof relies on. |
| `enum TypeError` | Why a proof term fails to check. |
| `struct TypeContext` | A type checking context: hypotheses, theorems and axioms. |
| `fn TypeContext::new() -> Self` | Create an empty context |
| `fn TypeContext::add_variable(&mut self, name: String, ty: LeanType)` | Add a hypothesis |
| `fn TypeContext::add_theorem(&mut self, name: String, ty: LeanType)` | Add a theorem |
| `fn TypeContext::add_axiom(&mut self, name: String, ty: LeanType)` | Declare an axiom |
| `fn TypeContext::lookup_variable(&self, name: &str) -> Option<&LeanType>` | Look up a hypothesis |
| `fn TypeContext::lookup_theorem(&self, name: &str) -> Option<&LeanType>` | Look up a theorem |
| `fn TypeContext::lookup_axiom(&self, name: &str) -> Option<&LeanType>` | Look up an axiom |
| `fn TypeContext::infer(&self, proof: &ProofTerm) -> Result<LeanType, TypeError>` | The statement a proof term proves in this context. |
| `fn TypeContext::check(&self, proof: &ProofTerm, statement: &LeanType) -> Result<(), TypeError>` | Check that `proof` proves `statement`. |

## Tests

`cargo test -p type_checking_interface` runs 8 unit tests.
