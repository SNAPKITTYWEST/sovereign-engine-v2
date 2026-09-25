//! chain_complex_shape
//!
//! Chain complex shape definition: rank, generators, degree information.
//! A chain complex C_* has a rank (number of generators) at each degree n.
//! This crate provides the fundamental shape primitives and operations.

#![warn(missing_docs)]

/// The maximum rank (number of generators) at any degree in a chain complex.
pub const MAX_CHAIN_RANK: usize = 1024;

/// Describes the shape of a chain complex at a single degree n.
///
/// A chain complex is graded; at each degree n we have:
/// - rank: number of free generators (basis elements)
/// - degree: the integer degree value
/// - generators: list of generator descriptors
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChainDegreeShape {
    /// The degree n (can be negative for cohomology).
    pub degree: i32,
    /// Number of generators (rank of free module at this degree).
    pub rank: usize,
    /// Generator labels/identifiers (optional descriptors).
    pub generators: Vec<String>,
}

impl ChainDegreeShape {
    /// Create a new chain degree shape at degree n with given rank.
    ///
    /// # Arguments
    /// * `degree` - The degree n of this component
    /// * `rank` - Number of generators at this degree
    ///
    /// # Panics
    /// Panics if rank > MAX_CHAIN_RANK.
    pub fn new(degree: i32, rank: usize) -> Self {
        assert!(rank <= MAX_CHAIN_RANK, "rank {} exceeds MAX_CHAIN_RANK", rank);
        Self {
            degree,
            rank,
            generators: (0..rank).map(|i| format!("gen_{}", i)).collect(),
        }
    }

    /// Set custom generator names.
    pub fn with_generators(mut self, generators: Vec<String>) -> Self {
        assert_eq!(generators.len(), self.rank, "generator count mismatch");
        self.generators = generators;
        self
    }

    /// Check if this degree has rank 0 (no generators).
    pub fn is_empty(&self) -> bool {
        self.rank == 0
    }

    /// Total rank (number of generators).
    pub fn len(&self) -> usize {
        self.rank
    }
}

/// Full shape of a chain complex: stores rank information at all relevant degrees.
///
/// A chain complex C_* = {C_n, d_n} consists of modules C_n at integer degrees n
/// with differentials d_n: C_n -> C_{n-1}. This struct tracks the shape: which
/// degrees have nonzero modules and their ranks.
#[derive(Debug, Clone)]
pub struct ChainComplexShape {
    /// Minimum degree with nonzero module (can be negative).
    pub min_degree: i32,
    /// Maximum degree with nonzero module.
    pub max_degree: i32,
    /// Shape at each degree: degree -> ChainDegreeShape
    pub degrees: Vec<ChainDegreeShape>,
    /// Total rank summed across all degrees.
    total_rank: usize,
}

impl ChainComplexShape {
    /// Create a new empty chain complex shape.
    pub fn new() -> Self {
        Self {
            min_degree: 0,
            max_degree: -1, // empty
            degrees: Vec::new(),
            total_rank: 0,
        }
    }

    /// Add or update a degree shape.
    pub fn add_degree(&mut self, shape: ChainDegreeShape) {
        if self.degrees.is_empty() {
            self.min_degree = shape.degree;
            self.max_degree = shape.degree;
        } else {
            self.min_degree = self.min_degree.min(shape.degree);
            self.max_degree = self.max_degree.max(shape.degree);
        }
        // Update total rank
        let old_rank = self.degrees
            .iter()
            .find(|d| d.degree == shape.degree)
            .map(|d| d.rank)
            .unwrap_or(0);
        self.total_rank -= old_rank;
        self.total_rank += shape.rank;

        // Replace or insert
        if let Some(pos) = self.degrees.iter().position(|d| d.degree == shape.degree) {
            self.degrees[pos] = shape;
        } else {
            self.degrees.push(shape);
            // Sort by degree for consistency
            self.degrees.sort_by_key(|d| d.degree);
        }
    }

