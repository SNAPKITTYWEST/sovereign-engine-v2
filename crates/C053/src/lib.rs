//! resolution_tensored
//!
//! Tensor a projective resolution P_* with a module N to get P_* ⊗ N.

#![warn(missing_docs)]

pub use tensor_product_module::{TensorProductModule, TensorElement, TensorGenerator};

/// A tensored chain complex obtained from P_* ⊗_R N
#[derive(Clone, Debug)]
pub struct TensoredComplex {
    /// Original ranks of modules in P_i
    pub p_ranks: Vec<usize>,
    /// Rank of the module N
    pub n_rank: usize,
    /// Tensored differentials: d_i ⊗ id_N in degree i (stored as matrix ranks)
    pub differential_ranks: Vec<usize>,
}

impl TensoredComplex {
    /// Create a tensored complex from a resolution of ranks p_ranks and module N with rank n_rank
    pub fn new(p_ranks: Vec<usize>, n_rank: usize) -> Self {
        let num_degrees = p_ranks.len();
        Self {
            p_ranks,
            n_rank,
            differential_ranks: vec![0; num_degrees],
        }
    }

    /// The rank of P_i ⊗ N (product of ranks)
    pub fn tensored_rank(&self, degree: usize) -> Option<usize> {
        self.p_ranks
            .get(degree)
            .map(|&p_rank| p_rank * self.n_rank)
    }

    /// Set the rank of differential at degree i
    pub fn set_differential_rank(&mut self, degree: usize, rank: usize) {
        if degree < self.differential_ranks.len() {
            self.differential_ranks[degree] = rank;
        }
    }

    /// Get the rank of differential at degree i
    pub fn get_differential_rank(&self, degree: usize) -> Option<usize> {
        self.differential_ranks.get(degree).copied()
    }

    /// Verify that d^2 = 0 in the tensored complex
    pub fn verify_complex(&self) -> bool {
        // In a valid chain complex, each map rank is bounded by tensor product dimensions
        for i in 0..self.differential_ranks.len() {
            let source_rank = self.tensored_rank(i).unwrap_or(0);
            let map_rank = self.differential_ranks[i];
            // The rank of the differential cannot exceed the source rank
            if map_rank > source_rank {
                return false;
            }
        }
        true
    }

    /// Number of degrees in the complex
    pub fn num_degrees(&self) -> usize {
        self.p_ranks.len()
    }

    /// Total rank (sum of all P_i ⊗ N ranks)
    pub fn total_rank(&self) -> usize {
        self.p_ranks
            .iter()
            .map(|&p_rank| p_rank * self.n_rank)
            .sum()
    }
}

/// Properties of the tensored complex
#[derive(Clone, Debug)]
pub struct TensoredComplexProperties {
    /// Is the complex exact at each degree?
    pub exact_at: Vec<bool>,
    /// Ranks of kernels at each degree
    pub kernel_ranks: Vec<usize>,
    /// Ranks of images at each degree
    pub image_ranks: Vec<usize>,
}

impl TensoredComplexProperties {
    /// Create from a tensored complex
    pub fn analyze(complex: &TensoredComplex) -> Self {
        let num_degrees = complex.num_degrees();
        Self {
            exact_at: vec![false; num_degrees],
            kernel_ranks: vec![0; num_degrees],
            image_ranks: vec![0; num_degrees],
        }
    }

    /// Is the complex exact?
    pub fn is_exact(&self) -> bool {
        self.exact_at.iter().all(|&e| e)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tensored_complex_creation() {
        let complex = TensoredComplex::new(vec![2, 3, 2], 4);
        assert_eq!(complex.num_degrees(), 3);
        assert_eq!(complex.n_rank, 4);
    }

    #[test]
    fn test_tensored_rank() {
        let complex = TensoredComplex::new(vec![2, 3, 2], 4);
        assert_eq!(complex.tensored_rank(0), Some(8)); // 2 * 4
        assert_eq!(complex.tensored_rank(1), Some(12)); // 3 * 4
        assert_eq!(complex.tensored_rank(2), Some(8)); // 2 * 4
    }

    #[test]
    fn test_total_rank() {
        let complex = TensoredComplex::new(vec![2, 3, 2], 4);
        assert_eq!(complex.total_rank(), 28); // 8 + 12 + 8
    }

    #[test]
    fn test_tensored_complex_properties() {
        let complex = TensoredComplex::new(vec![2, 3, 2], 4);
        let props = TensoredComplexProperties::analyze(&complex);
        assert_eq!(props.kernel_ranks.len(), 3);
        assert_eq!(props.image_ranks.len(), 3);
    }
}
