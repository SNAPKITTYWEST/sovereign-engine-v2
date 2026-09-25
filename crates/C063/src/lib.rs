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
    // In Z, (0) is prime but not maximal ((0) ⊂ (p)); (g) is maximal iff g
    // is a prime number.
    !ideal.is_zero && is_prime_ideal(ideal) && is_prime_number(ideal.gcd())
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

/// `lower ⊊ candidate ⊊ upper` as ideals (compared by their elements, not
/// by their generator lists).
pub fn is_strictly_between(lower: &Ideal, candidate: &Ideal, upper: &Ideal) -> bool {
    compare_ideals(candidate, lower) == IdealComparison::StrictlyGreater
        && compare_ideals(upper, candidate) == IdealComparison::StrictlyGreater
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
        let (two, four, three) = (Ideal::principal(2), Ideal::principal(4), Ideal::principal(3));
        assert_eq!(compare_ideals(&two, &four), IdealComparison::StrictlyGreater);
        assert_eq!(compare_ideals(&four, &two), IdealComparison::StrictlyLess);
        assert_eq!(compare_ideals(&two, &three), IdealComparison::Incomparable);
        assert_eq!(compare_ideals(&Ideal::new(vec![4, 6]), &two), IdealComparison::Equal);
    }

    #[test]
    fn test_is_strictly_between() {
        let (eight, four, two) = (Ideal::principal(8), Ideal::principal(4), Ideal::principal(2));
        assert!(is_strictly_between(&eight, &four, &two));
        assert!(!is_strictly_between(&two, &four, &eight));
        assert!(!is_strictly_between(&four, &Ideal::new(vec![8, 12]), &two));
        assert!(is_strictly_between(&Ideal::zero(), &two, &Ideal::principal(1)));
    }

    #[test]
    fn maximal_ideals_of_z() {
        assert!(is_maximal_ideal(&Ideal::new(vec![6, 9])));
        assert!(!is_maximal_ideal(&Ideal::new(vec![2, 3])));
        assert!(!is_maximal_ideal(&Ideal::principal(9)));
    }
}
