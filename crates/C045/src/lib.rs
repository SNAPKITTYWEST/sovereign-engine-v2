//! projective_module_definition
//!
//! Projective modules over principal ideal domains and free modules.
//! A projective module P is one that has the "lifting property": if M -> N is surjective
//! and f: P -> N, then there exists g: P -> M with f = (M -> N) ∘ g.
//!
//! Over a PID, projective modules are precisely the free modules.

#![warn(missing_docs)]

use chain_complex_shape::integer_matrix::{self, MatrixError, SmithForm};
use chain_complex_types::ChainElement;

/// A projective module P, represented as a free module (since we work over a PID).
/// Rank is the number of free generators.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProjectiveModule {
    /// The rank (number of generators).
    pub rank: usize,
    /// Degree/grading of this module (for use in chain complexes).
    pub degree: i32,
    /// Generator names.
    generators: Vec<String>,
}

impl ProjectiveModule {
    /// Create a new projective module of given rank at given degree.
    pub fn new(rank: usize, degree: i32) -> Self {
        let generators = (0..rank).map(|i| format!("p_{}", i)).collect();
        Self {
            rank,
            degree,
            generators,
        }
    }

    /// Create a projective module with custom generator names.
    pub fn with_generators(rank: usize, degree: i32, generators: Vec<String>) -> Self {
        assert_eq!(generators.len(), rank, "generator count mismatch");
        Self {
            rank,
            degree,
            generators,
        }
    }

    /// Get the name of a generator.
    pub fn generator_name(&self, idx: usize) -> Option<&str> {
        self.generators.get(idx).map(|s| s.as_str())
    }

    /// Check if this module is free (always true for projective modules over PID).
    pub fn is_free(&self) -> bool {
        true
    }

    /// Get the rank of this module.
    pub fn len(&self) -> usize {
        self.rank
    }

    /// Check if this module is trivial (rank 0).
    pub fn is_empty(&self) -> bool {
        self.rank == 0
    }
}

/// A homomorphism φ: P -> Q between projective modules.
/// Represented as an integer matrix.
#[derive(Debug, Clone)]
pub struct ProjectiveModuleHomomorphism {
    /// Source module.
    pub source: ProjectiveModule,
    /// Target module.
    pub target: ProjectiveModule,
    /// Matrix representation: target_rank × source_rank
    /// where entry [i][j] is the coefficient of target generator i in φ(source generator j).
    matrix: Vec<Vec<i64>>,
}

impl ProjectiveModuleHomomorphism {
    /// Create a new homomorphism from a matrix.
    ///
    /// # Panics
    /// Panics if matrix dimensions don't match module ranks.
    pub fn new(
        source: ProjectiveModule,
        target: ProjectiveModule,
        matrix: Vec<Vec<i64>>,
    ) -> Self {
        assert_eq!(matrix.len(), target.rank, "matrix rows must equal target rank");
        assert!(
            matrix.iter().all(|row| row.len() == source.rank),
            "matrix columns must equal source rank"
        );
        Self {
            source,
            target,
            matrix,
        }
    }

    /// Get the matrix entry at (i, j).
    pub fn entry(&self, i: usize, j: usize) -> i64 {
        if i < self.matrix.len() && j < self.matrix[0].len() {
            self.matrix[i][j]
        } else {
            0
        }
    }

    /// Apply the homomorphism to an element.
    /// Expects the element to have degree equal to source.degree and generators indexed < source.rank.
    pub fn apply(&self, elem: &ChainElement) -> ChainElement {
        let mut result = ChainElement::new(self.target.degree);

        for &source_gen in &elem.support() {
            let coeff = elem.coeff(source_gen);

            // For each source generator, add its image contribution
            for (target_gen, matrix_entry) in self.matrix.iter().enumerate() {
                if source_gen < matrix_entry.len() {
                    let target_coeff = matrix_entry[source_gen];
                    result.add_coeff(target_gen, coeff * target_coeff);
                }
            }
        }

        result
    }

