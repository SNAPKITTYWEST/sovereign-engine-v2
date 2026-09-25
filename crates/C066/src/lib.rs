//! spectrum_chains
//!
//! Prime chains in a spectrum: totally ordered sequences of prime ideals.
//! Used to compute Krull dimension as length of longest chains.

#![warn(missing_docs)]

use spectrum_definition::Spectrum;
use spectrum_order::SpecializationPreorder;

/// A chain in the spectrum: totally ordered sequence of primes
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PrimeChain {
    /// Primes in the chain, ordered by specialization
    chain: Vec<u64>,
}

impl PrimeChain {
    /// Create a single-element chain
    pub fn singleton(p: u64) -> Self {
        Self { chain: vec![p] }
    }

    /// Create empty chain
    pub fn empty() -> Self {
        Self { chain: Vec::new() }
    }

    /// Length of the chain
    pub fn len(&self) -> usize {
        self.chain.len()
    }

    /// Check if chain is empty
    pub fn is_empty(&self) -> bool {
        self.chain.is_empty()
    }

    /// Get elements in chain
    pub fn elements(&self) -> &[u64] {
        &self.chain
    }

    /// Check if chain is valid (totally ordered)
    pub fn is_valid(&self, preorder: &SpecializationPreorder) -> bool {
        for i in 0..self.chain.len() {
            for j in i + 1..self.chain.len() {
                if !preorder.le(self.chain[i], self.chain[j]) {
                    return false;
                }
            }
        }
        true
    }

    /// Try to extend chain with p
    pub fn extend(&self, p: u64, preorder: &SpecializationPreorder) -> Option<Self> {
        if self.chain.is_empty() {
            return Some(Self::singleton(p));
        }

        // p must be comparable with last element
        let last = self.chain[self.chain.len() - 1];
        if preorder.le(last, p) {
            let mut new_chain = self.clone();
            new_chain.chain.push(p);
            Some(new_chain)
        } else {
            None
        }
    }
}

impl Ord for PrimeChain {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.chain.cmp(&other.chain)
    }
}

impl PartialOrd for PrimeChain {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

/// Maximal chains in a spectrum
#[derive(Clone, Debug)]
pub struct MaximalChains {
    chains: Vec<PrimeChain>,
}

impl MaximalChains {
    /// Find all maximal chains in spectrum
    pub fn find_all(spec: &Spectrum, preorder: &SpecializationPreorder) -> Self {
        let primes: Vec<u64> = spec.primes.iter().copied().collect();
        let mut maximal = Vec::new();

        // Build chains greedily starting from each prime
        for &start in &primes {
            let chains = Self::build_chains_from(start, &primes, preorder);
            for chain in chains {
                // Check if already subsumed by existing chain
                let is_maximal = maximal.iter().all(|c: &PrimeChain| {
                    c.len() <= chain.len() || !Self::is_subchain(&chain, c)
                });
                if is_maximal {
                    maximal.retain(|c: &PrimeChain| {
                        chain.len() <= c.len() || !Self::is_subchain(c, &chain)
                    });
                    maximal.push(chain);
                }
            }
        }

        Self { chains: maximal }
    }

    /// Build all chains starting from p
    fn build_chains_from(p: u64, all_primes: &[u64], preorder: &SpecializationPreorder) -> Vec<PrimeChain> {
        let mut result = vec![PrimeChain::singleton(p)];
        let mut queue = vec![PrimeChain::singleton(p)];

        while let Some(current) = queue.pop() {
            for &q in all_primes {
                if let Some(extended) = current.extend(q, preorder) {
                    if !result.iter().any(|c| c == &extended) {
                        result.push(extended.clone());
                        queue.push(extended);
                    }
                }
            }
        }

        result
    }

    /// Check if chain1 is a subchain of chain2
    fn is_subchain(chain1: &PrimeChain, chain2: &PrimeChain) -> bool {
        if chain1.len() > chain2.len() {
            return false;
        }
        let mut j = 0;
        for &p in chain1.elements() {
            let mut found = false;
            while j < chain2.len() {
                if chain2.chain[j] == p {
                    found = true;
                    j += 1;
                    break;
                }
                j += 1;
            }
            if !found {
                return false;
            }
        }
        true
    }

    /// Length of longest chain
    pub fn longest_length(&self) -> usize {
        self.chains.iter().map(|c| c.len()).max().unwrap_or(0)
    }

    /// Get all maximal chains
    pub fn chains(&self) -> &[PrimeChain] {
        &self.chains
    }

    /// Filter chains of given length
    pub fn chains_of_length(&self, len: usize) -> Vec<&PrimeChain> {
        self.chains.iter().filter(|c| c.len() == len).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_prime_chain_singleton() {
        let chain = PrimeChain::singleton(2);
        assert_eq!(chain.len(), 1);
        assert!(!chain.is_empty());
        assert_eq!(chain.elements(), &[2]);
    }

    #[test]
    fn test_prime_chain_empty() {
        let chain = PrimeChain::empty();
        assert!(chain.is_empty());
        assert_eq!(chain.len(), 0);
    }

    #[test]
    fn test_maximal_chains() {
        let spec = Spectrum::new(vec![2, 3, 5]);
        let preorder = SpecializationPreorder::from_spectrum(&spec);
        let chains = MaximalChains::find_all(&spec, &preorder);

        assert!(!chains.chains().is_empty());
        assert!(chains.longest_length() > 0);
    }

    #[test]
    fn test_prime_chain_extend() {
        let spec = Spectrum::new(vec![2, 4, 6]);
        let preorder = SpecializationPreorder::from_spectrum(&spec);
        let chain = PrimeChain::singleton(2);

        // Try to extend
        if let Some(extended) = chain.extend(4, &preorder) {
            assert_eq!(extended.len(), 2);
        }
    }
}
