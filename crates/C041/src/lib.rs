//! chain_complex_shape
//!
//! Chain complex shape definition: rank, generators, degree information.
//! A chain complex C_* has a rank (number of generators) at each degree n.
//! This crate provides the fundamental shape primitives and operations.

#![warn(missing_docs)]

/// The maximum rank (number of generators) at any degree in a chain complex.
pub const MAX_CHAIN_RANK: usize = 1024;

/// Describes the shape of a chain complex at a single degree n.
///
/// A chain complex is graded; at each degree n we have:
/// - rank: number of free generators (basis elements)
/// - degree: the integer degree value
/// - generators: list of generator descriptors
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChainDegreeShape {
    /// The degree n (can be negative for cohomology).
    pub degree: i32,
    /// Number of generators (rank of free module at this degree).
    pub rank: usize,
    /// Generator labels/identifiers (optional descriptors).
    pub generators: Vec<String>,
}

impl ChainDegreeShape {
    /// Create a new chain degree shape at degree n with given rank.
    ///
    /// # Arguments
    /// * `degree` - The degree n of this component
    /// * `rank` - Number of generators at this degree
    ///
    /// # Panics
    /// Panics if rank > MAX_CHAIN_RANK.
    pub fn new(degree: i32, rank: usize) -> Self {
        assert!(rank <= MAX_CHAIN_RANK, "rank {} exceeds MAX_CHAIN_RANK", rank);
        Self {
            degree,
            rank,
            generators: (0..rank).map(|i| format!("gen_{}", i)).collect(),
        }
    }

    /// Set custom generator names.
    pub fn with_generators(mut self, generators: Vec<String>) -> Self {
        assert_eq!(generators.len(), self.rank, "generator count mismatch");
        self.generators = generators;
        self
    }

    /// Check if this degree has rank 0 (no generators).
    pub fn is_empty(&self) -> bool {
        self.rank == 0
    }

    /// Total rank (number of generators).
    pub fn len(&self) -> usize {
        self.rank
    }
}

/// Full shape of a chain complex: stores rank information at all relevant degrees.
///
/// A chain complex C_* = {C_n, d_n} consists of modules C_n at integer degrees n
/// with differentials d_n: C_n -> C_{n-1}. This struct tracks the shape: which
/// degrees have nonzero modules and their ranks.
#[derive(Debug, Clone)]
pub struct ChainComplexShape {
    /// Minimum degree with nonzero module (can be negative).
    pub min_degree: i32,
    /// Maximum degree with nonzero module.
    pub max_degree: i32,
    /// Shape at each degree: degree -> ChainDegreeShape
    pub degrees: Vec<ChainDegreeShape>,
    /// Total rank summed across all degrees.
    total_rank: usize,
}

impl ChainComplexShape {
    /// Create a new empty chain complex shape.
    pub fn new() -> Self {
        Self {
            min_degree: 0,
            max_degree: -1, // empty
            degrees: Vec::new(),
            total_rank: 0,
        }
    }

    /// Add or update a degree shape.
    pub fn add_degree(&mut self, shape: ChainDegreeShape) {
        if self.degrees.is_empty() {
            self.min_degree = shape.degree;
            self.max_degree = shape.degree;
        } else {
            self.min_degree = self.min_degree.min(shape.degree);
            self.max_degree = self.max_degree.max(shape.degree);
        }
        // Update total rank
        let old_rank = self.degrees
            .iter()
            .find(|d| d.degree == shape.degree)
            .map(|d| d.rank)
            .unwrap_or(0);
        self.total_rank -= old_rank;
        self.total_rank += shape.rank;

        // Replace or insert
        if let Some(pos) = self.degrees.iter().position(|d| d.degree == shape.degree) {
            self.degrees[pos] = shape;
        } else {
            self.degrees.push(shape);
            // Sort by degree for consistency
            self.degrees.sort_by_key(|d| d.degree);
        }
    }

    /// Get the rank at a specific degree.
    pub fn rank_at(&self, degree: i32) -> usize {
        self.degrees
            .iter()
            .find(|d| d.degree == degree)
            .map(|d| d.rank)
            .unwrap_or(0)
    }

