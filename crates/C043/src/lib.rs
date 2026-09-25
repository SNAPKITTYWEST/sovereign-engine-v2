//! differential_operator
//!
//! The differential operator d: C_n -> C_{n-1} in a chain complex.
//! The core operator of homological algebra: d² = 0 is verified separately in C044.

#![warn(missing_docs)]

pub use chain_complex_shape::{ChainComplexShape, ChainDegreeShape, MAX_CHAIN_RANK};
use chain_complex_types::{Chain, ChainElement};
use std::collections::{BTreeMap, HashMap};

/// Represents the differential operator d in a chain complex.
/// For each degree n, stores the matrix of d: C_n -> C_{n-1}.
/// The matrix is represented as: for each generator g_i in C_n,
/// d(g_i) = sum of coefficients times generators in C_{n-1}.
#[derive(Debug, Clone)]
pub struct DifferentialOperator {
    /// The shape of the chain complex this operator acts on.
    pub shape: ChainComplexShape,
    /// Maps source degree n to the differential matrix.
    /// matrix[n] = {source_gen_idx -> (target_degree, target_gen_idx, coeff)}
    matrices: HashMap<i32, HashMap<usize, Vec<(i32, usize, i64)>>>,
}

impl DifferentialOperator {
    /// Create a new differential operator for a given chain complex shape.
    pub fn new(shape: ChainComplexShape) -> Self {
        Self {
            shape,
            matrices: HashMap::new(),
        }
    }

    /// Set the image of a single generator under the differential.
    /// d(source_gen) = formal sum at target_degree. Repeated target
    /// generators are summed and zero coefficients dropped.
    ///
    /// # Arguments
    /// * `source_degree` - Degree n of source generator
    /// * `source_gen` - Index of source generator in C_n
    /// * `target_degree` - Degree n-1 of target
    /// * `target_image` - ChainElement at target_degree giving d(source_gen)
    ///
    /// # Panics
    /// Panics if source_degree != target_degree + 1 (differential must decrease
    /// degree by 1), if `source_gen` is not a generator of C_n or a target
    /// generator is not a generator of C_{n-1} in the shape, or if summing
    /// repeated coefficients overflows i64.
    pub fn set_generator_image(
        &mut self,
        source_degree: i32,
        source_gen: usize,
        target_degree: i32,
        target_image: Vec<(usize, i64)>,
    ) {
        assert_eq!(
            source_degree - 1,
            target_degree,
            "differential must decrease degree by exactly 1"
        );
        let source_rank = self.source_rank(source_degree);
        assert!(
            source_gen < source_rank,
            "source generator {source_gen} out of range: C_{source_degree} has rank {source_rank}"
        );
        let target_rank = self.target_rank(source_degree);

        let mut merged: BTreeMap<usize, i64> = BTreeMap::new();
        for (target_gen, coeff) in target_image {
            assert!(
                target_gen < target_rank,
                "target generator {target_gen} out of range: C_{target_degree} has rank {target_rank}"
            );
            let sum = merged.entry(target_gen).or_insert(0);
            *sum = sum.checked_add(coeff).expect("differential coefficient overflow");
        }
        let image = merged
            .into_iter()
            .filter(|&(_, coeff)| coeff != 0)
            .map(|(target_gen, coeff)| (target_degree, target_gen, coeff))
            .collect();
        self.matrices
            .entry(source_degree)
            .or_insert_with(HashMap::new)
            .insert(source_gen, image);
    }

    /// Apply the differential to a single generator.
    /// Returns d(g) as a ChainElement at degree n-1.
    pub fn apply_to_generator(&self, degree: i32, gen_idx: usize) -> ChainElement {
        let target_degree = degree - 1;
        let mut result = ChainElement::new(target_degree);

        if let Some(matrix) = self.matrices.get(&degree) {
            if let Some(image) = matrix.get(&gen_idx) {
                for &(_tgt_deg, tgt_gen, coeff) in image {
                    result.set_coeff(tgt_gen, coeff);
                }
            }
        }

        result
    }

    /// Apply the differential to a chain element.
    ///
    /// # Panics
    /// Panics if a coefficient of the result overflows i64.
    pub fn apply_to_element(&self, elem: &ChainElement) -> ChainElement {
        let target_degree = elem.degree - 1;
        let mut result = ChainElement::new(target_degree);

        for &gen_idx in &elem.support() {
            let coeff = elem.coeff(gen_idx);
            let gen_image = self.apply_to_generator(elem.degree, gen_idx);

            for &tgt_gen in &gen_image.support() {
                let tgt_coeff = gen_image.coeff(tgt_gen);
                let term = coeff.checked_mul(tgt_coeff).expect("differential coefficient overflow");
                result.add_coeff(tgt_gen, term);
            }
        }

        result
    }

    /// Apply the differential to a general chain.
    pub fn apply(&self, chain: &Chain) -> Chain {
        let mut result = Chain::new();
        for degree in chain.support_degrees() {
            if let Some(elem) = chain.element_at(degree) {
                let image = self.apply_to_element(elem);
                result.add_element(image);
            }
        }
        result
    }

    /// Get the matrix of the differential at a specific degree.
    /// Returns pairs (source_gen, target_elements).
    pub fn matrix_at(&self, degree: i32) -> Option<&HashMap<usize, Vec<(i32, usize, i64)>>> {
        self.matrices.get(&degree)
    }

    /// Get the rank of the source module C_n.
    pub fn source_rank(&self, degree: i32) -> usize {
        self.shape.rank_at(degree)
    }

