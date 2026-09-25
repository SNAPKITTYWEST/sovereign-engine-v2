//! tensor_product_module
//!
//! Tensor product modules M ⊗_R N over ring R.

#![warn(missing_docs)]

use std::collections::HashMap;

/// A generator in a tensor product, represented as a formal pair (i, j)
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct TensorGenerator {
    /// Index from first module M
    pub m_index: usize,
    /// Index from second module N
    pub n_index: usize,
}

impl TensorGenerator {
    /// Create a generator m_i ⊗ n_j
    pub fn new(m_index: usize, n_index: usize) -> Self {
        Self { m_index, n_index }
    }
}

/// A module element in the tensor product as a formal sum of generators
#[derive(Clone, Debug)]
pub struct TensorElement {
    /// Coefficients indexed by generator pairs
    pub coeffs: HashMap<TensorGenerator, i32>,
}

impl TensorElement {
    /// Create the zero element
    pub fn zero() -> Self {
        Self {
            coeffs: HashMap::new(),
        }
    }

    /// Create a single generator with coefficient c
    pub fn from_generator(gen: TensorGenerator, coeff: i32) -> Self {
        let mut coeffs = HashMap::new();
        if coeff != 0 {
            coeffs.insert(gen, coeff);
        }
        Self { coeffs }
    }

    /// Add another element to this one
    pub fn add(&mut self, other: &TensorElement) {
        for (gen, coeff) in &other.coeffs {
            *self.coeffs.entry(*gen).or_insert(0) += coeff;
            if self.coeffs[gen] == 0 {
                self.coeffs.remove(gen);
            }
        }
    }

    /// Scale by a coefficient
    pub fn scale(&mut self, factor: i32) {
        for coeff in self.coeffs.values_mut() {
            *coeff *= factor;
        }
        self.coeffs.retain(|_, &mut c| c != 0);
    }

    /// Is this element zero?
    pub fn is_zero(&self) -> bool {
        self.coeffs.is_empty()
    }

    /// Number of generators in the sum (with non-zero coefficient)
    pub fn num_generators(&self) -> usize {
        self.coeffs.len()
    }
}

/// A tensor product module M ⊗_R N
#[derive(Clone, Debug)]
pub struct TensorProductModule {
    /// Rank of M
    pub m_rank: usize,
    /// Rank of N
    pub n_rank: usize,
    /// Relations that must be satisfied (bilinearity)
    pub relations: Vec<TensorElement>,
}

impl TensorProductModule {
    /// Create M ⊗_R N with given ranks
    pub fn new(m_rank: usize, n_rank: usize) -> Self {
        Self {
            m_rank,
            n_rank,
            relations: Vec::new(),
        }
    }

    /// Add a bilinearity relation
    pub fn add_relation(&mut self, rel: TensorElement) {
        if !rel.is_zero() {
            self.relations.push(rel);
        }
    }

    /// Theoretical rank without relations (free rank)
    pub fn free_rank(&self) -> usize {
        self.m_rank * self.n_rank
    }

    /// Generate all basis elements (generators)
    pub fn basis_generators(&self) -> Vec<TensorGenerator> {
        let mut gens = Vec::new();
        for i in 0..self.m_rank {
            for j in 0..self.n_rank {
                gens.push(TensorGenerator::new(i, j));
            }
        }
        gens
    }

    /// Tensor element m_i ⊗ n_j
    pub fn generator(&self, i: usize, j: usize) -> Option<TensorElement> {
        if i < self.m_rank && j < self.n_rank {
            Some(TensorElement::from_generator(TensorGenerator::new(i, j), 1))
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tensor_generator() {
        let gen = TensorGenerator::new(1, 2);
        assert_eq!(gen.m_index, 1);
        assert_eq!(gen.n_index, 2);
    }

    #[test]
    fn test_tensor_element_zero() {
        let elem = TensorElement::zero();
        assert!(elem.is_zero());
        assert_eq!(elem.num_generators(), 0);
    }

    #[test]
    fn test_tensor_element_add() {
        let gen1 = TensorGenerator::new(0, 0);
        let mut elem1 = TensorElement::from_generator(gen1, 2);

        let gen2 = TensorGenerator::new(0, 1);
        let elem2 = TensorElement::from_generator(gen2, 3);

        elem1.add(&elem2);
        assert_eq!(elem1.num_generators(), 2);
    }

    #[test]
    fn test_tensor_element_scale() {
        let gen = TensorGenerator::new(0, 0);
        let mut elem = TensorElement::from_generator(gen, 2);
        elem.scale(3);
        assert_eq!(elem.coeffs[&gen], 6);
    }

    #[test]
    fn test_tensor_product_module() {
        let module = TensorProductModule::new(2, 3);
        assert_eq!(module.free_rank(), 6);
        assert_eq!(module.basis_generators().len(), 6);
    }

    #[test]
    fn test_tensor_product_generator() {
        let module = TensorProductModule::new(2, 3);
        let elem = module.generator(0, 1).unwrap();
        assert_eq!(elem.num_generators(), 1);

        assert!(module.generator(10, 10).is_none());
    }
}
