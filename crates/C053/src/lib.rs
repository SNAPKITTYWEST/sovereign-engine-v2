//! resolution_tensored
//!
//! The tensor product of two free chain complexes, `Tot(P ⊗ Q)`.
//!
//! For complexes `P` (differentials `d^P_{k+1}: P_{k+1} → P_k`) and `Q`,
//! `Tot_n = ⊕_{a+b=n} P_a ⊗ Q_b` with differential
//! `D(x ⊗ y) = d^P x ⊗ y + (−1)^a x ⊗ d^Q y`. Within `Tot_n` blocks are
//! ordered by increasing `a`, and inside block `(a, b)` the generator
//! `p_i ⊗ q_j` has index `i · rank Q_b + j`.
//!
//! When `P` resolves `M` and `Q` resolves `N`, `H_n(Tot(P ⊗ Q)) = Tor_n(M, N)`.

#![warn(missing_docs)]

use differential_operator::{ChainComplexShape, DifferentialOperator, MAX_CHAIN_RANK};
use differential_squared_zero::SquaredZeroVerifier;
use std::collections::BTreeMap;
pub use tensor_product_module::integer_matrix;
use tensor_product_module::integer_matrix::{check_shape, smith_form, MatrixError};
pub use tensor_product_module::{TensorElement, TensorGenerator, TensorProductModule};

/// `Tot(P ⊗ Q)` with explicit differentials.
#[derive(Clone, Debug)]
pub struct TensoredComplex {
    /// Ranks of `P_i`.
    pub p_ranks: Vec<usize>,
    /// Ranks of `Q_j`.
    pub q_ranks: Vec<usize>,
    /// Rank of `Q_0` (the coefficient module when `Q` is a single free module).
    pub n_rank: usize,
    /// `differential_ranks[n]` = rank of `D_n: Tot_n → Tot_{n-1}`
    /// (`D_0 = 0`).
    pub differential_ranks: Vec<usize>,
    total_ranks: Vec<usize>,
    block_offsets: Vec<BTreeMap<usize, usize>>,
    operator: DifferentialOperator,
}

fn check_complex(name: &str, ranks: &[usize], diffs: &[Vec<Vec<i64>>]) -> Result<(), String> {
    if ranks.is_empty() {
        if diffs.is_empty() {
            return Ok(());
        }
        return Err(format!("{name}: differentials given for an empty complex"));
    }
    if diffs.len() != ranks.len() - 1 {
        return Err(format!(
            "{name}: {} modules need {} differentials, got {}",
            ranks.len(),
            ranks.len() - 1,
            diffs.len()
        ));
    }
    for (k, d) in diffs.iter().enumerate() {
        if d.len() != ranks[k] {
            return Err(format!("{name}: d_{} has {} rows, expected {}", k + 1, d.len(), ranks[k]));
        }
        check_shape(d, ranks[k + 1]).map_err(|e| format!("{name}: d_{}: {e}", k + 1))?;
    }
    Ok(())
}

