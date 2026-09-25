//! dimension_upper_bounds
//!
//! Upper bounds on Krull dimension via various algebraic properties.
//! Key bounds: generator count, saturation, integral extensions.

#![warn(missing_docs)]

pub use krull_dimension_definition::{KrullDim, Spectrum};

/// Upper bound on Krull dimension
#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub struct DimensionUpperBound(pub usize);

impl DimensionUpperBound {
    /// Bound from number of generators
    /// For polynomial rings: dim(k[x₁,...,xₙ]) = n
    pub fn from_generators(num_generators: usize) -> Self {
        Self(num_generators)
    }

    /// Bound from number of relations
    /// In a quotient, dimension typically decreases
    pub fn from_relations(num_generators: usize, num_relations: usize) -> Self {
        let bound = if num_generators >= num_relations {
            num_generators - num_relations
        } else {
            0
        };
        Self(bound)
    }

    /// Bound from saturation property
    /// If I is an ideal, ht(I) ≤ μ(I) (number of generators)
    pub fn from_ideal_saturation(num_generators: usize) -> Self {
        Self(num_generators)
    }

    /// Bound from integral extension
    /// If R ⊆ S integral, then dim(R) ≤ dim(S)
    /// But we can also bound via transcendence degree
    pub fn from_transcendence_degree(trans_deg: usize) -> Self {
        Self(trans_deg)
    }

    /// Krull's principal ideal theorem: ht(p) ≤ μ(I) where p is minimal over I
    pub fn krull_pit_bound(num_generators: usize) -> Self {
        Self(num_generators)
    }

    /// Cohen-Seidenberg: for R ⊆ S integral, same dimension
    pub fn integral_extension_bound(other_dim: KrullDim) -> Self {
        Self(other_dim.dim())
    }

    /// Get numeric bound
    pub fn bound(&self) -> usize {
        self.0
    }

    /// Check if actual dimension satisfies bound
    pub fn satisfies(&self, actual_dim: KrullDim) -> bool {
        actual_dim.dim() <= self.0
    }

    /// Refine bound by taking minimum
    pub fn refine(&mut self, other: Self) {
        self.0 = self.0.min(other.0);
    }

    /// Get tightest bound from multiple sources
    pub fn tightest(bounds: &[Self]) -> Self {
        bounds
            .iter()
            .copied()
            .min()
            .unwrap_or(Self(usize::MAX))
    }
}

impl std::fmt::Display for DimensionUpperBound {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "dim ≤ {}", self.0)
    }
}

/// Collection of bounds with refinement
#[derive(Clone, Debug)]
pub struct BoundCollection {
    bounds: Vec<(String, DimensionUpperBound)>,
}

impl BoundCollection {
    /// Create empty collection
    pub fn new() -> Self {
        Self {
            bounds: Vec::new(),
        }
    }

    /// Add a bound from generators
    pub fn add_generator_bound(&mut self, num_generators: usize) {
        self.bounds.push((
            format!("generators (n={})", num_generators),
            DimensionUpperBound::from_generators(num_generators),
        ));
    }

    /// Add a bound from relations
    pub fn add_relation_bound(&mut self, num_gen: usize, num_rel: usize) {
        self.bounds.push((
            format!("relations (gen={}, rel={})", num_gen, num_rel),
            DimensionUpperBound::from_relations(num_gen, num_rel),
        ));
    }

    /// Add a bound from ideal saturation
    pub fn add_saturation_bound(&mut self, num_generators: usize) {
        self.bounds.push((
            format!("saturation (n={})", num_generators),
            DimensionUpperBound::from_ideal_saturation(num_generators),
        ));
    }

    /// Add Krull PIT bound
    pub fn add_krull_pit_bound(&mut self, num_generators: usize) {
        self.bounds.push((
            format!("Krull PIT (n={})", num_generators),
            DimensionUpperBound::krull_pit_bound(num_generators),
        ));
    }

    /// Get tightest bound
    pub fn tightest(&self) -> Option<DimensionUpperBound> {
        if self.bounds.is_empty() {
            None
        } else {
            Some(DimensionUpperBound::tightest(
                &self.bounds.iter().map(|(_, b)| *b).collect::<Vec<_>>(),
            ))
        }
    }