    /// Get the shape at a specific degree (if it exists).
    pub fn degree_shape(&self, degree: i32) -> Option<&ChainDegreeShape> {
        self.degrees.iter().find(|d| d.degree == degree)
    }

    /// Check if the complex is empty (no degrees).
    pub fn is_empty(&self) -> bool {
        self.degrees.is_empty()
    }

    /// Number of nonzero degrees.
    pub fn len(&self) -> usize {
        self.degrees.len()
    }

    /// Total rank across all degrees.
    pub fn total_rank(&self) -> usize {
        self.total_rank
    }

    /// Create a chain complex shape for a free module (single generator).
    /// Useful for testing and simple chains.
    pub fn free_module(degree: i32) -> Self {
        let mut shape = Self::new();
        shape.add_degree(ChainDegreeShape::new(degree, 1));
        shape
    }

    /// Create a chain complex from a list of degree/rank pairs.
    pub fn from_ranks(pairs: Vec<(i32, usize)>) -> Self {
        let mut shape = Self::new();
        for (degree, rank) in pairs {
            shape.add_degree(ChainDegreeShape::new(degree, rank));
        }
        shape
    }
}

impl Default for ChainComplexShape {
    fn default() -> Self {
        Self::new()
    }
}

/// Exact integer linear algebra for small dense matrices: rank, Smith normal
/// form (invariant factors), a Z-basis of the kernel, and checked products.
///
/// Matrices are row-major `Vec<Vec<i64>>`. A matrix with zero rows cannot
/// record its column count, so the column count is always passed explicitly.
/// Intermediate arithmetic is done in `i128` with overflow checks; results
/// that do not fit return [`integer_matrix::MatrixError::Overflow`] rather
/// than a wrong answer.
pub mod integer_matrix {
    use std::fmt;