impl TensoredComplex {
    /// Build `Tot(P ⊗ Q)`. `p_diffs[k]` is the matrix of `d_{k+1}: P_{k+1} →
    /// P_k` (rows `P_k`, columns `P_{k+1}`), likewise for `q_diffs`.
    pub fn from_complexes(
        p_ranks: Vec<usize>,
        p_diffs: &[Vec<Vec<i64>>],
        q_ranks: Vec<usize>,
        q_diffs: &[Vec<Vec<i64>>],
    ) -> Result<Self, String> {
        check_complex("P", &p_ranks, p_diffs)?;
        check_complex("Q", &q_ranks, q_diffs)?;
        let n_rank = q_ranks.first().copied().unwrap_or(0);
        if p_ranks.is_empty() || q_ranks.is_empty() {
            return Ok(Self {
                p_ranks,
                q_ranks,
                n_rank,
                differential_ranks: Vec::new(),
                total_ranks: Vec::new(),
                block_offsets: Vec::new(),
                operator: DifferentialOperator::new(ChainComplexShape::new()),
            });
        }

        let top = p_ranks.len() - 1 + q_ranks.len() - 1;
        // block_offsets[n][a] = start of block (a, n - a) within Tot_n.
        let mut block_offsets: Vec<BTreeMap<usize, usize>> = Vec::with_capacity(top + 1);
        let mut total_ranks = Vec::with_capacity(top + 1);
        for n in 0..=top {
            let mut offsets = BTreeMap::new();
            let mut size = 0usize;
            for (a, &pa) in p_ranks.iter().enumerate() {
                if a > n || n - a >= q_ranks.len() {
                    continue;
                }
                offsets.insert(a, size);
                size = pa
                    .checked_mul(q_ranks[n - a])
                    .and_then(|s| size.checked_add(s))
                    .ok_or("Tot rank overflows usize")?;
            }
            if size > MAX_CHAIN_RANK {
                return Err(format!("Tot_{n} has rank {size}, above the supported limit"));
            }
            block_offsets.push(offsets);
            total_ranks.push(size);
        }

        let shape = ChainComplexShape::from_ranks(
            total_ranks.iter().enumerate().map(|(n, &r)| (n as i32, r)).collect(),
        );
        let mut operator = DifferentialOperator::new(shape);
        for n in 1..=top {
            for (&a, &offset) in &block_offsets[n] {
                let b = n - a;
                let (pa, qb) = (p_ranks[a], q_ranks[b]);
                for i in 0..pa {
                    for j in 0..qb {
                        let mut image: BTreeMap<usize, i64> = BTreeMap::new();
                        if a >= 1 {
                            let target = block_offsets[n - 1][&(a - 1)];
                            for (i2, row) in p_diffs[a - 1].iter().enumerate() {
                                if row[i] != 0 {
                                    *image.entry(target + i2 * qb + j).or_insert(0) += row[i];
                                }
                            }
                        }
                        if b >= 1 {
                            let target = block_offsets[n - 1][&a];
                            let q_prev = q_ranks[b - 1];
                            let sign = if a % 2 == 0 { 1 } else { -1 };
                            for (j2, row) in q_diffs[b - 1].iter().enumerate() {
                                if row[j] != 0 {
                                    *image.entry(target + i * q_prev + j2).or_insert(0) += sign * row[j];
                                }
                            }
                        }
                        let source = offset + i * qb + j;
                        operator.set_generator_image(
                            n as i32,
                            source,
                            n as i32 - 1,
                            image.into_iter().filter(|&(_, c)| c != 0).collect(),
                        );
                    }
                }
            }
        }

        let mut complex = Self {
            p_ranks,
            q_ranks,
            n_rank,
            differential_ranks: vec![0; top + 1],
            total_ranks,
            block_offsets,
            operator,
        };
        for n in 1..=top {
            complex.differential_ranks[n] = smith_form(&complex.differential_matrix(n), complex.total_rank_at(n))
                .map_err(|e| format!("rank of D_{n}: {e}"))?
                .rank();
        }
        Ok(complex)
    }

    /// `P` with zero differentials tensored with the free module `Z^n_rank`.
    ///
    /// # Panics
    /// Panics if a total rank exceeds the chain-complex rank limit.
    pub fn new(p_ranks: Vec<usize>, n_rank: usize) -> Self {
        let zero_diffs: Vec<Vec<Vec<i64>>> = p_ranks
            .windows(2)
            .map(|w| vec![vec![0i64; w[1]]; w[0]])
            .collect();
        Self::from_complexes(p_ranks, &zero_diffs, vec![n_rank], &[])
            .expect("zero differentials always form a valid complex")
    }

    /// Rank of `P_degree ⊗ Q_0`.
    pub fn tensored_rank(&self, degree: usize) -> Option<usize> {
        self.p_ranks.get(degree).map(|&p_rank| p_rank * self.n_rank)
    }

    /// Rank of `Tot_n` (0 outside the complex).
    pub fn total_rank_at(&self, n: usize) -> usize {
        self.total_ranks.get(n).copied().unwrap_or(0)
    }

    /// Index within `Tot_n` of the first generator of block `P_a ⊗ Q_{n-a}`,
    /// if that block exists.
    pub fn block_offset(&self, n: usize, a: usize) -> Option<usize> {
        self.block_offsets.get(n).and_then(|m| m.get(&a)).copied()
    }

    /// Rank of `D_n` (0 for `n = 0` and outside the complex).
    pub fn get_differential_rank(&self, degree: usize) -> Option<usize> {
        self.differential_ranks.get(degree).copied()
    }

    /// Dense matrix of `D_n` (rows `Tot_{n-1}`, columns `Tot_n`).
    pub fn differential_matrix(&self, n: usize) -> Vec<Vec<i64>> {
        self.operator.to_dense_matrix(n as i32)
    }