    /// Get the rank of the target module C_{n-1}.
    pub fn target_rank(&self, degree: i32) -> usize {
        self.shape.rank_at(degree - 1)
    }

    /// Check that the differential is "locally" consistent with the current
    /// shape: every image lies at degree n-1 and every source and target
    /// generator index is below the rank of its degree. Images are validated
    /// when set, so this fails only if the public `shape` was replaced
    /// afterwards. This is a necessary but not sufficient check; d² = 0 is
    /// verified separately.
    pub fn is_consistent(&self) -> bool {
        self.matrices.iter().all(|(&degree, matrix)| {
            let (source_rank, target_rank) = (self.source_rank(degree), self.target_rank(degree));
            matrix.iter().all(|(&source_gen, image)| {
                source_gen < source_rank
                    && image
                        .iter()
                        .all(|&(tgt_deg, tgt_gen, _)| tgt_deg == degree - 1 && tgt_gen < target_rank)
            })
        })
    }

    /// Compute the matrix representation as nested vectors.
    /// Returns a 2D matrix where matrix[i][j] = coefficient of generator i in d(generator j).
    ///
    /// # Panics
    /// Panics if a stored entry lies outside the current shape (the public
    /// `shape` was replaced after images were set) rather than dropping it.
    pub fn to_dense_matrix(&self, degree: i32) -> Vec<Vec<i64>> {
        let source_rank = self.source_rank(degree);
        let target_rank = self.target_rank(degree);

        let mut matrix = vec![vec![0i64; source_rank]; target_rank];

        if let Some(mat) = self.matrix_at(degree) {
            for (&source_gen, image) in mat {
                for &(_tgt_deg, target_gen, coeff) in image {
                    assert!(
                        source_gen < source_rank && target_gen < target_rank,
                        "entry ({target_gen}, {source_gen}) of d_{degree} lies outside the {target_rank}x{source_rank} shape"
                    );
                    matrix[target_gen][source_gen] = coeff;
                }
            }
        }

        matrix
    }

    /// Get all degrees where the differential is nontrivial (has nonzero matrix).
    pub fn support_degrees(&self) -> Vec<i32> {
        let mut degrees: Vec<_> = self.matrices.keys().copied().collect();
        degrees.sort_unstable();
        degrees
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_differential_new() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 3)]);
        let diff = DifferentialOperator::new(shape);
        assert_eq!(diff.source_rank(1), 3);
        assert_eq!(diff.target_rank(1), 2);
    }

    #[test]
    fn test_set_generator_image() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 3)]);
        let mut diff = DifferentialOperator::new(shape);

        // d(gen_0 at degree 1) = 2 * gen_0 + 3 * gen_1 at degree 0
        diff.set_generator_image(1, 0, 0, vec![(0, 2), (1, 3)]);

        let image = diff.apply_to_generator(1, 0);
        assert_eq!(image.degree, 0);
        assert_eq!(image.coeff(0), 2);
        assert_eq!(image.coeff(1), 3);
    }

    #[test]
    fn test_apply_to_element() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 2)]);
        let mut diff = DifferentialOperator::new(shape);

        // d(gen_0) = gen_0 at degree 0
        diff.set_generator_image(1, 0, 0, vec![(0, 1)]);
        // d(gen_1) = gen_1 at degree 0
        diff.set_generator_image(1, 1, 0, vec![(1, 1)]);

        // Element: 2 * gen_0 + 3 * gen_1 at degree 1
        let mut elem = ChainElement::new(1);
        elem.set_coeff(0, 2);
        elem.set_coeff(1, 3);

        let image = diff.apply_to_element(&elem);
        assert_eq!(image.degree, 0);
        assert_eq!(image.coeff(0), 2); // 2 * d(gen_0)
        assert_eq!(image.coeff(1), 3); // 3 * d(gen_1)
    }

    #[test]
    fn test_consistency_check() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 2)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![(0, 1)]);
        assert!(diff.is_consistent());
    }

    #[test]
    fn test_dense_matrix() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 2)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![(0, 1)]);
        diff.set_generator_image(1, 1, 0, vec![(1, 2)]);

        let matrix = diff.to_dense_matrix(1);
        assert_eq!(matrix.len(), 2); // 2 target generators
        assert_eq!(matrix[0].len(), 2); // 2 source generators
        assert_eq!(matrix[0][0], 1); // d(gen_0) has gen_0 with coeff 1
        assert_eq!(matrix[1][1], 2); // d(gen_1) has gen_1 with coeff 2
    }

    #[test]
    fn repeated_targets_are_summed() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 1)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![(0, 2), (1, 5), (0, 3), (1, -5)]);
        assert_eq!(diff.to_dense_matrix(1), vec![vec![5], vec![0]]);
        assert_eq!(diff.apply_to_generator(1, 0).sorted_coefficients(), vec![(0, 5)]);
    }

    #[test]
    #[should_panic(expected = "target generator 2 out of range")]
    fn out_of_range_target_is_rejected() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 1)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![(2, 1)]);
    }

    #[test]
    #[should_panic(expected = "source generator 1 out of range")]
    fn out_of_range_source_is_rejected() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 1)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 1, 0, vec![(0, 1)]);
    }

    #[test]
    fn consistency_tracks_the_current_shape() {
        let shape = ChainComplexShape::from_ranks(vec![(0, 2), (1, 1)]);
        let mut diff = DifferentialOperator::new(shape);
        diff.set_generator_image(1, 0, 0, vec![(1, 1)]);
        assert!(diff.is_consistent());
        diff.shape = ChainComplexShape::from_ranks(vec![(0, 1), (1, 1)]);
        assert!(!diff.is_consistent());
    }
}
