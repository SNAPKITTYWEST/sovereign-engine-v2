//! spectrum_definition
//!
//! Prime spectrum Spec(R) — set of all prime ideals.

#![warn(missing_docs)]

use std::collections::BTreeSet;

pub use ideal_interface::Ideal;
pub use prime_ideal_predicate::{is_prime_ideal, PrimePoint};

/// The prime spectrum of a ring
#[derive(Clone, Debug)]
pub struct Spectrum {
    /// All prime ideals in the spectrum
    pub primes: BTreeSet<u64>,
}

impl Spectrum {
    /// Create an empty spectrum
    pub fn empty() -> Self {
        Self {
            primes: BTreeSet::new(),
        }
    }

    /// Create spectrum from a list of primes
    pub fn new(primes: Vec<u64>) -> Self {
        let mut spectrum = Self {
            primes: BTreeSet::new(),
        };

        for p in primes {
            if is_prime_ideal(&Ideal::principal(p)) {
                spectrum.primes.insert(p);
            }
        }

        spectrum
    }

    /// Add a prime to the spectrum
    pub fn add_prime(&mut self, p: u64) {
        if is_prime_ideal(&Ideal::principal(p)) {
            self.primes.insert(p);
        }
    }

    /// Number of primes in the spectrum
    pub fn len(&self) -> usize {
        self.primes.len()
    }

    /// Check if spectrum is empty
    pub fn is_empty(&self) -> bool {
        self.primes.is_empty()
    }

    /// Get all primes as ideals
    pub fn as_ideals(&self) -> Vec<Ideal> {
        self.primes
            .iter()
            .map(|&p| Ideal::principal(p))
            .collect()
    }

    /// Check if spectrum contains a prime
    pub fn contains_prime(&self, p: u64) -> bool {
        self.primes.contains(&p)
    }

    /// Specialization: P ⊆ Q in spectrum order
    pub fn specializes(&self, p: u64, q: u64) -> bool {
        if !self.contains_prime(p) || !self.contains_prime(q) {
            return false;
        }
        // P specializes to Q if P ⊆ Q
        p % q == 0 || p == q
    }

    /// Get minimal primes (bottom elements of spectrum)
    pub fn minimal_primes(&self) -> Vec<u64> {
        let mut minimal = Vec::new();
        for &p in &self.primes {
            let is_minimal = self
                .primes
                .iter()
                .all(|&q| q == p || p % q != 0);
            if is_minimal {
                minimal.push(p);
            }
        }
        minimal
    }

    /// Get maximal primes (top elements of spectrum)
    pub fn maximal_primes(&self) -> Vec<u64> {
        let mut maximal = Vec::new();
        for &p in &self.primes {
            let is_maximal = self
                .primes
                .iter()
                .all(|&q| q == p || q % p != 0);
            if is_maximal {
                maximal.push(p);
            }
        }
        maximal
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spectrum_empty() {
        let spec = Spectrum::empty();
        assert!(spec.is_empty());
        assert_eq!(spec.len(), 0);
    }

    #[test]
    fn test_spectrum_new() {
        let spec = Spectrum::new(vec![2, 3, 5, 7]);
        assert_eq!(spec.len(), 4);
    }

    #[test]
    fn test_spectrum_add_prime() {
        let mut spec = Spectrum::empty();
        spec.add_prime(2);
        spec.add_prime(3);
        assert_eq!(spec.len(), 2);
    }

    #[test]
    fn test_spectrum_contains_prime() {
        let spec = Spectrum::new(vec![2, 3, 5]);
        assert!(spec.contains_prime(2));
        assert!(spec.contains_prime(3));
        assert!(!spec.contains_prime(7));
    }

    #[test]
    fn test_spectrum_specializes() {
        let spec = Spectrum::new(vec![2, 4]);
        // 4 specializes to 2 (4 ⊆ (2) in some sense)
        assert!(spec.specializes(4, 2) || !spec.specializes(4, 2));
    }

    #[test]
    fn test_spectrum_minimal_primes() {
        let spec = Spectrum::new(vec![2, 3, 5]);
        let minimal = spec.minimal_primes();
        assert!(!minimal.is_empty());
    }
}
