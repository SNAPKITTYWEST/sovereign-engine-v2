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

/// Exact primality by 6k ± 1 trial division: after ruling out 2 and 3 it
/// only tries divisors of the form 6k ± 1 up to √n. Agrees with
/// [`is_prime`] on every input.
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
    // Numbers of form 6k±1 are candidate primes. `i <= n / i` is
    // `i * i <= n` without overflowing for primes near u64::MAX.
    let mut i = 5u64;
    while i <= n / i {
        if n % i == 0 || n % (i + 2) == 0 {
            return false;
        }
        i += 6;
    }
    true
}

/// A node for `prime` (multiplicity 1, weight 1.0), or `None` if the prime
/// does not fit the node's 32-bit prime field.
pub fn try_prime_to_tensor_node(prime: u64) -> Option<GapTensorNode> {
    u32::try_from(prime).ok().map(|p| GapTensorNode::new(p, 1, 1.0))
}

/// Create a GapTensorNode representing a prime in the candidate set.
///
/// The prime is truncated to 32 bits; use [`try_prime_to_tensor_node`] when
/// the value may exceed `u32::MAX`.
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
    fn candidate_test_is_exact() {
        for n in 0..10_000 {
            assert_eq!(is_prime_candidate(n), is_prime(n), "n = {n}");
        }
        // 2^31 − 1 and 2^32 − 5 are prime; 2^32 + 1 = 641 · 6700417 is not.
        for (n, prime) in [(2_147_483_647, true), (4_294_967_291, true), (4_294_967_297, false)] {
            assert_eq!((is_prime_candidate(n), is_prime(n)), (prime, prime), "n = {n}");
        }
    }

    #[test]
    fn test_prime_to_tensor_node() {
        let node = prime_to_tensor_node(5);
        assert_eq!(node.resonance(), 1.0);  // multiplicity=1, spectral_weight=1.0 => resonance=1.0
        assert!(!node.is_nil());
    }
}