    /// Get all bounds
    pub fn all(&self) -> &[(String, DimensionUpperBound)] {
        &self.bounds
    }

    /// Check all bounds are satisfied
    pub fn all_satisfied(&self, actual_dim: KrullDim) -> bool {
        self.bounds.iter().all(|(_, b)| b.satisfies(actual_dim))
    }

    /// Combine the bounds according to `strategy`: the minimum of all bounds,
    /// only generator bounds, only Krull PIT bounds, or (conservatively) the
    /// maximum. `None` if no bound matches.
    pub fn combined(&self, strategy: BoundStrategy) -> Option<DimensionUpperBound> {
        let matching = |prefix: &str| -> Vec<DimensionUpperBound> {
            self.bounds
                .iter()
                .filter(|(label, _)| label.starts_with(prefix))
                .map(|(_, b)| *b)
                .collect()
        };
        let all: Vec<DimensionUpperBound> = self.bounds.iter().map(|(_, b)| *b).collect();
        match strategy {
            BoundStrategy::AllBounds => all.into_iter().min(),
            BoundStrategy::Conservative => all.into_iter().max(),
            BoundStrategy::GeneratorsOnly => matching("generators").into_iter().min(),
            BoundStrategy::KrullPITOnly => matching("Krull PIT").into_iter().min(),
        }
    }
}

impl Default for BoundCollection {
    fn default() -> Self {
        Self::new()
    }
}

/// Strategy for computing bounds
#[derive(Clone, Copy, Debug)]
pub enum BoundStrategy {
    /// Use all available bounds, take minimum
    AllBounds,
    /// Use only generator count
    GeneratorsOnly,
    /// Use only PIT bound
    KrullPITOnly,
    /// Conservative: use maximum of available
    Conservative,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bound_from_generators() {
        let bound = DimensionUpperBound::from_generators(3);
        assert_eq!(bound.bound(), 3);
    }

    #[test]
    fn test_bound_from_relations() {
        let bound = DimensionUpperBound::from_relations(5, 2);
        assert_eq!(bound.bound(), 3);
    }

    #[test]
    fn test_bound_satisfies() {
        let bound = DimensionUpperBound::from_generators(3);
        let dim = KrullDim(2);
        assert!(bound.satisfies(dim));
    }

    #[test]
    fn test_bound_refine() {
        let mut bound = DimensionUpperBound::from_generators(5);
        bound.refine(DimensionUpperBound::from_generators(3));
        assert_eq!(bound.bound(), 3);
    }

    #[test]
    fn test_bound_collection() {
        let mut coll = BoundCollection::new();
        coll.add_generator_bound(4);
        coll.add_relation_bound(4, 1);

        assert!(coll.tightest().is_some());
        assert_eq!(coll.tightest().unwrap().bound(), 3);
    }

    #[test]
    fn test_bound_collection_all_satisfied() {
        let mut coll = BoundCollection::new();
        coll.add_generator_bound(4);
        let dim = KrullDim(3);
        assert!(coll.all_satisfied(dim));
    }

    #[test]
    fn strategies_select_bounds() {
        let mut coll = BoundCollection::new();
        coll.add_generator_bound(4);
        coll.add_krull_pit_bound(2);
        coll.add_relation_bound(5, 2);
        assert_eq!(coll.combined(BoundStrategy::AllBounds), Some(DimensionUpperBound(2)));
        assert_eq!(coll.combined(BoundStrategy::Conservative), Some(DimensionUpperBound(4)));
        assert_eq!(coll.combined(BoundStrategy::GeneratorsOnly), Some(DimensionUpperBound(4)));
        assert_eq!(coll.combined(BoundStrategy::KrullPITOnly), Some(DimensionUpperBound(2)));
        assert_eq!(BoundCollection::new().combined(BoundStrategy::AllBounds), None);
    }

    #[test]
    fn test_krull_pit_bound() {
        let bound = DimensionUpperBound::krull_pit_bound(2);
        assert_eq!(bound.bound(), 2);
    }

    #[test]
    fn test_integral_extension_bound() {
        let dim = KrullDim(3);
        let bound = DimensionUpperBound::integral_extension_bound(dim);
        assert_eq!(bound.bound(), 3);
    }
}