    /// Errors from integer matrix operations.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub enum MatrixError {
        /// A row's length differs from the declared column count.
        Ragged {
            /// Row index.
            row: usize,
            /// Its length.
            len: usize,
            /// Declared column count.
            cols: usize,
        },
        /// Inner dimensions of a product disagree.
        DimensionMismatch {
            /// Columns of the left factor.
            left_cols: usize,
            /// Rows of the right factor.
            right_rows: usize,
        },
        /// A vector's length does not match the matrix.
        LengthMismatch {
            /// Required length.
            expected: usize,
            /// Supplied length.
            got: usize,
        },
        /// A value exceeded the supported range.
        Overflow,
    }

    impl fmt::Display for MatrixError {
        fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            write!(f, "{self:?}")
        }
    }

    impl std::error::Error for MatrixError {}

    /// Smith normal form summary of an integer matrix `A`.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct SmithForm {
        /// Positive invariant factors `d_1 | d_2 | … | d_r`, where `r` is the
        /// rank of `A`.
        pub invariant_factors: Vec<u64>,
        /// A Z-basis of `{x ∈ Z^cols : A·x = 0}`.
        pub kernel_basis: Vec<Vec<i64>>,
    }

    impl SmithForm {
        /// Rank of the matrix (over Q, equivalently over Z).
        pub fn rank(&self) -> usize {
            self.invariant_factors.len()
        }

        /// Invariant factors greater than 1: the torsion of `coker(A)`.
        pub fn torsion(&self) -> Vec<u64> {
            self.invariant_factors.iter().copied().filter(|&d| d > 1).collect()
        }

        /// True iff `coker(A)` is torsion-free (every invariant factor is 1).
        pub fn is_torsion_free(&self) -> bool {
            self.invariant_factors.iter().all(|&d| d == 1)
        }
    }

    /// Check that every row has exactly `cols` entries.
    pub fn check_shape(m: &[Vec<i64>], cols: usize) -> Result<(), MatrixError> {
        for (row, r) in m.iter().enumerate() {
            if r.len() != cols {
                return Err(MatrixError::Ragged { row, len: r.len(), cols });
            }
        }
        Ok(())
    }

    /// True iff every entry is zero.
    pub fn is_zero(m: &[Vec<i64>]) -> bool {
        m.iter().all(|r| r.iter().all(|&x| x == 0))
    }

    /// Checked product `a · b` where `a` is `a.len() × a_cols` and `b` is
    /// `b.len() × b_cols`.
    pub fn multiply(
        a: &[Vec<i64>],
        a_cols: usize,
        b: &[Vec<i64>],
        b_cols: usize,
    ) -> Result<Vec<Vec<i64>>, MatrixError> {
        check_shape(a, a_cols)?;
        check_shape(b, b_cols)?;
        if a_cols != b.len() {
            return Err(MatrixError::DimensionMismatch {
                left_cols: a_cols,
                right_rows: b.len(),
            });
        }
        let mut out = vec![vec![0i64; b_cols]; a.len()];
        for (i, row) in a.iter().enumerate() {
            for j in 0..b_cols {
                let mut sum = 0i128;
                for (k, &x) in row.iter().enumerate() {
                    sum = sum
                        .checked_add(x as i128 * b[k][j] as i128)
                        .ok_or(MatrixError::Overflow)?;
                }
                out[i][j] = i64::try_from(sum).map_err(|_| MatrixError::Overflow)?;
            }
        }
        Ok(out)
    }

    /// Checked matrix–vector product `A·x`.
    pub fn apply(m: &[Vec<i64>], cols: usize, x: &[i64]) -> Result<Vec<i64>, MatrixError> {
        let column: Vec<Vec<i64>> = x.iter().map(|&v| vec![v]).collect();
        Ok(multiply(m, cols, &column, 1)?.into_iter().map(|r| r[0]).collect())
    }

    /// Rank of `m`.
    pub fn rank(m: &[Vec<i64>], cols: usize) -> Result<usize, MatrixError> {
        Ok(smith_form(m, cols)?.rank())
    }

    fn row_sub(a: &mut [Vec<i128>], target: usize, source: usize, q: i128) -> Result<(), MatrixError> {
        for c in 0..a[target].len() {
            let delta = a[source][c].checked_mul(q).ok_or(MatrixError::Overflow)?;
            a[target][c] = a[target][c].checked_sub(delta).ok_or(MatrixError::Overflow)?;
        }
        Ok(())
    }

    fn col_sub(a: &mut [Vec<i128>], target: usize, source: usize, q: i128) -> Result<(), MatrixError> {
        for row in a.iter_mut() {
            let delta = row[source].checked_mul(q).ok_or(MatrixError::Overflow)?;
            row[target] = row[target].checked_sub(delta).ok_or(MatrixError::Overflow)?;
        }
        Ok(())
    }

    fn swap_cols(a: &mut [Vec<i128>], i: usize, j: usize) {
        if i != j {
            for row in a.iter_mut() {
                row.swap(i, j);
            }
        }
    }

    fn identity(n: usize) -> Vec<Vec<i128>> {
        (0..n)
            .map(|i| (0..n).map(|j| i128::from(i == j)).collect())
            .collect()
    }

    /// Row transform `U` and its inverse, when tracked.
    type RowTransform = Option<(Vec<Vec<i128>>, Vec<Vec<i128>>)>;

    fn swap_rows(a: &mut [Vec<i128>], u: &mut RowTransform, i: usize, j: usize) {
        a.swap(i, j);
        if let Some((u, u_inv)) = u {
            u.swap(i, j);
            swap_cols(u_inv, i, j);
        }
    }

    /// `row_target -= q · row_source` on `a`, mirrored on `U` (left) and on
    /// `U⁻¹` (right, as the inverse column operation).
    fn sub_rows(
        a: &mut [Vec<i128>],
        u: &mut RowTransform,
        target: usize,
        source: usize,
        q: i128,
    ) -> Result<(), MatrixError> {
        row_sub(a, target, source, q)?;
        if let Some((u, u_inv)) = u {
            row_sub(u, target, source, q)?;
            let neg = q.checked_neg().ok_or(MatrixError::Overflow)?;
            col_sub(u_inv, source, target, neg)?;
        }
        Ok(())
    }

    struct Reduction {
        a: Vec<Vec<i128>>,
        u: RowTransform,
        v: Vec<Vec<i128>>,
        rank: usize,
    }

    /// Diagonalize `m` with unimodular row and column operations
    /// (Euclidean pivoting). Afterwards `a = U·m·V` is diagonal with
    /// `a[i][i]` dividing `a[i+1][i+1]`.
    fn reduce(m: &[Vec<i64>], cols: usize, track_rows: bool) -> Result<Reduction, MatrixError> {
        check_shape(m, cols)?;
        let rows = m.len();
        let mut a: Vec<Vec<i128>> = m
            .iter()
            .map(|r| r.iter().map(|&x| x as i128).collect())
            .collect();
        let mut v = identity(cols);
        let mut u: RowTransform = track_rows.then(|| (identity(rows), identity(rows)));

        let mut t = 0;
        while t < rows.min(cols) {
            let mut best: Option<(usize, usize)> = None;
            for i in t..rows {
                for j in t..cols {
                    if a[i][j] != 0
                        && best.map_or(true, |(bi, bj)| a[i][j].abs() < a[bi][bj].abs())
                    {
                        best = Some((i, j));
                    }
                }
            }
            let Some((pi, pj)) = best else { break };
            swap_rows(&mut a, &mut u, t, pi);
            swap_cols(&mut a, t, pj);
            swap_cols(&mut v, t, pj);

            loop {
                let mut clean = true;
                for i in t + 1..rows {
                    if a[i][t] != 0 {
                        let q = a[i][t] / a[t][t];
                        sub_rows(&mut a, &mut u, i, t, q)?;
                        clean &= a[i][t] == 0;
                    }
                }
                for j in t + 1..cols {
                    if a[t][j] != 0 {
                        let q = a[t][j] / a[t][t];
                        col_sub(&mut a, j, t, q)?;
                        col_sub(&mut v, j, t, q)?;
                        clean &= a[t][j] == 0;
                    }
                }
                if !clean {
                    let mut best = (t, t);
                    for i in t + 1..rows {
                        if a[i][t] != 0 && a[i][t].abs() < a[best.0][best.1].abs() {
                            best = (i, t);
                        }
                    }
                    for j in t + 1..cols {
                        if a[t][j] != 0 && a[t][j].abs() < a[best.0][best.1].abs() {
                            best = (t, j);
                        }
                    }
                    swap_rows(&mut a, &mut u, t, best.0);
                    swap_cols(&mut a, t, best.1);
                    swap_cols(&mut v, t, best.1);
                    continue;
                }
                let pivot = a[t][t];
                let offender = (t + 1..rows).find(|&i| (t + 1..cols).any(|j| a[i][j] % pivot != 0));
                match offender {
                    Some(i) => sub_rows(&mut a, &mut u, t, i, -1)?,
                    None => break,
                }
            }
            t += 1;
        }
        Ok(Reduction { a, u, v, rank: t })
    }

    fn to_i64(m: &[Vec<i128>]) -> Result<Vec<Vec<i64>>, MatrixError> {
        m.iter()
            .map(|row| {
                row.iter()
                    .map(|&x| i64::try_from(x).map_err(|_| MatrixError::Overflow))
                    .collect()
            })
            .collect()
    }

    /// Smith normal form of `m` (`m.len() × cols`): invariant factors and a
    /// kernel basis.
    ///
    /// Column operations are mirrored on an identity matrix `V`; after
    /// diagonalization `m·V` has zero columns from the rank onward, so those
    /// columns of the unimodular `V` form a Z-basis of the kernel.
    pub fn smith_form(m: &[Vec<i64>], cols: usize) -> Result<SmithForm, MatrixError> {
        let r = reduce(m, cols, false)?;
        let invariant_factors = (0..r.rank)
            .map(|i| u64::try_from(r.a[i][i].unsigned_abs()).map_err(|_| MatrixError::Overflow))
            .collect::<Result<Vec<_>, _>>()?;
        let kernel_basis = (r.rank..cols)
            .map(|j| {
                r.v.iter()
                    .map(|row| i64::try_from(row[j]).map_err(|_| MatrixError::Overflow))
                    .collect::<Result<Vec<_>, _>>()
            })
            .collect::<Result<Vec<_>, _>>()?;
        Ok(SmithForm {
            invariant_factors,
            kernel_basis,
        })
    }

    /// Full decomposition `U·A·V = D` with unimodular `U` and `V`.
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub struct SmithDecomposition {
        /// Row transform (`rows × rows`).
        pub u: Vec<Vec<i64>>,
        /// Inverse of `u`.
        pub u_inv: Vec<Vec<i64>>,
        /// Column transform (`cols × cols`).
        pub v: Vec<Vec<i64>>,
        /// Signed diagonal entries `D[i][i]`, `i < rank` (all non-zero,
        /// each dividing the next).
        pub diagonal: Vec<i64>,
    }

    impl SmithDecomposition {
        /// Rank of `A`.
        pub fn rank(&self) -> usize {
            self.diagonal.len()
        }

        /// Invariant factors `|D[i][i]|`.
        pub fn invariant_factors(&self) -> Vec<u64> {
            self.diagonal.iter().map(|d| d.unsigned_abs()).collect()
        }
    }

    /// Compute `U·A·V = D` for `m` (`m.len() × cols`).
    pub fn smith_decomposition(m: &[Vec<i64>], cols: usize) -> Result<SmithDecomposition, MatrixError> {
        let r = reduce(m, cols, true)?;
        let (u, u_inv) = r.u.expect("row transform tracked");
        let diagonal = (0..r.rank)
            .map(|i| i64::try_from(r.a[i][i]).map_err(|_| MatrixError::Overflow))
            .collect::<Result<Vec<_>, _>>()?;
        Ok(SmithDecomposition {
            u: to_i64(&u)?,
            u_inv: to_i64(&u_inv)?,
            v: to_i64(&r.v)?,
            diagonal,
        })
    }

    /// An integer solution of `A·x = b`, or `None` if there is none over Z.
    /// When solutions exist, the one returned sets every free coordinate
    /// (in Smith coordinates) to zero.
    pub fn solve(m: &[Vec<i64>], cols: usize, b: &[i64]) -> Result<Option<Vec<i64>>, MatrixError> {
        if b.len() != m.len() {
            return Err(MatrixError::LengthMismatch {
                expected: m.len(),
                got: b.len(),
            });
        }
        let r = reduce(m, cols, true)?;
        let (u, _) = r.u.as_ref().expect("row transform tracked");
        let mut c = vec![0i128; m.len()];
        for (i, row) in u.iter().enumerate() {
            for (&x, &y) in row.iter().zip(b) {
                let term = x.checked_mul(y as i128).ok_or(MatrixError::Overflow)?;
                c[i] = c[i].checked_add(term).ok_or(MatrixError::Overflow)?;
            }
        }
        let mut y = vec![0i128; cols];
        for i in 0..r.rank {
            let d = r.a[i][i];
            if c[i] % d != 0 {
                return Ok(None);
            }
            y[i] = c[i] / d;
        }
        if c[r.rank..].iter().any(|&x| x != 0) {
            return Ok(None);
        }
        let mut x = Vec::with_capacity(cols);
        for row in &r.v {
            let mut sum = 0i128;
            for (&vij, &yj) in row.iter().zip(&y) {
                let term = vij.checked_mul(yj).ok_or(MatrixError::Overflow)?;
                sum = sum.checked_add(term).ok_or(MatrixError::Overflow)?;
            }
            x.push(i64::try_from(sum).map_err(|_| MatrixError::Overflow)?);
        }
        Ok(Some(x))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chain_degree_shape_new() {
        let shape = ChainDegreeShape::new(0, 3);
        assert_eq!(shape.degree, 0);
        assert_eq!(shape.rank, 3);
        assert_eq!(shape.len(), 3);
        assert!(!shape.is_empty());
    }

    #[test]
    fn test_chain_degree_shape_empty() {
        let shape = ChainDegreeShape::new(5, 0);
        assert!(shape.is_empty());
        assert_eq!(shape.len(), 0);
    }

    #[test]
    fn test_chain_complex_shape_add_degree() {
        let mut shape = ChainComplexShape::new();
        assert!(shape.is_empty());
        assert_eq!(shape.total_rank(), 0);

        shape.add_degree(ChainDegreeShape::new(0, 2));
        assert!(!shape.is_empty());
        assert_eq!(shape.len(), 1);
        assert_eq!(shape.rank_at(0), 2);
        assert_eq!(shape.total_rank(), 2);

        shape.add_degree(ChainDegreeShape::new(1, 3));
        assert_eq!(shape.len(), 2);
        assert_eq!(shape.rank_at(1), 3);
        assert_eq!(shape.total_rank(), 5);
        assert_eq!(shape.min_degree, 0);
        assert_eq!(shape.max_degree, 1);
    }

    #[test]
    fn test_chain_complex_shape_negative_degrees() {
        let shape = ChainComplexShape::from_ranks(vec![(-2, 1), (-1, 2), (0, 3)]);
        assert_eq!(shape.len(), 3);
        assert_eq!(shape.min_degree, -2);
        assert_eq!(shape.max_degree, 0);
        assert_eq!(shape.rank_at(-2), 1);
        assert_eq!(shape.rank_at(-1), 2);
        assert_eq!(shape.rank_at(0), 3);
        assert_eq!(shape.total_rank(), 6);
    }

    #[test]
    fn test_chain_complex_shape_free_module() {
        let shape = ChainComplexShape::free_module(5);
        assert_eq!(shape.len(), 1);
        assert_eq!(shape.rank_at(5), 1);
        assert_eq!(shape.min_degree, 5);
        assert_eq!(shape.max_degree, 5);
    }

    mod integer_matrix_tests {
        use crate::integer_matrix::*;

        fn check_kernel(m: &[Vec<i64>], cols: usize) {
            let snf = smith_form(m, cols).unwrap();
            assert_eq!(snf.kernel_basis.len(), cols - snf.rank());
            for k in &snf.kernel_basis {
                assert!(apply(m, cols, k).unwrap().iter().all(|&x| x == 0), "{k:?} not in kernel");
            }
        }

        #[test]
        fn ranks() {
            assert_eq!(rank(&[vec![1, 2, 3], vec![4, 5, 6]], 3), Ok(2));
            assert_eq!(rank(&[vec![2, 4], vec![1, 2]], 2), Ok(1));
            assert_eq!(rank(&[], 3), Ok(0));
            assert_eq!(rank(&[vec![0, 0]], 2), Ok(0));
        }

        #[test]
        fn invariant_factors_of_known_matrix() {
            let m = vec![vec![2, 4, 4], vec![-6, 6, 12], vec![10, -4, -16]];
            let snf = smith_form(&m, 3).unwrap();
            assert_eq!(snf.invariant_factors, vec![2, 6, 12]);
            assert_eq!(snf.torsion(), vec![2, 6, 12]);
            assert!(snf.kernel_basis.is_empty());
        }

        #[test]
        fn cyclic_and_unimodular() {
            let z6 = smith_form(&[vec![6]], 1).unwrap();
            assert_eq!(z6.invariant_factors, vec![6]);
            assert!(!z6.is_torsion_free());
            let unimodular = smith_form(&[vec![2, 3]], 2).unwrap();
            assert_eq!(unimodular.invariant_factors, vec![1]);
            assert!(unimodular.is_torsion_free());
            assert_eq!(smith_form(&[vec![4, 6]], 2).unwrap().invariant_factors, vec![2]);
        }

        #[test]
        fn kernel_bases_are_correct() {
            check_kernel(&[vec![1, 2, 3], vec![4, 5, 6]], 3);
            check_kernel(&[vec![2, 4], vec![1, 2]], 2);
            check_kernel(&[vec![-1, 1, 0], vec![0, -1, 1], vec![1, 0, -1]], 3);
            check_kernel(&[vec![0, 0, 0]], 3);
            check_kernel(&[], 2);
            let snf = smith_form(&[vec![6, 4]], 2).unwrap();
            assert_eq!(snf.kernel_basis.len(), 1);
            let k = &snf.kernel_basis[0];
            assert_eq!(k[0].abs(), 2);
            assert_eq!(k[1].abs(), 3);
        }

        fn identity(n: usize) -> Vec<Vec<i64>> {
            (0..n).map(|i| (0..n).map(|j| i64::from(i == j)).collect()).collect()
        }

        #[test]
        fn decomposition_satisfies_u_a_v_equals_d() {
            let cases: Vec<(Vec<Vec<i64>>, usize)> = vec![
                (vec![vec![2, 4, 4], vec![-6, 6, 12], vec![10, -4, -16]], 3),
                (vec![vec![1, 2, 3], vec![4, 5, 6]], 3),
                (vec![vec![0, 6], vec![4, 0], vec![2, 2]], 2),
                (vec![vec![0, 0]], 2),
            ];
            for (m, cols) in cases {
                let s = smith_decomposition(&m, cols).unwrap();
                let rows = m.len();
                let uav = multiply(&multiply(&s.u, rows, &m, cols).unwrap(), cols, &s.v, cols).unwrap();
                for i in 0..rows {
                    for j in 0..cols {
                        let expected = if i == j && i < s.rank() { s.diagonal[i] } else { 0 };
                        assert_eq!(uav[i][j], expected, "U·A·V ≠ D for {m:?}");
                    }
                }
                assert_eq!(multiply(&s.u, rows, &s.u_inv, rows).unwrap(), identity(rows));
                for w in s.diagonal.windows(2) {
                    assert_eq!(w[1] % w[0], 0);
                }
            }
        }

        #[test]
        fn integer_solving() {
            assert_eq!(solve(&[vec![2]], 1, &[4]), Ok(Some(vec![2])));
            assert_eq!(solve(&[vec![2]], 1, &[3]), Ok(None));
            let m = vec![vec![1, 1], vec![1, -1]];
            let x = solve(&m, 2, &[4, 2]).unwrap().unwrap();
            assert_eq!(apply(&m, 2, &x).unwrap(), vec![4, 2]);
            assert_eq!(solve(&m, 2, &[3, 0]), Ok(None));
            let under = vec![vec![2, 3]];
            let x = solve(&under, 2, &[7]).unwrap().unwrap();
            assert_eq!(apply(&under, 2, &x).unwrap(), vec![7]);
            assert_eq!(solve(&[vec![1], vec![1]], 1, &[1, 2]), Ok(None));
            assert_eq!(
                solve(&[vec![1]], 1, &[1, 2]),
                Err(MatrixError::LengthMismatch { expected: 1, got: 2 })
            );
        }

        #[test]
        fn products_and_errors() {
            let a = vec![vec![1, 2], vec![3, 4]];
            let b = vec![vec![0, 1], vec![1, 0]];
            assert_eq!(multiply(&a, 2, &b, 2), Ok(vec![vec![2, 1], vec![4, 3]]));
            assert_eq!(
                multiply(&a, 2, &[vec![1, 1, 1]], 3),
                Err(MatrixError::DimensionMismatch { left_cols: 2, right_rows: 1 })
            );
            assert_eq!(multiply(&[vec![i64::MAX]], 1, &[vec![2]], 1), Err(MatrixError::Overflow));
            assert_eq!(
                smith_form(&[vec![1, 2], vec![3]], 2),
                Err(MatrixError::Ragged { row: 1, len: 1, cols: 2 })
            );
            assert!(is_zero(&[vec![0, 0], vec![0, 0]]));
            assert!(!is_zero(&a));
        }
    }

    #[test]
    fn test_chain_degree_shape_generators() {
        let gen_names = vec!["x".to_string(), "y".to_string()];
        let shape = ChainDegreeShape::new(0, 2).with_generators(gen_names.clone());
        assert_eq!(shape.generators, gen_names);
    }
}
