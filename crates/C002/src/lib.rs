//! gap_tensor_primes
//!
//! Prime-level operations over the candidate prime set used by the gap
//! tensor: candidate lookup, neighbouring candidates, gaps between
//! candidates, and validated node construction.

#![warn(missing_docs)]

use gap_tensor_core::{GapTensorNode, CANDIDATE_PRIMES, SIGMA_GAP_MAX};
use std::fmt;

/// Number of candidate primes (tensor axes).
pub const NUM_CANDIDATES: usize = CANDIDATE_PRIMES.len();

/// Errors from prime-level node operations.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PrimeError {
    /// The value is not one of [`CANDIDATE_PRIMES`].
    NotACandidate(u32),
    /// The node is Nil and carries no prime.
    NilNode,
}

impl fmt::Display for PrimeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PrimeError::NotACandidate(p) => write!(f, "{p} is not a candidate prime"),
            PrimeError::NilNode => write!(f, "node is Nil and has no prime"),
        }
    }
}

impl std::error::Error for PrimeError {}

/// Is `p` one of the candidate primes?
pub fn is_candidate_prime(p: u32) -> bool {
    CANDIDATE_PRIMES.contains(&p)
}

/// Position of `p` in [`CANDIDATE_PRIMES`], if it is a candidate.
pub fn candidate_index(p: u32) -> Option<usize> {
    CANDIDATE_PRIMES.iter().position(|&c| c == p)
}

/// The candidate prime at `index`, if in range.
pub fn candidate_at(index: usize) -> Option<u32> {
    CANDIDATE_PRIMES.get(index).copied()
}

/// The next larger candidate prime after `p`. `None` if `p` is the largest
/// candidate or not a candidate at all.
pub fn next_candidate(p: u32) -> Option<u32> {
    candidate_index(p).and_then(|i| candidate_at(i + 1))
}

/// The next smaller candidate prime before `p`. `None` if `p` is the smallest
/// candidate or not a candidate at all.
pub fn prev_candidate(p: u32) -> Option<u32> {
    candidate_index(p)
        .and_then(|i| i.checked_sub(1))
        .and_then(candidate_at)
}

/// Gaps between consecutive candidate primes, in order.
pub fn candidate_gaps() -> [u32; NUM_CANDIDATES - 1] {
    let mut gaps = [0; NUM_CANDIDATES - 1];
    for (i, gap) in gaps.iter_mut().enumerate() {
        *gap = CANDIDATE_PRIMES[i + 1] - CANDIDATE_PRIMES[i];
    }
    gaps
}

/// A gap is consonant iff it does not exceed [`SIGMA_GAP_MAX`].
pub fn is_consonant_gap(gap: u32) -> bool {
    gap <= SIGMA_GAP_MAX
}

/// Absolute difference between the primes of two nodes.
pub fn node_gap(a: &GapTensorNode, b: &GapTensorNode) -> Result<u32, PrimeError> {
    let pa = a.prime_opt().ok_or(PrimeError::NilNode)?;
    let pb = b.prime_opt().ok_or(PrimeError::NilNode)?;
    Ok(pa.abs_diff(pb))
}

/// Build a node whose prime is checked against [`CANDIDATE_PRIMES`].
pub fn candidate_node(
    prime: u32,
    multiplicity: u32,
    spectral_weight: f32,
) -> Result<GapTensorNode, PrimeError> {
    if !is_candidate_prime(prime) {
        return Err(PrimeError::NotACandidate(prime));
    }
    Ok(GapTensorNode::new(prime, multiplicity, spectral_weight))
}

/// A node is well-formed at the prime level iff it is Nil or carries a
/// candidate prime.
pub fn validate_node(node: &GapTensorNode) -> Result<(), PrimeError> {
    if node.is_nil() || is_candidate_prime(node.prime_val) {
        Ok(())
    } else {
        Err(PrimeError::NotACandidate(node.prime_val))
    }
}

/// Deterministic primality test by trial division.
pub fn is_prime(n: u32) -> bool {
    if n < 2 {
        return false;
    }
    if n < 4 {
        return true;
    }
    if n % 2 == 0 {
        return false;
    }
    let n = n as u64;
    let mut d = 3u64;
    while d * d <= n {
        if n % d == 0 {
            return false;
        }
        d += 2;
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn candidate_lookup() {
        assert!(is_candidate_prime(7));
        assert!(!is_candidate_prime(9));
        assert!(!is_candidate_prime(0));
        assert_eq!(candidate_index(11), Some(4));
        assert_eq!(candidate_at(0), Some(2));
        assert_eq!(candidate_at(NUM_CANDIDATES), None);
    }

    #[test]
    fn neighbouring_candidates() {
        assert_eq!(next_candidate(2), Some(3));
        assert_eq!(next_candidate(13), None);
        assert_eq!(next_candidate(4), None);
        assert_eq!(prev_candidate(2), None);
        assert_eq!(prev_candidate(11), Some(7));
    }

    #[test]
    fn candidate_gaps_are_consonant() {
        assert_eq!(candidate_gaps(), [1, 2, 2, 4, 2]);
        assert!(candidate_gaps().iter().all(|&g| is_consonant_gap(g)));
        assert!(!is_consonant_gap(SIGMA_GAP_MAX + 1));
    }

    #[test]
    fn gaps_between_nodes() {
        let a = GapTensorNode::new(2, 1, 1.0);
        let b = GapTensorNode::new(7, 1, 1.0);
        assert_eq!(node_gap(&a, &b), Ok(5));
        assert_eq!(node_gap(&b, &a), Ok(5));
        assert_eq!(node_gap(&a, &GapTensorNode::NIL), Err(PrimeError::NilNode));
    }

    #[test]
    fn validated_construction() {
        assert_eq!(candidate_node(9, 1, 1.0), Err(PrimeError::NotACandidate(9)));
        assert_eq!(candidate_node(5, 2, 0.5).unwrap().prime_val, 5);
        assert!(validate_node(&GapTensorNode::NIL).is_ok());
        assert_eq!(
            validate_node(&GapTensorNode::new(4, 1, 1.0)),
            Err(PrimeError::NotACandidate(4))
        );
    }

    #[test]
    fn primality() {
        let primes = [2, 3, 5, 7, 11, 13, 17, 97, 7919, 4_294_967_291];
        let composites = [0, 1, 4, 9, 15, 91, 7917, 4_294_967_295];
        assert!(primes.iter().all(|&p| is_prime(p)));
        assert!(composites.iter().all(|&c| !is_prime(c)));
        assert!(CANDIDATE_PRIMES.iter().all(|&p| is_prime(p)));
    }
}
