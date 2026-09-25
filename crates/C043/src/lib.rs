//! differential_operator
//!
//! The differential operator d: C_n -> C_{n-1} in a chain complex.
//! The core operator of homological algebra: d² = 0 is verified separately in C044.

#![warn(missing_docs)]

use chain_complex_shape::ChainComplexShape;
use chain_complex_types::{Chain, ChainElement};
use std::collections::HashMap;

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
    /// d(source_gen) = formal sum at target_degree.
    ///
    /// # Arguments
    /// * `source_degree` - Degree n of source generator
    /// * `source_gen` - Index of source generator in C_n
    /// * `target_degree` - Degree n-1 of target
    /// * `target_image` - ChainElement at target_degree giving d(source_gen)
    ///
    /// # Panics
    /// Panics if source_degree != target_degree + 1 (differential must decrease degree by 1).
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

        let matrix = self
            .matrices
            .entry(source_degree)
            .or_insert_with(HashMap::new);

        let mut image = Vec::new();
        for (target_gen, coeff) in target_image {
            if coeff != 0 {
                image.push((target_degree, target_gen, coeff));
            }
        }
        matrix.insert(source_gen, image);
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
    pub fn apply_to_element(&self, elem: &ChainElement) -> ChainElement {
        let target_degree = elem.degree - 1;
        let mut result = ChainElement::new(target_degree);

        for &gen_idx in &elem.support() {
            let coeff = elem.coeff(gen_idx);
            let gen_image = self.apply_to_generator(elem.degree, gen_idx);

            for &tgt_gen in &gen_image.support() {
                let tgt_coeff = gen_image.coeff(tgt_gen);
                result.add_coeff(tgt_gen, coeff * tgt_coeff);
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

    /// Check if the differential is "locally" consistent (all generator images are at correct degree).
    /// This is a necessary but not sufficient check; d² = 0 is verified separately.
    pub fn is_consistent(&self) -> bool {
        for (&degree, matrix) in &self.matrices {
            let target_degree = degree - 1;
            for (_source_gen, image) in matrix {
                for &(tgt_deg, _tgt_gen, _coeff) in image {
                    if tgt_deg != target_degree {
                        return false;
                    }
                }
            }
        }
        true
    }

    /// Compute the matrix representation as nested vectors.
    /// Returns a 2D matrix where matrix[i][j] = coefficient of generator i in d(generator j).
    pub fn to_dense_matrix(&self, degree: i32) -> Vec<Vec<i64>> {
        let source_rank = self.source_rank(degree);
        let target_rank = self.target_rank(degree);

        let mut matrix = vec![vec![0i64; source_rank]; target_rank];

        if let Some(mat) = self.matrix_at(degree) {
            for (&source_gen, image) in mat {
                for &(_tgt_deg, target_gen, coeff) in image {
                    if target_gen < target_rank {
                        matrix[target_gen][source_gen] = coeff;
                    }
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
}
