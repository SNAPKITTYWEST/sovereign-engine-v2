# `differential_operator` (C043)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

The differential operator d: C_n -> C_{n-1} in a chain complex.
The core operator of homological algebra: d² = 0 is verified separately in C044.

## Dependencies

- [C041 `chain_complex_shape`](../C041/README.md)
- [C042 `chain_complex_types`](../C042/README.md)

## Re-exports

- `chain_complex_shape::{ChainComplexShape, ChainDegreeShape, MAX_CHAIN_RANK}`

## Public API

| Item | Description |
|---|---|
| `struct DifferentialOperator` | Represents the differential operator d in a chain complex. |
| `fn DifferentialOperator::new(shape: ChainComplexShape) -> Self` | Create a new differential operator for a given chain complex shape. |
| `fn DifferentialOperator::set_generator_image(&mut self, source_degree: i32, source_gen: usize, target_degree: i32, target_image: Vec<(usize, i64)>)` | Set the image of a single generator under the differential. |
| `fn DifferentialOperator::apply_to_generator(&self, degree: i32, gen_idx: usize) -> ChainElement` | Apply the differential to a single generator. |
| `fn DifferentialOperator::apply_to_element(&self, elem: &ChainElement) -> ChainElement` | Apply the differential to a chain element. |
| `fn DifferentialOperator::apply(&self, chain: &Chain) -> Chain` | Apply the differential to a general chain. |
| `fn DifferentialOperator::matrix_at(&self, degree: i32) -> Option<&HashMap<usize, Vec<(i32, usize, i64)>>>` | Get the matrix of the differential at a specific degree. |
| `fn DifferentialOperator::source_rank(&self, degree: i32) -> usize` | Get the rank of the source module C_n. |
| `fn DifferentialOperator::target_rank(&self, degree: i32) -> usize` | Get the rank of the target module C_{n-1}. |
| `fn DifferentialOperator::is_consistent(&self) -> bool` | Check that the differential is "locally" consistent with the current shape: every image lies at degree n-1 and every source and target generator index is below the rank of its degree. |
| `fn DifferentialOperator::to_dense_matrix(&self, degree: i32) -> Vec<Vec<i64>>` | Compute the matrix representation as nested vectors. |
| `fn DifferentialOperator::support_degrees(&self) -> Vec<i32>` | Get all degrees where the differential is nontrivial (has nonzero matrix). |

## Tests

`cargo test -p differential_operator` runs 9 unit tests.
