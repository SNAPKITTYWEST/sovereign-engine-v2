# `lean_obligation_aggregator` (C080)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Aggregates every proof obligation of the pipeline: each tier lemma
(`tier_{N}_{name}`) and each cross-layer lemma (`tier_9_{id}`, depending
on its tier premises). Proven lemmas are discharged through the
obligation manager (so their proofs are type-checked again), refuted ones
are marked failed, and the report states exactly what is closed, open or
failed, broken down by tier and by evidence grade.

## Dependencies

- [C071 `type_checking_interface`](../C071/README.md)
- [C072 `obligation_management`](../C072/README.md)
- [C073 `gap_lemmas_library`](../C073/README.md)
- [C074 `memory_lemmas_library`](../C074/README.md)
- [C075 `recursion_lemmas_library`](../C075/README.md)
- [C076 `homological_lemmas_library`](../C076/README.md)
- [C077 `tor_resolution_lemmas_library`](../C077/README.md)
- [C078 `krull_lemmas_library`](../C078/README.md)
- [C079 `cross_layer_lemmas_library`](../C079/README.md)

## Re-exports

- `cross_layer_lemmas_library::{CrossLayerLemmaLibrary, STANDARD_CORRESPONDENCES}`
- `obligation_management::{ DischargeError, Evidence, Obligation, ObligationManager, ObligationStatus, }`
- `type_checking_interface::{LeanType, ProofTerm, TypeContext}`

## Public API

| Item | Description |
|---|---|
| `enum VerificationStatus` | Overall verification status. |
| `struct AggregatedObligationReport` | Aggregated proof obligation report |
| `struct ObligationStats` | Statistics for a group of obligations |
| `fn AggregatedObligationReport::from_manager(manager: &ObligationManager) -> Self` | Create from an obligation manager |
| `fn AggregatedObligationReport::all_closed(&self) -> bool` | Check if all obligations are closed |
| `fn AggregatedObligationReport::status(&self) -> VerificationStatus` | Overall status. |
| `fn AggregatedObligationReport::status_string(&self) -> String` | Get completion status |
| `fn extract_tier_from_id(id: &str) -> Option<usize>` | Tier number from an id of the form `tier_N_…`. |
| `fn tier_obligation_id(tier: usize, name: &str) -> String` | Obligation id of a tier lemma. |
| `fn cross_layer_obligation_id(id: &str) -> String` | Obligation id of a cross-layer lemma. |
| `fn collect_obligations(lib: &CrossLayerLemmaLibrary) -> Result<ObligationManager, DischargeError>` | Build the obligation manager for a cross-layer library and the tier lemmas it imported. |
| `struct FullObligationContext` | Full aggregation context combining all obligations |
| `fn FullObligationContext::new() -> Self` | Create an empty context |
| `fn FullObligationContext::from_library(lib: &CrossLayerLemmaLibrary) -> Result<Self, DischargeError>` | Aggregate a cross-layer library and its imported tier lemmas. |
| `fn FullObligationContext::standard() -> Result<Self, DischargeError>` | Aggregate the standard libraries (cross-layer lemmas not yet decided). |
| `fn FullObligationContext::add_obligation(&mut self, obligation: Obligation)` | Add an obligation to the context |
| `fn FullObligationContext::refresh_report(&mut self)` | Update the report |
| `fn FullObligationContext::is_complete(&self) -> bool` | Check overall completion |
| `fn FullObligationContext::statistics(&self) -> String` | Get aggregated statistics |

## Tests

`cargo test -p lean_obligation_aggregator` runs 6 unit tests.
