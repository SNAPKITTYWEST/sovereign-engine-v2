# `cross_layer_lemmas_library` (C079)

Tier 7 — proof obligations. *Generated from the crate source; regenerate after API changes.*

Statements that relate two tiers, and the bookkeeping to close them.

 declares the cross-layer
correspondences the pipeline relies on (all `Open`) and imports every
proven lemma of the tier libraries (C073–C078) as a citable theorem named
`tier{N}.{name}`. The correspondences involve code from several tiers, so
they are decided by the Tier 9 crates (which depend on that code) through
; nothing here closes them by
assumption.

## Dependencies

- [C071 `type_checking_interface`](../C071/README.md)
- [C073 `gap_lemmas_library`](../C073/README.md)
- [C074 `memory_lemmas_library`](../C074/README.md)
- [C075 `recursion_lemmas_library`](../C075/README.md)
- [C076 `homological_lemmas_library`](../C076/README.md)
- [C077 `tor_resolution_lemmas_library`](../C077/README.md)
- [C078 `krull_lemmas_library`](../C078/README.md)

## Re-exports

- `type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError}`

## Public API

| Item | Description |
|---|---|
| `struct TierLemmaRecord` | Summary of one tier lemma imported from a tier library. |
| `fn TierLemmaRecord::qualified_name(&self) -> String` | Qualified name `tier{N}.{name}`. |
| `fn standard_tier_lemmas() -> Vec<TierLemmaRecord>` | Collect every lemma of the six standard tier libraries. |
| `struct CrossLayerLemma` | A cross-layer relationship between two tiers |
| `fn CrossLayerLemma::new(id: String, source_tier: usize, target_tier: usize, statement: LeanType) -> Self` | Create a cross-layer lemma |
| `fn CrossLayerLemma::with_premises(mut self, premises: &[&str]) -> Self` | Record the tier lemmas this statement builds on |
| `fn CrossLayerLemma::prove(&mut self, proof: ProofTerm) -> Result<(), TypeError>` | Close with a self-contained proof (checked in an empty context). |
| `fn CrossLayerLemma::is_proven(&self) -> bool` | Is this lemma proven? |
| `fn CrossLayerLemma::evidence(&self) -> Option<Evidence>` | Evidence grade, if proven |
| `fn CrossLayerLemma::direction_name(&self) -> String` | Get direction name |
| `struct CrossLayerLemmaLibrary` | Cross-layer lemmas plus the imported tier lemmas. |
| `const STANDARD_CORRESPONDENCES: [(&str, &str)` | Ids of the standard cross-layer lemmas, with the Tier 9 crate that decides each. |
| `fn CrossLayerLemmaLibrary::new() -> Self` | Create an empty library |
| `fn CrossLayerLemmaLibrary::standard() -> Self` | The standard cross-layer statements (all open) with the six tier libraries imported. |
| `fn CrossLayerLemmaLibrary::import_tier_lemmas(&mut self, records: Vec<TierLemmaRecord>)` | Import tier lemmas; proven ones become theorems `tier{N}.{name}`. |
| `fn CrossLayerLemmaLibrary::unmet_premises(&self, id: &str) -> Vec<String>` | Premises of `id` that are not proven tier lemmas. |
| `fn CrossLayerLemmaLibrary::decide(&mut self, id: &str, procedure: &str, check: impl FnOnce() -> Result<u64, String>) -> Result<(), String>` | Run a decision procedure for cross-layer lemma `id`. |
| `fn CrossLayerLemmaLibrary::add_lemma(&mut self, lemma: CrossLayerLemma)` | Add a lemma to the library |
| `fn CrossLayerLemmaLibrary::get_lemma(&self, id: &str) -> Option<&CrossLayerLemma>` | Get a lemma by ID |
| `fn CrossLayerLemmaLibrary::count_proven(&self) -> usize` | Count proven lemmas |
| `fn CrossLayerLemmaLibrary::lemmas_for_transition(&self, from: usize, to: usize) -> Vec<&CrossLayerLemma>` | Get all lemmas for a given tier transition |
| `fn CrossLayerLemmaLibrary::are_tiers_related(&self, tier1: usize, tier2: usize) -> bool` | Check if two tiers are related (direct lemma exists) |
| `fn CrossLayerLemmaLibrary::proof_coverage(&self) -> f64` | Fraction of cross-layer lemmas proven (1.0 when empty) |

## Tests

`cargo test -p cross_layer_lemmas_library` runs 5 unit tests.
