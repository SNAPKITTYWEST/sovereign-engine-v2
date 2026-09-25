//! chain_complex_types
//!
//! Chain element types and operations. Defines elements of chain complexes
//! as formal sums of generators with integer coefficients.

#![warn(missing_docs)]

use std::collections::HashMap;

/// A single chain element at a fixed degree n.
/// Represented as a sparse formal sum: Σ c_i * g_i where g_i are generators
/// and c_i are integer coefficients.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChainElement {
    /// The degree n of this chain element.
    pub degree: i32,
    /// Sparse representation: generator index -> coefficient.
    /// Only nonzero coefficients are stored.
    coefficients: HashMap<usize, i64>,
}

impl ChainElement {
    /// Create a new zero chain element at degree n.
    pub fn new(degree: i32) -> Self {
        Self {
            degree,
            coefficients: HashMap::new(),
        }
    }

    /// Create a chain element with a single generator.
    /// Equivalent to `c * gen_idx` where gen_idx is the generator index.
    pub fn from_generator(degree: i32, gen_idx: usize, coeff: i64) -> Self {
        let mut elem = Self::new(degree);
        if coeff != 0 {
            elem.coefficients.insert(gen_idx, coeff);
        }
        elem
    }

    /// Get the coefficient of a generator.
    pub fn coeff(&self, gen_idx: usize) -> i64 {
        *self.coefficients.get(&gen_idx).unwrap_or(&0)
    }

    /// Set the coefficient of a generator.
    /// Setting to 0 removes the generator.
    pub fn set_coeff(&mut self, gen_idx: usize, coeff: i64) {
        if coeff == 0 {
            self.coefficients.remove(&gen_idx);
        } else {
            self.coefficients.insert(gen_idx, coeff);
        }
    }

    /// Add a coefficient to an existing generator.
    pub fn add_coeff(&mut self, gen_idx: usize, delta: i64) {
        let new_coeff = self.coeff(gen_idx) + delta;
        self.set_coeff(gen_idx, new_coeff);
    }

    /// Check if this is the zero element.
    pub fn is_zero(&self) -> bool {
        self.coefficients.is_empty()
    }

    /// Number of nonzero generators in this element.
    pub fn support_size(&self) -> usize {
        self.coefficients.len()
    }

    /// Get all generator indices with nonzero coefficients.
    pub fn support(&self) -> Vec<usize> {
        let mut indices: Vec<_> = self.coefficients.keys().copied().collect();
        indices.sort_unstable();
        indices
    }

    /// Add two chain elements (must be at the same degree).
    ///
    /// # Panics
    /// Panics if the degrees don't match.
    pub fn add(&mut self, other: &ChainElement) {
        assert_eq!(self.degree, other.degree, "cannot add elements at different degrees");
        for (&gen_idx, &coeff) in &other.coefficients {
            self.add_coeff(gen_idx, coeff);
        }
    }

    /// Scalar multiply this chain element by c.
    pub fn scalar_mul(&mut self, c: i64) {
        if c == 0 {
            self.coefficients.clear();
        } else {
            for coeff in self.coefficients.values_mut() {
                *coeff *= c;
            }
        }
    }

    /// Return the negation of this chain element.
    pub fn neg(&self) -> Self {
        let mut result = self.clone();
        result.scalar_mul(-1);
        result
    }

    /// Compute the sum of two chain elements (immutable version).
    pub fn plus(mut a: ChainElement, b: &ChainElement) -> ChainElement {
        a.add(b);
        a
    }

    /// Get all coefficients in sorted order by generator index.
    pub fn sorted_coefficients(&self) -> Vec<(usize, i64)> {
        let mut pairs: Vec<_> = self.coefficients.iter().map(|(&g, &c)| (g, c)).collect();
        pairs.sort_by_key(|(g, _)| *g);
        pairs
    }

    /// Compute the GCD of all coefficients (for normalization).
    pub fn coeff_gcd(&self) -> i64 {
        if self.coefficients.is_empty() {
            return 1;
        }
        let mut gcd_val = 0i64;
        for &coeff in self.coefficients.values() {
            gcd_val = gcd(gcd_val, coeff.abs());
        }
        if gcd_val == 0 { 1 } else { gcd_val }
    }

    /// Normalize this element by dividing all coefficients by their GCD.
    pub fn normalize(&mut self) {
        let g = self.coeff_gcd();
        if g > 1 {
            for coeff in self.coefficients.values_mut() {
                *coeff /= g;
            }
        }
    }
}

/// Compute GCD of two integers.
fn gcd(mut a: i64, mut b: i64) -> i64 {
    a = a.abs();
    b = b.abs();
    while b != 0 {
        let temp = b;
        b = a % b;
        a = temp;
    }
    a
}

/// A general chain (possibly with generators at multiple degrees).
/// This is a formal sum of chain elements.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Chain {
    /// Elements at each degree: degree -> ChainElement
    elements: HashMap<i32, ChainElement>,
}

