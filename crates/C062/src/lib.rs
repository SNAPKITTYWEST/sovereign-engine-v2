//! prime_ideal_predicate
//!
//! Test whether an ideal is prime.

#![warn(missing_docs)]

pub use ideal_interface::Ideal;

/// Is the ideal prime? Over Z an ideal is `(g)` with `g = gcd` of its
/// generators, and `(g)` is prime iff `g = 0` (Z is a domain) or `g` is a
/// prime number. `(1) = Z` is not prime.
pub fn is_prime_ideal(ideal: &Ideal) -> bool {
    ideal.is_zero || is_prime_number(ideal.gcd())
}

/// Check if a number is prime
fn is_prime_number(n: u64) -> bool {
    match n {
        0 | 1 => false,
        2 => true,
        n if n % 2 == 0 => false,
        n => {
            let limit = (n as f64).sqrt() as u64 + 1;
            !(3..=limit).step_by(2).any(|i| n % i == 0)
        }
    }
}

/// Check if an ideal is weakly prime (a weaker condition)
pub fn is_weakly_prime(ideal: &Ideal) -> bool {
    if ideal.is_zero {
        return true;
    }
    let g = ideal.gcd();
    g == 1 || is_prime_number(g)
}

/// Convert ideal to prime spectrum point (if prime). In Z, `(0)` has height
/// 0 and every non-zero prime `(p)` has height 1 (`(0) ⊂ (p)`).
pub fn to_prime_point(ideal: &Ideal) -> Option<PrimePoint> {
    if is_prime_ideal(ideal) {
        Some(PrimePoint {
            ideal: ideal.clone(),
            height: if ideal.is_zero { 0 } else { 1 },
        })
    } else {
        None
    }
}

/// A point in the prime spectrum
#[derive(Clone, Debug)]
pub struct PrimePoint {
    /// The prime ideal
    pub ideal: Ideal,
    /// Height of the prime (number of primes below it)
    pub height: usize,
}

impl PrimePoint {
    /// Check if this prime contains another prime
    pub fn contains(&self, other: &PrimePoint) -> bool {
        self.ideal.contains_ideal(&other.ideal)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_prime_ideal_zero() {
        let ideal = Ideal::zero();
        assert!(is_prime_ideal(&ideal));
    }

    #[test]
    fn test_is_prime_ideal_principal() {
        let ideal2 = Ideal::principal(2);
        assert!(is_prime_ideal(&ideal2));

        let ideal4 = Ideal::principal(4);
        assert!(!is_prime_ideal(&ideal4));
    }

    #[test]
    fn multi_generator_ideals_use_the_gcd() {
        assert!(is_prime_ideal(&Ideal::new(vec![6, 10])));
        assert!(!is_prime_ideal(&Ideal::new(vec![2, 3])));
        assert!(!is_prime_ideal(&Ideal::principal(1)));
        assert_eq!(to_prime_point(&Ideal::zero()).unwrap().height, 0);
    }

    #[test]
    fn test_is_weakly_prime() {
        let ideal = Ideal::new(vec![2, 3]);
        assert!(is_weakly_prime(&ideal)); // gcd = 1
    }

    #[test]
    fn test_to_prime_point() {
        let ideal = Ideal::principal(5);
        let point = to_prime_point(&ideal);
        assert!(point.is_some());
        assert_eq!(point.unwrap().height, 1);
    }

    #[test]
    fn test_prime_point_contains() {
        let p1 = Ideal::principal(2);
        let p2 = Ideal::principal(4);
        let point1 = PrimePoint {
            ideal: p1,
            height: 0,
        };
        let point2 = PrimePoint {
            ideal: p2,
            height: 1,
        };
        assert!(point1.contains(&point2));
    }
}
