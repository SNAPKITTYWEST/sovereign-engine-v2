# `spectrum_order` (C065)

Tier 6 — Krull dimension. *Generated from the crate source; regenerate after API changes.*

Topological ordering on prime spectra.
Specialization order: `P ≤ Q` iff `P ⊆ Q` (Q is a specialization of P,
i.e. Q lies in the closure of {P}). For Spec(Z) this is exact:
`(p) ⊆ (q)` iff `q | p`, so `(0)` lies below every point.
Used for the Zariski topology, whose closed sets are the sets closed
under specialization.

## Dependencies

- [C008 `gap_tensor_ordering`](../C008/README.md)
- [C064 `spectrum_definition`](../C064/README.md)

## Public API

| Item | Description |
|---|---|
| `struct SpecializationPreorder` | Specialization preorder on spectrum |
| `fn SpecializationPreorder::from_spectrum(spec: &Spectrum) -> Self` | Create preorder from spectrum |
| `fn SpecializationPreorder::le(&self, p: u64, q: u64) -> bool` | `p ≤ q`: `(p) ⊆ (q)`, i.e. |
| `fn SpecializationPreorder::upper_set(&self, p: u64) -> BTreeSet<u64>` | Get all elements ≥ p |
| `fn SpecializationPreorder::lower_set(&self, q: u64) -> BTreeSet<u64>` | Get all elements ≤ q |
| `fn SpecializationPreorder::minimal_elements(&self, subset: &BTreeSet<u64>) -> BTreeSet<u64>` | Get minimal elements of a subset |
| `fn SpecializationPreorder::maximal_elements(&self, subset: &BTreeSet<u64>) -> BTreeSet<u64>` | Get maximal elements of a subset |
| `struct ZariskiTopology` | Zariski topology on spectrum |
| `fn ZariskiTopology::from_spectrum(spec: &Spectrum) -> Self` | Create Zariski topology from spectrum |
| `fn ZariskiTopology::is_closed(&self, subset: &BTreeSet<u64>, spectrum: &Spectrum) -> bool` | Closed sets are closed under specialization: if `P ∈ U` and `P ≤ Q` then `Q ∈ U`. |
| `fn ZariskiTopology::is_open(&self, subset: &BTreeSet<u64>, spectrum: &Spectrum) -> bool` | Open sets are complements of closed sets |
| `fn ZariskiTopology::neighborhood(&self, p: u64) -> BTreeSet<u64>` | Get neighborhood of point p |
| `fn ZariskiTopology::closure(&self, subset: &BTreeSet<u64>, spectrum: &Spectrum) -> BTreeSet<u64>` | Get closure of a subset |
| `fn ZariskiTopology::interior(&self, subset: &BTreeSet<u64>, spectrum: &Spectrum) -> BTreeSet<u64>` | Get interior of a subset |
| `fn ZariskiTopology::preorder(&self) -> &SpecializationPreorder` | Get the specialization preorder |

## Tests

`cargo test -p spectrum_order` runs 4 unit tests.
