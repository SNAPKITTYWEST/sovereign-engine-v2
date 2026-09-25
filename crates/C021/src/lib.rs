//! prime_predicate
//!
//! Core prime number predicate and basic primality testing.
//! Foundation for Tier 2 prime/gap engine.

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;

/// Check if a number is prime using trial division.
///
/// # Arguments
/// * `n` - The number to test
///
/// # Returns
/// `true` if n is prime, `false` otherwise
pub fn is_prime(n: u64) -> bool {
    match n {
        0 | 1 => false,
        2 => true,
        n if n % 2 == 0 => false,
        n => {
            let limit = (n as f64).sqrt() as u64 + 1;
            !(3..=limit)
                .step_by(2)
                .any(|i| n % i == 0)
        }
    }
}

/// Check if a number is a prime candidate (sieve-based prefilter).
///
/// This is a fast heuristic that catches obvious composites.
pub fn is_prime_candidate(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    if n == 2 || n == 3 {
        return true;
    }
    if n % 2 == 0 || n % 3 == 0 {
        return false;
    }
    // Numbers of form 6k±1 are candidate primes
    let mut i = 5u64;
    while i * i <= n {
        if n % i == 0 || n % (i + 2) == 0 {
            return false;
        }
        i += 6;
    }
    true
}

/// Create a GapTensorNode representing a prime in the candidate set.
pub fn prime_to_tensor_node(prime: u64) -> GapTensorNode {
    GapTensorNode::new(
        prime as u32,       // prime_val
        1,                  // multiplicity = 1 (appears once)
        1.0,                // spectral_weight = 1.0 (normal resonance)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_prime_small() {
        assert!(!is_prime(0));
        assert!(!is_prime(1));
        assert!(is_prime(2));
        assert!(is_prime(3));
        assert!(!is_prime(4));
        assert!(is_prime(5));
        assert!(!is_prime(6));
        assert!(is_prime(7));
    }

    #[test]
    fn test_is_prime_larger() {
        assert!(is_prime(11));
        assert!(is_prime(13));
        assert!(!is_prime(15));
        assert!(is_prime(17));
        assert!(is_prime(19));
        assert!(!is_prime(20));
        assert!(is_prime(23));
    }

    #[test]
    fn test_is_prime_candidate() {
        assert!(!is_prime_candidate(0));
        assert!(!is_prime_candidate(1));
        assert!(is_prime_candidate(2));
        assert!(is_prime_candidate(3));
        assert!(!is_prime_candidate(4));
        assert!(is_prime_candidate(5));
        assert!(!is_prime_candidate(6));
        assert!(is_prime_candidate(7));
        assert!(!is_prime_candidate(8));
        assert!(!is_prime_candidate(9));
    }

    #[test]
    fn test_prime_to_tensor_node() {
        let node = prime_to_tensor_node(5);
        assert_eq!(node.resonance(), 1.0);  // multiplicity=1, spectral_weight=1.0 => resonance=1.0
        assert!(!node.is_nil());
    }
}