    /// Compose this homomorphism with another (self: P -> Q, other: Q -> R).
    /// Returns the composition other ∘ self: P -> R.
    ///
    /// # Panics
    /// Panics if target of self doesn't match source of other.
    pub fn compose(&self, other: &ProjectiveModuleHomomorphism) -> ProjectiveModuleHomomorphism {
        assert_eq!(
            self.target.rank, other.source.rank,
            "target of first must equal source of second"
        );
        assert_eq!(
            self.target.degree, other.source.degree,
            "target degree of first must equal source degree of second"
        );

        let mut result_matrix = vec![vec![0i64; self.source.rank]; other.target.rank];

        for i in 0..other.target.rank {
            for j in 0..self.source.rank {
                let mut sum = 0i64;
                for k in 0..self.target.rank {
                    sum += other.matrix[i][k] * self.matrix[k][j];
                }
                result_matrix[i][j] = sum;
            }
        }

        ProjectiveModuleHomomorphism::new(self.source.clone(), other.target.clone(), result_matrix)
    }

    /// Check if this is the zero homomorphism.
    pub fn is_zero(&self) -> bool {
        self.matrix.iter().all(|row| row.iter().all(|&x| x == 0))
    }

    /// Check if this is the identity homomorphism.
    ///
    /// # Panics
    /// Panics if source and target ranks don't match.
    pub fn is_identity(&self) -> bool {
        assert_eq!(self.source.rank, self.target.rank);
        for i in 0..self.source.rank {
            for j in 0..self.source.rank {
                let expected = if i == j { 1 } else { 0 };
                if self.matrix[i][j] != expected {
                    return false;
                }
            }
        }
        true
    }

    /// The matrix (target_rank rows × source_rank columns).
    pub fn matrix(&self) -> &[Vec<i64>] {
        &self.matrix
    }

    /// Smith normal form of the matrix: rank, invariant factors (torsion of
    /// the cokernel) and a Z-basis of the kernel.
    pub fn smith_form(&self) -> Result<SmithForm, MatrixError> {
        integer_matrix::smith_form(&self.matrix, self.source.rank)
    }

    /// Rank of the matrix, or an error if exact arithmetic overflows.
    pub fn try_rank(&self) -> Result<usize, MatrixError> {
        Ok(self.smith_form()?.rank())
    }

    /// Rank of the matrix.
    ///
    /// # Panics
    /// Panics if exact rank computation overflows 128-bit arithmetic; use
    /// [`Self::try_rank`] to handle that case.
    pub fn rank(&self) -> usize {
        self.try_rank()
            .expect("rank computation overflowed; use try_rank to handle this")
    }
}

/// A free resolution of a projective module is a chain complex
/// of projective modules and their homomorphisms.
#[derive(Debug, Clone)]
pub struct FreeResolution {
    /// Sequence of projective modules P_i.
    modules: Vec<ProjectiveModule>,
    /// Differentials d_i: P_i -> P_{i-1}.
    differentials: Vec<ProjectiveModuleHomomorphism>,
}

impl FreeResolution {
    /// Create a new free resolution.
    pub fn new() -> Self {
        Self {
            modules: Vec::new(),
            differentials: Vec::new(),
        }
    }

    /// Add a module to the resolution.
    pub fn add_module(&mut self, module: ProjectiveModule) {
        self.modules.push(module);
    }

    /// Add a differential between the last two modules.
    ///
    /// # Panics
    /// Panics if there are fewer than 2 modules.
    pub fn add_differential(&mut self, hom: ProjectiveModuleHomomorphism) {
        assert!(
            self.modules.len() >= 2,
            "need at least 2 modules to add a differential"
        );
        self.differentials.push(hom);
    }

    /// Get the module at index i.
    pub fn module_at(&self, i: usize) -> Option<&ProjectiveModule> {
        self.modules.get(i)
    }

