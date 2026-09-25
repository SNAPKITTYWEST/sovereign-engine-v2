//! prime_enumeration
//!
//! Prime number enumeration and sequence generation.

#![warn(missing_docs)]

pub use prime_predicate::{is_prime, is_prime_candidate};

/// Generate all primes up to a given limit using Sieve of Eratosthenes.
///
/// # Arguments
/// * `limit` - Upper bound (inclusive)
///
/// # Returns
/// Vector of all primes <= limit
pub fn primes_up_to(limit: u64) -> Vec<u64> {
    if limit < 2 {
        return Vec::new();
    }

    let n = (limit + 1) as usize;
    let mut sieve = vec![true; n];
    sieve[0] = false;
    sieve[1] = false;

    for i in 2..((limit as f64).sqrt() as usize + 1) {
        if sieve[i] {
            for j in ((i * i)..n).step_by(i) {
                sieve[j] = false;
            }
        }
    }

    sieve
        .into_iter()
        .enumerate()
        .filter_map(|(i, is_p)| if is_p { Some(i as u64) } else { None })
        .collect()
}

/// Get the n-th prime (0-indexed).
pub fn nth_prime(n: usize) -> Option<u64> {
    if n == 0 {
        return Some(2);
    }

    // Better upper bound for nth prime using Prime Number Theorem
    let estimate = if n < 6 {
        20
    } else if n < 1000 {
        (n as f64 * ((n as f64).ln() + (n as f64).ln().ln())) as u64 + 10
    } else {
        (n as f64 * (n as f64).ln() * 1.3) as u64
    };

    let primes = primes_up_to(estimate);
    primes.get(n).copied()
}

/// Count the number of primes up to n (Prime Counting Function π(n)).
pub fn prime_count(limit: u64) -> usize {
    primes_up_to(limit).len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_primes_up_to_small() {
        let primes = primes_up_to(10);
        assert_eq!(primes, vec![2, 3, 5, 7]);
    }

    #[test]
    fn test_primes_up_to_larger() {
        let primes = primes_up_to(30);
        assert_eq!(primes, vec![2, 3, 5, 7, 11, 13, 17, 19, 23, 29]);
    }

    #[test]
    fn test_nth_prime() {
        assert_eq!(nth_prime(0), Some(2));
        assert_eq!(nth_prime(1), Some(3));
        assert_eq!(nth_prime(2), Some(5));
        assert_eq!(nth_prime(3), Some(7));
        assert_eq!(nth_prime(10), Some(31));
    }

    #[test]
    fn test_prime_count() {
        assert_eq!(prime_count(2), 1);  // just 2
        assert_eq!(prime_count(10), 4); // 2,3,5,7
        assert_eq!(prime_count(30), 10); // 2..29
    }
}
