# `chain_complex_types` (C042)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Chain element types and operations. Defines elements of chain complexes
as formal sums of generators with integer coefficients. Elements and
chains can be checked against a `ChainComplexShape`, and coefficient
addition and scaling panic on i64 overflow instead of wrapping.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C041 `chain_complex_shape`](../C041/README.md)

## Public API

| Item | Description |
|---|---|
| `struct ChainElement` | A single chain element at a fixed degree n. |
| `fn ChainElement::new(degree: i32) -> Self` | Create a new zero chain element at degree n. |
| `fn ChainElement::from_generator(degree: i32, gen_idx: usize, coeff: i64) -> Self` | Create a chain element with a single generator. |
| `fn ChainElement::coeff(&self, gen_idx: usize) -> i64` | Get the coefficient of a generator. |
| `fn ChainElement::set_coeff(&mut self, gen_idx: usize, coeff: i64)` | Set the coefficient of a generator. |
| `fn ChainElement::add_coeff(&mut self, gen_idx: usize, delta: i64)` | Add a coefficient to an existing generator. |
| `fn ChainElement::fits_shape(&self, shape: &ChainComplexShape) -> bool` | Whether every generator in the support is a generator of C_n in `shape` (its index is below the rank at this element's degree). |
| `fn ChainElement::is_zero(&self) -> bool` | Check if this is the zero element. |
| `fn ChainElement::support_size(&self) -> usize` | Number of nonzero generators in this element. |
| `fn ChainElement::support(&self) -> Vec<usize>` | Get all generator indices with nonzero coefficients. |
| `fn ChainElement::add(&mut self, other: &ChainElement)` | Add two chain elements (must be at the same degree). |
| `fn ChainElement::scalar_mul(&mut self, c: i64)` | Scalar multiply this chain element by c. |
| `fn ChainElement::neg(&self) -> Self` | Return the negation of this chain element. |
| `fn ChainElement::plus(mut a: ChainElement, b: &ChainElement) -> ChainElement` | Compute the sum of two chain elements (immutable version). |
| `fn ChainElement::sorted_coefficients(&self) -> Vec<(usize, i64)>` | Get all coefficients in sorted order by generator index. |
| `fn ChainElement::coeff_gcd(&self) -> i64` | Compute the GCD of all coefficients (for normalization). |
| `fn ChainElement::normalize(&mut self)` | Normalize this element by dividing all coefficients by their GCD. |
| `struct Chain` | A general chain (possibly with generators at multiple degrees). |
| `fn Chain::new() -> Self` | Create a new empty chain. |
| `fn Chain::add_element(&mut self, elem: ChainElement)` | Add a chain element at its degree. |
| `fn Chain::element_at(&self, degree: i32) -> Option<&ChainElement>` | Get the chain element at a specific degree. |
| `fn Chain::support_degrees(&self) -> Vec<i32>` | Get all degrees with nonzero elements. |
| `fn Chain::is_zero(&self) -> bool` | Check if this chain is zero. |
| `fn Chain::support_size(&self) -> usize` | Number of nonzero degrees. |
| `fn Chain::fits_shape(&self, shape: &ChainComplexShape) -> bool` | Whether every element of the chain fits `shape`. |
| `fn Chain::scalar_mul(&mut self, c: i64)` | Scalar multiply the entire chain. |
| `fn Chain::add(&mut self, other: &Chain)` | Add another chain to this one. |
| `fn Chain::neg(&self) -> Self` | Return the negation of this chain. |

## Tests

`cargo test -p chain_complex_types` runs 12 unit tests.
