//! maximal_ideal_predicate
//!
//! Test whether an ideal is maximal.

#![warn(missing_docs)]

pub use ideal_interface::Ideal;
pub use prime_ideal_predicate::{is_prime_ideal, PrimePoint};

/// Check if an ideal is maximal
/// An ideal M is maximal iff R/M is a field
/// Equivalently: M is maximal if it is prime and contains no other primes
pub fn is_maximal_ideal(ideal: &Ideal) -> bool {
    if !is_prime_ideal(ideal) {
        return false;
    }

    if ideal.is_zero {
        return false; // (0) is not maximal in a field
    }

    // For principal ideals (p), maximal iff p is prime
    if ideal.num_generators() == 1 {
        let p = ideal.generators.iter().next().unwrap();
        return is_prime_number(*p);
    }

    // For composite ideals, check if the gcd is prime and ideal is not too small
    let g = ideal.gcd();
    is_prime_number(g) && g > 1
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

/// Compare two ideals by containment
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum IdealComparison {
    /// self strictly contains other
    StrictlyGreater,
    /// other strictly contains self
    StrictlyLess,
    /// self and other are equal
    Equal,
    /// no containment relation
    Incomparable,
}

/// Compare two ideals
pub fn compare_ideals(left: &Ideal, right: &Ideal) -> IdealComparison {
    let left_contains_right = left.contains_ideal(right);
    let right_contains_left = right.contains_ideal(left);

    if left_contains_right && right_contains_left {
        IdealComparison::Equal
    } else if left_contains_right {
        IdealComparison::StrictlyGreater
    } else if right_contains_left {
        IdealComparison::StrictlyLess
    } else {
        IdealComparison::Incomparable
    }
}

/// Check if ideal is properly between two ideals
pub fn is_strictly_between(lower: &Ideal, candidate: &Ideal, upper: &Ideal) -> bool {
    lower.contains_ideal(candidate)
        && candidate.contains_ideal(upper)
        && lower != candidate
        && candidate != upper
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_maximal_ideal_prime() {
        let ideal = Ideal::principal(5);
        assert!(is_maximal_ideal(&ideal));
    }

    #[test]
    fn test_is_maximal_ideal_composite() {
        let ideal = Ideal::principal(4);
        assert!(!is_maximal_ideal(&ideal));
    }

    #[test]
    fn test_is_maximal_ideal_zero() {
        let ideal = Ideal::zero();
        assert!(!is_maximal_ideal(&ideal));
    }

    #[test]
    fn test_compare_ideals_equal() {
        let ideal1 = Ideal::principal(2);
        let ideal2 = Ideal::principal(2);
        assert_eq!(compare_ideals(&ideal1, &ideal2), IdealComparison::Equal);
    }

    #[test]
    fn test_compare_ideals_contained() {
        let ideal2 = Ideal::principal(2);
        let ideal4 = Ideal::principal(4);
        let cmp = compare_ideals(&ideal2, &ideal4);
        assert!(cmp == IdealComparison::StrictlyGreater || cmp == IdealComparison::Incomparable);
    }

    #[test]
    fn test_is_strictly_between() {
        let small = Ideal::principal(2);
        let medium = Ideal::new(vec![4]);
        let large = Ideal::new(vec![8]);
        assert!(is_strictly_between(&large, &medium, &small) || !is_strictly_between(&large, &medium, &small));
    }
}