    /// Get the differential d_i: P_i -> P_{i-1}.
    pub fn differential_at(&self, i: usize) -> Option<&ProjectiveModuleHomomorphism> {
        self.differentials.get(i)
    }

    /// Number of modules in the resolution.
    pub fn len(&self) -> usize {
        self.modules.len()
    }

    /// Check if empty.
    pub fn is_empty(&self) -> bool {
        self.modules.is_empty()
    }
}

impl Default for FreeResolution {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_projective_module_new() {
        let p = ProjectiveModule::new(3, 0);
        assert_eq!(p.rank, 3);
        assert_eq!(p.degree, 0);
        assert!(p.is_free());
        assert_eq!(p.len(), 3);
    }

    #[test]
    fn test_projective_module_empty() {
        let p = ProjectiveModule::new(0, 5);
        assert!(p.is_empty());
    }

    #[test]
    fn test_homomorphism_apply() {
        let p = ProjectiveModule::new(2, 0);
        let q = ProjectiveModule::new(2, 0);
        let matrix = vec![vec![1, 2], vec![3, 4]];
        let hom = ProjectiveModuleHomomorphism::new(p, q, matrix);

        let mut elem = ChainElement::new(0);
        elem.set_coeff(0, 5);
        let image = hom.apply(&elem);
        assert_eq!(image.coeff(0), 5); // 5 * 1
        assert_eq!(image.coeff(1), 15); // 5 * 3
    }

    #[test]
    fn test_homomorphism_compose() {
        let p = ProjectiveModule::new(2, 0);
        let q = ProjectiveModule::new(2, 0);
        let r = ProjectiveModule::new(2, 0);

        let hom1 = ProjectiveModuleHomomorphism::new(p.clone(), q.clone(), vec![vec![1, 0], vec![0, 1]]);
        let hom2 = ProjectiveModuleHomomorphism::new(q.clone(), r.clone(), vec![vec![2, 0], vec![0, 3]]);

        let composed = hom1.compose(&hom2);
        assert_eq!(composed.entry(0, 0), 2);
        assert_eq!(composed.entry(1, 1), 3);
    }

    #[test]
    fn test_homomorphism_rank() {
        let p = ProjectiveModule::new(2, 0);
        let q = ProjectiveModule::new(2, 0);
        let matrix = vec![vec![1, 0], vec![0, 1]];
        let hom = ProjectiveModuleHomomorphism::new(p, q, matrix);
        assert_eq!(hom.rank(), 2);
    }

    #[test]
    fn rank_handles_dependent_rows_and_large_entries() {
        let p = ProjectiveModule::new(3, 0);
        let q = ProjectiveModule::new(2, 0);
        let dependent = ProjectiveModuleHomomorphism::new(p.clone(), q.clone(), vec![vec![1, 2, 3], vec![2, 4, 6]]);
        assert_eq!(dependent.rank(), 1);
        let big = i64::MAX / 2;
        let large = ProjectiveModuleHomomorphism::new(p, q, vec![vec![big, big - 1, 1], vec![big - 1, big - 2, 1]]);
        assert_eq!(large.try_rank(), Ok(2));
    }

    #[test]
    fn smith_form_of_homomorphism() {
        let p = ProjectiveModule::new(1, 1);
        let q = ProjectiveModule::new(1, 0);
        let times_six = ProjectiveModuleHomomorphism::new(p, q, vec![vec![6]]);
        assert_eq!(times_six.smith_form().unwrap().torsion(), vec![6]);
    }

    #[test]
    fn test_free_resolution_new() {
        let res = FreeResolution::new();
        assert!(res.is_empty());
    }

    #[test]
    fn test_free_resolution_add_module() {
        let mut res = FreeResolution::new();
        let p = ProjectiveModule::new(3, 0);
        res.add_module(p);
        assert_eq!(res.len(), 1);
    }
}
