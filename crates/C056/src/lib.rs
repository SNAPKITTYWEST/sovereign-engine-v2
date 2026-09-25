//! tor_higher_degrees
//!
//! Higher Tor groups Tor_i(M, N) for i > 0.

#![warn(missing_docs)]

pub use tor_functor_definition::{TorGroup, TorIndex};
pub use derived_homology::compute_tor_from_resolution;

/// Properties of higher Tor groups
#[derive(Clone, Debug)]
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

    /// Check if all higher Tor groups are trivial
    pub fn all_trivial(&self) -> bool {
        self.ranks.iter().all(|&r| r == 0)
    }

    /// Total rank across all Tor_i for fixed i
    pub fn total_rank(&self) -> usize {
        self.ranks.iter().sum()
    }
}

/// Analyze if resolution is short exact (all Tor_i for i > 0 are trivial)
pub fn is_short_exact_sequence(
    tor_groups: &[Option<TorGroup>],
) -> bool {
    // Check if all Tor_i for i > 0 are trivial
    tor_groups
        .iter()
        .skip(1)
        .all(|opt| opt.as_ref().map(|g| g.is_trivial()).unwrap_or(true))
}

/// Get vanishing indices (degrees where Tor vanishes)
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

/// Compute growth rate of Tor ranks across degrees
pub fn tor_growth_rate(tor_groups: &[Option<TorGroup>]) -> Vec<f64> {
    let mut rates = Vec::new();
    let ranks: Vec<usize> = tor_groups
        .iter()
        .map(|opt| opt.as_ref().map(|g| g.num_generators()).unwrap_or(0))
        .collect();

    for i in 1..ranks.len() {
        if ranks[i - 1] > 0 {
            rates.push(ranks[i] as f64 / ranks[i - 1] as f64);
        }
    }
    rates
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_higher_tor_properties() {
        let props = HigherTorProperties::new(1, vec![2, 3, 1]);
        assert_eq!(props.degree, 1);
        assert_eq!(props.total_rank(), 6);
    }

    #[test]
    fn test_is_short_exact() {
        let mut tor_groups = vec![
            Some(TorGroup::new(TorIndex::new(0), 5)),
            None,
            None,
        ];
        assert!(is_short_exact_sequence(&tor_groups));

        tor_groups[1] = Some(TorGroup::new(TorIndex::new(1), 2));
        assert!(!is_short_exact_sequence(&tor_groups));
    }

    #[test]
    fn test_vanishing_indices() {
        let tor_groups = vec![
            Some(TorGroup::new(TorIndex::new(0), 5)),
            None,
            Some(TorGroup::new(TorIndex::new(2), 0)),
            None,
        ];
        let vanishing = vanishing_indices(&tor_groups);
        assert!(vanishing.contains(&1));
        assert!(vanishing.contains(&2));
        assert!(vanishing.contains(&3));
    }

    #[test]
    fn test_tor_growth_rate() {
        let tor_groups = vec![
            Some(TorGroup::new(TorIndex::new(0), 4)),
            Some(TorGroup::new(TorIndex::new(1), 2)),
            Some(TorGroup::new(TorIndex::new(2), 1)),
        ];
        let rates = tor_growth_rate(&tor_groups);
        assert_eq!(rates.len(), 2);
        assert!(rates[0] < 1.0); // 2 / 4 = 0.5
    }
}