    /// Get the rank at a specific degree.
    pub fn rank_at(&self, degree: i32) -> usize {
        self.degrees
            .iter()
            .find(|d| d.degree == degree)
            .map(|d| d.rank)
            .unwrap_or(0)
    }

    /// Get the shape at a specific degree (if it exists).
    pub fn degree_shape(&self, degree: i32) -> Option<&ChainDegreeShape> {
        self.degrees.iter().find(|d| d.degree == degree)
    }

    /// Check if the complex is empty (no degrees).
    pub fn is_empty(&self) -> bool {
        self.degrees.is_empty()
    }

    /// Number of nonzero degrees.
    pub fn len(&self) -> usize {
        self.degrees.len()
    }

    /// Total rank across all degrees.
    pub fn total_rank(&self) -> usize {
        self.total_rank
    }

    /// Create a chain complex shape for a free module (single generator).
    /// Useful for testing and simple chains.
    pub fn free_module(degree: i32) -> Self {
        let mut shape = Self::new();
        shape.add_degree(ChainDegreeShape::new(degree, 1));
        shape
    }

    /// Create a chain complex from a list of degree/rank pairs.
    pub fn from_ranks(pairs: Vec<(i32, usize)>) -> Self {
        let mut shape = Self::new();
        for (degree, rank) in pairs {
            shape.add_degree(ChainDegreeShape::new(degree, rank));
        }
        shape
    }
}

impl Default for ChainComplexShape {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chain_degree_shape_new() {
        let shape = ChainDegreeShape::new(0, 3);
        assert_eq!(shape.degree, 0);
        assert_eq!(shape.rank, 3);
        assert_eq!(shape.len(), 3);
        assert!(!shape.is_empty());
    }

    #[test]
    fn test_chain_degree_shape_empty() {
        let shape = ChainDegreeShape::new(5, 0);
        assert!(shape.is_empty());
        assert_eq!(shape.len(), 0);
    }

    #[test]
    fn test_chain_complex_shape_add_degree() {
        let mut shape = ChainComplexShape::new();
        assert!(shape.is_empty());
        assert_eq!(shape.total_rank(), 0);

        shape.add_degree(ChainDegreeShape::new(0, 2));
        assert!(!shape.is_empty());
        assert_eq!(shape.len(), 1);
        assert_eq!(shape.rank_at(0), 2);
        assert_eq!(shape.total_rank(), 2);

        shape.add_degree(ChainDegreeShape::new(1, 3));
        assert_eq!(shape.len(), 2);
        assert_eq!(shape.rank_at(1), 3);
        assert_eq!(shape.total_rank(), 5);
        assert_eq!(shape.min_degree, 0);
        assert_eq!(shape.max_degree, 1);
    }

    #[test]
    fn test_chain_complex_shape_negative_degrees() {
        let shape = ChainComplexShape::from_ranks(vec![(-2, 1), (-1, 2), (0, 3)]);
        assert_eq!(shape.len(), 3);
        assert_eq!(shape.min_degree, -2);
        assert_eq!(shape.max_degree, 0);
        assert_eq!(shape.rank_at(-2), 1);
        assert_eq!(shape.rank_at(-1), 2);
        assert_eq!(shape.rank_at(0), 3);
        assert_eq!(shape.total_rank(), 6);
    }

    #[test]
    fn test_chain_complex_shape_free_module() {
        let shape = ChainComplexShape::free_module(5);
        assert_eq!(shape.len(), 1);
        assert_eq!(shape.rank_at(5), 1);
        assert_eq!(shape.min_degree, 5);
        assert_eq!(shape.max_degree, 5);
    }

    #[test]
    fn test_chain_degree_shape_generators() {
        let gen_names = vec!["x".to_string(), "y".to_string()];
        let shape = ChainDegreeShape::new(0, 2).with_generators(gen_names.clone());
        assert_eq!(shape.generators, gen_names);
    }
}
