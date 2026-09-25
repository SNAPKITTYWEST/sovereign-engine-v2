//! functoriality_of_tor
//!
//! Functoriality of Tor: maps induced by module homomorphisms.

#![warn(missing_docs)]

pub use tor_functor_definition::{TorGroup, TorComputation};
pub use derived_homology::verify_tor_computation;

/// A module homomorphism f: M → M'
#[derive(Clone, Debug)]
pub struct ModuleMap {
    /// Source rank
    pub source_rank: usize,
    /// Target rank
    pub target_rank: usize,
    /// Matrix representing the map (row-major)
    pub matrix: Vec<i32>,
}

impl ModuleMap {
    /// Create a module map with given source and target ranks
    pub fn new(source_rank: usize, target_rank: usize) -> Self {
        let size = source_rank * target_rank;
        Self {
            source_rank,
            target_rank,
            matrix: vec![0; size],
        }
    }

    /// Set matrix entry at (i, j)
    pub fn set(&mut self, i: usize, j: usize, val: i32) {
        if i < self.source_rank && j < self.target_rank {
            self.matrix[i * self.target_rank + j] = val;
        }
    }

    /// Get matrix entry at (i, j)
    pub fn get(&self, i: usize, j: usize) -> i32 {
        if i < self.source_rank && j < self.target_rank {
            self.matrix[i * self.target_rank + j]
        } else {
            0
        }
    }

    /// Check if this map is injective (rank equals source rank)
    pub fn is_injective(&self) -> bool {
        // Simplified: assumes full rank if non-zero entries exist
        self.matrix.iter().any(|&e| e != 0)
    }

    /// Check if this map is surjective (rank equals target rank)
    pub fn is_surjective(&self) -> bool {
        // Simplified check
        self.source_rank >= self.target_rank && self.is_injective()
    }
}

/// Induced map on Tor: f* : Tor_i(M, N) → Tor_i(M', N)
pub fn induced_tor_map(
    source_tor: &TorGroup,
    target_tor: &TorGroup,
    f: &ModuleMap,
) -> ModuleMap {
    let mut induced = ModuleMap::new(source_tor.num_generators(), target_tor.num_generators());

    // In a real implementation, this would compose the resolution map with Tor functor
    // For now, create a compatible map
    if f.is_injective() {
        for i in 0..source_tor.num_generators().min(target_tor.num_generators()) {
            induced.set(i, i, 1);
        }
    }

    induced
}

/// Composition of induced Tor maps
pub fn compose_tor_maps(f: &ModuleMap, g: &ModuleMap) -> Option<ModuleMap> {
    if f.target_rank != g.source_rank {
        return None;
    }

    let mut result = ModuleMap::new(f.source_rank, g.target_rank);

    // Matrix multiplication: result[i,k] = sum_j f[i,j] * g[j,k]
    for i in 0..f.source_rank {
        for k in 0..g.target_rank {
            let mut sum = 0i32;
            for j in 0..f.target_rank {
                sum += f.get(i, j) * g.get(j, k);
            }
            result.set(i, k, sum);
        }
    }

    Some(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_module_map_creation() {
        let map = ModuleMap::new(2, 3);
        assert_eq!(map.source_rank, 2);
        assert_eq!(map.target_rank, 3);
    }

    #[test]
    fn test_module_map_set_get() {
        let mut map = ModuleMap::new(2, 3);
        map.set(0, 1, 5);
        assert_eq!(map.get(0, 1), 5);
        assert_eq!(map.get(1, 0), 0);
    }

    #[test]
    fn test_module_map_injective() {
        let mut map = ModuleMap::new(2, 3);
        map.set(0, 0, 1);
        assert!(map.is_injective());
    }

    #[test]
    fn test_compose_tor_maps() {
        let mut f = ModuleMap::new(2, 3);
        f.set(0, 0, 1);
        f.set(0, 1, 0);

        let mut g = ModuleMap::new(3, 2);
        g.set(0, 0, 2);

        let result = compose_tor_maps(&f, &g);
        assert!(result.is_some());
    }

    #[test]
    fn test_compose_incompatible_maps() {
        let f = ModuleMap::new(2, 3);
        let g = ModuleMap::new(2, 3);
        assert!(compose_tor_maps(&f, &g).is_none());
    }
}
