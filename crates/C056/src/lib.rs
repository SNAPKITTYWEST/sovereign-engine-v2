//! tor_higher_degrees
//!
//! Higher Tor groups `Tor_i(M, N)`, `i > 0`: vanishing, growth, and the
//! bridge from a computed [`TorComputation`] to per-degree sequences.

#![warn(missing_docs)]

pub use derived_homology::compute_tor_from_resolution;
pub use tor_functor_definition::{TorComputation, TorGroup, TorIndex};

/// Free ranks of `Tor_i` for one degree across several module pairs.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HigherTorProperties {
    /// The degree i
    pub degree: usize,
    /// Ranks at this degree
    pub ranks: Vec<usize>,
}

impl HigherTorProperties {
    /// Create properties for Tor_i
    pub fn new(degree: usize, ranks: Vec<usize>) -> Self {
        Self { degree, ranks }
    }

    /// True iff every recorded rank is zero.
    pub fn all_trivial(&self) -> bool {
        self.ranks.iter().all(|&r| r == 0)
    }

    /// Total rank across all Tor_i for fixed i
    pub fn total_rank(&self) -> usize {
        self.ranks.iter().sum()
    }
}

/// `Tor_0, Tor_1, …` up to the highest computed degree; missing degrees are
/// `None`.
pub fn tor_sequence(tor: &TorComputation) -> Vec<Option<TorGroup>> {
    match tor.max_degree() {
        None => Vec::new(),
        Some(top) => (0..=top).map(|i| tor.tor(i).cloned()).collect(),
    }
}

/// True iff every `Tor_i` with `i > 0` is trivial (missing degrees count as
/// trivial) — e.g. when one of the modules is free.
pub fn is_short_exact_sequence(tor_groups: &[Option<TorGroup>]) -> bool {
    tor_groups
        .iter()
        .skip(1)
        .all(|opt| opt.as_ref().map(|g| g.is_trivial()).unwrap_or(true))
}

/// Degrees where Tor vanishes (missing degrees count as vanishing).
pub fn vanishing_indices(tor_groups: &[Option<TorGroup>]) -> Vec<usize> {
    tor_groups
        .iter()
        .enumerate()
        .filter_map(|(i, opt)| {
            if opt.as_ref().map(|g| g.is_trivial()).unwrap_or(true) {
                Some(i)
            } else {
                None
            }
        })
        .collect()
}

/// Ratios of generator counts between consecutive degrees (skipping degrees
/// that follow a zero count).
pub fn tor_growth_rate(tor_groups: &[Option<TorGroup>]) -> Vec<f64> {
    let counts: Vec<usize> = tor_groups
        .iter()
        .map(|opt| opt.as_ref().map(|g| g.num_generators()).unwrap_or(0))
        .collect();
    counts
        .windows(2)
        .filter(|w| w[0] > 0)
        .map(|w| w[1] as f64 / w[0] as f64)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use derived_homology::tor_of;
    use tor_functor_definition::ProjectiveResolution;

    fn tor(m: i64, n: i64) -> TorComputation {
        tor_of(
            &ProjectiveResolution::cyclic_resolution(m),
            &ProjectiveResolution::cyclic_resolution(n),
        )
        .unwrap()
    }

    #[test]
    fn higher_tor_detects_shared_torsion() {
        let seq = tor_sequence(&tor(4, 6));
        assert!(!is_short_exact_sequence(&seq));
        assert_eq!(vanishing_indices(&seq), vec![2]);
        assert_eq!(tor_growth_rate(&seq), vec![1.0, 0.0]);

        let coprime = tor_sequence(&tor(2, 3));
        assert!(is_short_exact_sequence(&coprime));
        assert_eq!(vanishing_indices(&coprime), vec![0, 1, 2]);
    }

    #[test]
    fn free_argument_kills_higher_tor() {
        let seq = tor_sequence(&tor(4, 0));
        assert!(is_short_exact_sequence(&seq));
        assert_eq!(seq[0].as_ref().unwrap().torsion_orders(), vec![4]);
    }

    #[test]
    fn properties_helpers() {
        let props = HigherTorProperties::new(1, vec![0, 0]);
        assert!(props.all_trivial());
        assert_eq!(HigherTorProperties::new(2, vec![1, 2]).total_rank(), 3);
        assert!(tor_sequence(&TorComputation::new()).is_empty());
    }
}
