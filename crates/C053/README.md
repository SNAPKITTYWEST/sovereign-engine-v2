# `resolution_tensored` (C053)

Tier 5 — Tor functor. *Generated from the crate source; regenerate after API changes.*

The tensor product of two free chain complexes, `Tot(P ⊗ Q)`.

For complexes `P` (differentials `d^P_{k+1}: P_{k+1} → P_k`) and `Q`,
`Tot_n = ⊕_{a+b=n} P_a ⊗ Q_b` with differential
`D(x ⊗ y) = d^P x ⊗ y + (−1)^a x ⊗ d^Q y`. Within `Tot_n` blocks are
ordered by increasing `a`, and inside block `(a, b)` the generator
`p_i ⊗ q_j` has index `i · rank Q_b + j`.

When `P` resolves `M` and `Q` resolves `N`, `H_n(Tot(P ⊗ Q)) = Tor_n(M, N)`.

## Dependencies

- [C043 `differential_operator`](../C043/README.md)
- [C044 `differential_squared_zero`](../C044/README.md)
- [C052 `tensor_product_module`](../C052/README.md)

## Re-exports

- `tensor_product_module::integer_matrix`
- `tensor_product_module::{TensorElement, TensorGenerator, TensorProductModule}`

## Public API

| Item | Description |
|---|---|
| `struct TensoredComplex` | `Tot(P ⊗ Q)` with explicit differentials. |
| `fn TensoredComplex::from_complexes(p_ranks: Vec<usize>, p_diffs: &[Vec<Vec<i64>>], q_ranks: Vec<usize>, q_diffs: &[Vec<Vec<i64>>]) -> Result<Self, String>` | Build `Tot(P ⊗ Q)`. |
| `fn TensoredComplex::new(p_ranks: Vec<usize>, n_rank: usize) -> Self` | `P` with zero differentials tensored with the free module `Z^n_rank`. |
| `fn TensoredComplex::tensored_rank(&self, degree: usize) -> Option<usize>` | Rank of `P_degree ⊗ Q_0`. |
| `fn TensoredComplex::total_rank_at(&self, n: usize) -> usize` | Rank of `Tot_n` (0 outside the complex). |
| `fn TensoredComplex::block_offset(&self, n: usize, a: usize) -> Option<usize>` | Index within `Tot_n` of the first generator of block `P_a ⊗ Q_{n-a}`, if that block exists. |
| `fn TensoredComplex::get_differential_rank(&self, degree: usize) -> Option<usize>` | Rank of `D_n` (0 for `n = 0` and outside the complex). |
| `fn TensoredComplex::differential_matrix(&self, n: usize) -> Vec<Vec<i64>>` | Dense matrix of `D_n` (rows `Tot_{n-1}`, columns `Tot_n`). |
| `fn TensoredComplex::operator(&self) -> &DifferentialOperator` | The total complex as a differential operator (degrees `0..`). |
| `fn TensoredComplex::verify_complex(&self) -> bool` | Check `D ∘ D = 0` everywhere, exactly. |
| `fn TensoredComplex::num_degrees(&self) -> usize` | Number of degrees of `Tot`. |
| `fn TensoredComplex::total_rank(&self) -> usize` | Sum of all `Tot_n` ranks. |
| `struct TensoredComplexProperties` | Kernel/image ranks and exactness of a tensored complex at each degree. |
| `fn TensoredComplexProperties::analyze(complex: &TensoredComplex) -> Result<Self, MatrixError>` | Compute kernel and image ranks and exactness exactly. |
| `fn TensoredComplexProperties::is_exact(&self) -> bool` | Exact at every degree? |

## Tests

`cargo test -p resolution_tensored` runs 4 unit tests.
