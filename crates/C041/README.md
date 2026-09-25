# `chain_complex_shape` (C041)

Tier 4 — homological algebra. *Generated from the crate source; regenerate after API changes.*

Chain complex shape definition: rank, generators, degree information.
A chain complex C_* has a rank (number of generators) at each degree n.
This crate provides the fundamental shape primitives and operations.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C004 `gap_tensor_shape`](../C004/README.md)

## Public API

| Item | Description |
|---|---|
| `const MAX_CHAIN_RANK: usize = 1024` | The maximum rank (number of generators) at any degree in a chain complex. |
| `struct ChainDegreeShape` | Describes the shape of a chain complex at a single degree n. |
| `fn ChainDegreeShape::new(degree: i32, rank: usize) -> Self` | Create a new chain degree shape at degree n with given rank. |
| `fn ChainDegreeShape::with_generators(mut self, generators: Vec<String>) -> Self` | Set custom generator names. |
| `fn ChainDegreeShape::is_empty(&self) -> bool` | Check if this degree has rank 0 (no generators). |
| `fn ChainDegreeShape::len(&self) -> usize` | Total rank (number of generators). |
| `struct ChainComplexShape` | Full shape of a chain complex: stores rank information at all relevant degrees. |
| `fn ChainComplexShape::new() -> Self` | Create a new empty chain complex shape. |
| `fn ChainComplexShape::add_degree(&mut self, shape: ChainDegreeShape)` | Add or update a degree shape. |
| `fn ChainComplexShape::rank_at(&self, degree: i32) -> usize` | Get the rank at a specific degree. |
| `fn ChainComplexShape::degree_shape(&self, degree: i32) -> Option<&ChainDegreeShape>` | Get the shape at a specific degree (if it exists). |
| `fn ChainComplexShape::is_empty(&self) -> bool` | Check if the complex is empty (no degrees). |
| `fn ChainComplexShape::len(&self) -> usize` | Number of nonzero degrees. |
| `fn ChainComplexShape::total_rank(&self) -> usize` | Total rank across all degrees. |
| `fn ChainComplexShape::free_module(degree: i32) -> Self` | Create a chain complex shape for a free module (single generator). |
| `fn ChainComplexShape::from_ranks(pairs: Vec<(i32, usize)>) -> Self` | Create a chain complex from a list of degree/rank pairs. |
| `mod integer_matrix` | Exact integer linear algebra for small dense matrices: rank, Smith normal form (invariant factors), a Z-basis of the kernel, and checked products. |
| `enum integer_matrix::MatrixError` | Errors from integer matrix operations. |
| `struct integer_matrix::SmithForm` | Smith normal form summary of an integer matrix `A`. |
| `fn integer_matrix::SmithForm::rank(&self) -> usize` | Rank of the matrix (over Q, equivalently over Z). |
| `fn integer_matrix::SmithForm::torsion(&self) -> Vec<u64>` | Invariant factors greater than 1: the torsion of `coker(A)`. |
| `fn integer_matrix::SmithForm::is_torsion_free(&self) -> bool` | True iff `coker(A)` is torsion-free (every invariant factor is 1). |
| `fn integer_matrix::check_shape(m: &[Vec<i64>], cols: usize) -> Result<(), MatrixError>` | Check that every row has exactly `cols` entries. |
| `fn integer_matrix::is_zero(m: &[Vec<i64>]) -> bool` | True iff every entry is zero. |
| `fn integer_matrix::multiply(a: &[Vec<i64>], a_cols: usize, b: &[Vec<i64>], b_cols: usize) -> Result<Vec<Vec<i64>>, MatrixError>` | Checked product `a · b` where `a` is `a.len() × a_cols` and `b` is `b.len() × b_cols`. |
| `fn integer_matrix::apply(m: &[Vec<i64>], cols: usize, x: &[i64]) -> Result<Vec<i64>, MatrixError>` | Checked matrix–vector product `A·x`. |
| `fn integer_matrix::rank(m: &[Vec<i64>], cols: usize) -> Result<usize, MatrixError>` | Rank of `m`. |
| `fn integer_matrix::smith_form(m: &[Vec<i64>], cols: usize) -> Result<SmithForm, MatrixError>` | Smith normal form of `m` (`m.len() × cols`): invariant factors and a kernel basis. |
| `struct integer_matrix::SmithDecomposition` | Full decomposition `U·A·V = D` with unimodular `U` and `V`. |
| `fn integer_matrix::SmithDecomposition::rank(&self) -> usize` | Rank of `A`. |
| `fn integer_matrix::SmithDecomposition::invariant_factors(&self) -> Vec<u64>` | Invariant factors `\|D[i][i]\|`. |
| `fn integer_matrix::smith_decomposition(m: &[Vec<i64>], cols: usize) -> Result<SmithDecomposition, MatrixError>` | Compute `U·A·V = D` for `m` (`m.len() × cols`). |
| `fn integer_matrix::solve(m: &[Vec<i64>], cols: usize, b: &[i64]) -> Result<Option<Vec<i64>>, MatrixError>` | An integer solution of `A·x = b`, or `None` if there is none over Z. |

## Tests

`cargo test -p chain_complex_shape` runs 13 unit tests.
