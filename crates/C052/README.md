# tensor_product_module (C052)

## What it does
Represents the tensor product module `M ⊗_R N` as a free module on generator pairs `(m_index, n_index)`, with formal-sum elements (`TensorElement`) and a bilinearity-relations list on the module itself (`TensorProductModule.relations`) that is currently populated but never enforced/used anywhere.

## Public API
- `TensorGenerator { m_index, n_index }` — `new()`.
- `TensorElement { coeffs: HashMap<TensorGenerator, i32> }` — `zero()`, `from_generator()`, `add()`, `scale()` (drops zero entries after scaling), `is_zero()`, `num_generators()`.
- `TensorProductModule { m_rank, n_rank, relations: Vec<TensorElement> }` — `new()`, `add_relation()` (drops zero relations), `free_rank()` (= `m_rank * n_rank`), `basis_generators()`, `generator(i, j) -> Option<TensorElement>` (bounds-checked).

## Pipeline position
No dependencies. Foundational free-module type for the Tor sub-layer, consumed by `resolution_tensored` (C053, re-exports its types), `derived_homology` (C054, re-exports `TensorProductModule`), and `tor_zero_structure` (C055, `analyze_tor_zero` uses `free_rank()` directly as `Tor_0`'s rank).

## Notes / gaps
- **Gap — `relations` is unused everywhere:** `TensorProductModule.relations` and `add_relation()` exist and are exercised by nothing else in the crate or its consumers — the module's `free_rank()` always returns the *unquotiented* free rank `m_rank * n_rank`, never accounting for any bilinearity relations that were added. This means `TensorProductModule` currently models the free module on generator pairs, not the actual tensor product quotiented by bilinearity (`m ⊗ (n1+n2) = m⊗n1 + m⊗n2`, etc.) — the relations field is a placeholder for a quotient that's never taken. `analyze_tor_zero` (C055) inherits this: it reports `Tor_0` rank as the *free* rank, not the true tensor-product rank after relations.
- `TensorElement::add`'s cleanup (`if self.coeffs[gen] == 0 { self.coeffs.remove(gen) }`) does an extra hashmap lookup (`self.coeffs[gen]`) right after `entry().or_insert()` already gave a mutable reference — functionally correct but slightly redundant; a `get_mut` + retain-style pattern would avoid the double lookup.
- 5 unit tests, none touching `relations`/`add_relation` at all — consistent with the gap above (the untested code path is also the never-consumed one).