    /// The total complex as a differential operator (degrees `0..`).
    pub fn operator(&self) -> &DifferentialOperator {
        &self.operator
    }

    /// Check `D ∘ D = 0` everywhere, exactly.
    pub fn verify_complex(&self) -> bool {
        SquaredZeroVerifier::verify_global(&self.operator).is_valid
    }

    /// Number of degrees of `Tot`.
    pub fn num_degrees(&self) -> usize {
        self.total_ranks.len()
    }

    /// Sum of all `Tot_n` ranks.
    pub fn total_rank(&self) -> usize {
        self.total_ranks.iter().sum()
    }
}

/// Kernel/image ranks and exactness of a tensored complex at each degree.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TensoredComplexProperties {
    /// Exact at degree n (`ker D_n = im D_{n+1}`, torsion-free quotient).
    pub exact_at: Vec<bool>,
    /// Rank of `ker D_n`.
    pub kernel_ranks: Vec<usize>,
    /// Rank of `im D_{n+1}`.
    pub image_ranks: Vec<usize>,
}

impl TensoredComplexProperties {
    /// Compute kernel and image ranks and exactness exactly.
    pub fn analyze(complex: &TensoredComplex) -> Result<Self, MatrixError> {
        let mut props = Self {
            exact_at: Vec::new(),
            kernel_ranks: Vec::new(),
            image_ranks: Vec::new(),
        };
        for n in 0..complex.num_degrees() {
            let kernel = complex.total_rank_at(n) - complex.differential_ranks[n];
            let incoming = smith_form(&complex.differential_matrix(n + 1), complex.total_rank_at(n + 1))?;
            props.kernel_ranks.push(kernel);
            props.image_ranks.push(incoming.rank());
            props.exact_at.push(kernel == incoming.rank() && incoming.is_torsion_free());
        }
        Ok(props)
    }

    /// Exact at every degree?
    pub fn is_exact(&self) -> bool {
        self.exact_at.iter().all(|&e| e)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cyclic(n: i64) -> (Vec<usize>, Vec<Vec<Vec<i64>>>) {
        (vec![1, 1], vec![vec![vec![n]]])
    }

    #[test]
    fn free_complex_with_zero_differentials() {
        let complex = TensoredComplex::new(vec![2, 3, 2], 4);
        assert_eq!(complex.tensored_rank(0), Some(8));
        assert_eq!(complex.tensored_rank(1), Some(12));
        assert_eq!(complex.total_rank(), 28);
        assert_eq!(complex.num_degrees(), 3);
        assert!(complex.verify_complex());
        assert_eq!(complex.get_differential_rank(1), Some(0));
    }

    #[test]
    fn tensor_of_two_cyclic_presentations() {
        let (pr, pd) = cyclic(4);
        let (qr, qd) = cyclic(6);
        let c = TensoredComplex::from_complexes(pr, &pd, qr, &qd).unwrap();
        assert_eq!((0..3).map(|n| c.total_rank_at(n)).collect::<Vec<_>>(), vec![1, 2, 1]);
        assert_eq!(c.differential_matrix(1), vec![vec![6, 4]]);
        assert_eq!(c.differential_matrix(2), vec![vec![4], vec![-6]]);
        assert!(c.verify_complex());
        assert_eq!(c.differential_ranks, vec![0, 1, 1]);
    }

    #[test]
    fn exactness_analysis() {
        let (pr, pd) = cyclic(1);
        let (qr, qd) = cyclic(1);
        let unit = TensoredComplex::from_complexes(pr, &pd, qr, &qd).unwrap();
        let props = TensoredComplexProperties::analyze(&unit).unwrap();
        assert!(props.is_exact(), "{props:?}");

        let (pr, pd) = cyclic(2);
        let (qr, qd) = cyclic(2);
        let z2 = TensoredComplex::from_complexes(pr, &pd, qr, &qd).unwrap();
        let props = TensoredComplexProperties::analyze(&z2).unwrap();
        assert_eq!(props.exact_at, vec![false, false, true]);
    }

    #[test]
    fn malformed_inputs_are_rejected() {
        assert!(TensoredComplex::from_complexes(vec![1, 1], &[], vec![1], &[]).is_err());
        assert!(TensoredComplex::from_complexes(vec![1, 2], &[vec![vec![1]]], vec![1], &[]).is_err());
        let empty = TensoredComplex::from_complexes(vec![], &[], vec![1], &[]).unwrap();
        assert_eq!(empty.num_degrees(), 0);
    }
}