impl Chain {
    /// Create a new empty chain.
    pub fn new() -> Self {
        Self {
            elements: HashMap::new(),
        }
    }

    /// Add a chain element at its degree.
    pub fn add_element(&mut self, elem: ChainElement) {
        if elem.is_zero() {
            return;
        }
        self.elements
            .entry(elem.degree)
            .or_insert_with(|| ChainElement::new(elem.degree))
            .add(&elem);
    }

    /// Get the chain element at a specific degree.
    pub fn element_at(&self, degree: i32) -> Option<&ChainElement> {
        self.elements.get(&degree)
    }

    /// Get all degrees with nonzero elements.
    pub fn support_degrees(&self) -> Vec<i32> {
        let mut degrees: Vec<_> = self.elements.keys().copied().collect();
        degrees.sort_unstable();
        degrees
    }

    /// Check if this chain is zero.
    pub fn is_zero(&self) -> bool {
        self.elements.is_empty()
    }

    /// Number of nonzero degrees.
    pub fn support_size(&self) -> usize {
        self.elements.len()
    }

    /// Scalar multiply the entire chain.
    pub fn scalar_mul(&mut self, c: i64) {
        if c == 0 {
            self.elements.clear();
        } else {
            for elem in self.elements.values_mut() {
                elem.scalar_mul(c);
            }
        }
    }

    /// Add another chain to this one.
    pub fn add(&mut self, other: &Chain) {
        for elem in other.elements.values() {
            self.add_element(elem.clone());
        }
    }

    /// Return the negation of this chain.
    pub fn neg(&self) -> Self {
        let mut result = self.clone();
        result.scalar_mul(-1);
        result
    }
}

impl Default for Chain {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chain_element_new() {
        let elem = ChainElement::new(0);
        assert_eq!(elem.degree, 0);
        assert!(elem.is_zero());
        assert_eq!(elem.support_size(), 0);
    }

    #[test]
    fn test_chain_element_from_generator() {
        let elem = ChainElement::from_generator(1, 2, 5);
        assert_eq!(elem.degree, 1);
        assert!(!elem.is_zero());
        assert_eq!(elem.coeff(2), 5);
        assert_eq!(elem.coeff(0), 0);
    }

    #[test]
    fn test_chain_element_coeff_operations() {
        let mut elem = ChainElement::new(0);
        elem.set_coeff(0, 3);
        elem.set_coeff(1, 2);
        assert_eq!(elem.coeff(0), 3);
        assert_eq!(elem.coeff(1), 2);

        elem.add_coeff(0, 1);
        assert_eq!(elem.coeff(0), 4);

        elem.set_coeff(1, 0);
        assert_eq!(elem.support_size(), 1);
    }

    #[test]
    fn test_chain_element_add() {
        let mut e1 = ChainElement::from_generator(0, 0, 2);
        let e2 = ChainElement::from_generator(0, 1, 3);
        e1.add(&e2);
        assert_eq!(e1.coeff(0), 2);
        assert_eq!(e1.coeff(1), 3);
        assert_eq!(e1.support_size(), 2);
    }

    #[test]
    fn test_chain_element_scalar_mul() {
        let mut elem = ChainElement::from_generator(0, 0, 5);
        elem.add_coeff(1, 3);
        elem.scalar_mul(2);
        assert_eq!(elem.coeff(0), 10);
        assert_eq!(elem.coeff(1), 6);
    }

    #[test]
    fn test_chain_element_neg() {
        let elem = ChainElement::from_generator(0, 0, 5);
        let neg_elem = elem.neg();
        assert_eq!(neg_elem.coeff(0), -5);
    }

    #[test]
    fn test_chain_element_normalize() {
        let mut elem = ChainElement::new(0);
        elem.set_coeff(0, 6);
        elem.set_coeff(1, 9);
        elem.normalize();
        assert_eq!(elem.coeff(0), 2);
        assert_eq!(elem.coeff(1), 3);
    }

    #[test]
    fn test_chain_new() {
        let chain = Chain::new();
        assert!(chain.is_zero());
        assert_eq!(chain.support_size(), 0);
    }

    #[test]
    fn test_chain_add_element() {
        let mut chain = Chain::new();
        let elem = ChainElement::from_generator(0, 0, 5);
        chain.add_element(elem);
        assert!(!chain.is_zero());
        assert_eq!(chain.support_size(), 1);
        assert_eq!(chain.element_at(0).unwrap().coeff(0), 5);
    }

    #[test]
    fn test_chain_support_degrees() {
        let mut chain = Chain::new();
        chain.add_element(ChainElement::from_generator(0, 0, 1));
        chain.add_element(ChainElement::from_generator(2, 1, 1));
        chain.add_element(ChainElement::from_generator(-1, 0, 1));
        let degrees = chain.support_degrees();
        assert_eq!(degrees, vec![-1, 0, 2]);
    }
}
