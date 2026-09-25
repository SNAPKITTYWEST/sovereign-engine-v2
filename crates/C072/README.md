# `obligation_management` (C072)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Proof obligations and their bookkeeping. An obligation is closed only by
a proof that type-checks against its proposition
(`type_checking_interface`), and — when discharged through the manager —
only after every dependency is closed. Dependency cycles and references to
unknown obligations are detected, not silently ignored.

## Dependencies

- [C010 `gap_tensor_trace`](../C010/README.md)
- [C071 `type_checking_interface`](../C071/README.md)

## Re-exports

- `type_checking_interface::{ DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError, }`

## Public API

| Item | Description |
|---|---|
| `enum ObligationStatus` | Status of a proof obligation |
| `struct Obligation` | A single proof obligation |
| `fn Obligation::new(id: String, proposition: LeanType) -> Self` | Create a new open obligation |
| `fn Obligation::add_dependency(&mut self, dep_id: String)` | Add a dependency |
| `fn Obligation::dependencies_satisfied(&self, obligations: &[Obligation]) -> bool` | Check if all dependencies are closed |
| `fn Obligation::prove(&mut self, proof: ProofTerm) -> Result<(), TypeError>` | Close with a self-contained proof (checked in an empty context: only `Trivial` for `True` and decided statements qualify). |
| `fn Obligation::evidence(&self) -> Option<Evidence>` | Evidence grade of the closing proof, if closed. |
| `enum DischargeError` | Why an obligation could not be discharged. |
| `struct ObligationManager` | Manager for a collection of proof obligations |
| `fn ObligationManager::new() -> Self` | Create a new obligation manager |
| `fn ObligationManager::add_obligation(&mut self, obligation: Obligation)` | Add an obligation |
| `fn ObligationManager::get_obligation(&self, id: &str) -> Option<&Obligation>` | Get an obligation by ID |
| `fn ObligationManager::get_obligation_mut(&mut self, id: &str) -> Option<&mut Obligation>` | Get mutable obligation |
| `fn ObligationManager::discharge(&mut self, id: &str, proof: ProofTerm) -> Result<(), DischargeError>` | Close obligation `id` with `proof`, checked in this manager's context. |
| `fn ObligationManager::mark_failed(&mut self, id: &str) -> Result<(), DischargeError>` | Mark obligation `id` as refuted. |
| `fn ObligationManager::count_open(&self) -> usize` | Count open obligations |
| `fn ObligationManager::count_closed(&self) -> usize` | Count closed obligations |
| `fn ObligationManager::count_status(&self, status: ObligationStatus) -> usize` | Count obligations with a given status |
| `fn ObligationManager::evidence_counts(&self) -> BTreeMap<Evidence, usize>` | Closed obligations grouped by the evidence grade of their proofs. |
| `fn ObligationManager::missing_dependencies(&self) -> Vec<(String, String)>` | Dependencies that name no obligation, as `(obligation, missing id)`. |
| `fn ObligationManager::find_cycle(&self) -> Option<Vec<String>>` | A dependency cycle, if any, as the ids along it (first id repeated at the end). |
| `fn ObligationManager::try_topological_order(&self) -> Result<Vec<String>, Vec<String>>` | Obligations with dependencies first, or the cycle that prevents such an order. |
| `fn ObligationManager::topological_order(&self) -> Vec<String>` | Obligations with dependencies first. |

## Tests

`cargo test -p obligation_management` runs 6 unit tests.
