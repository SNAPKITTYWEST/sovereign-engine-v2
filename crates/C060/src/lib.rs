//! tor_tests_integration
//!
//! Integration tests for the complete Tor functor tier (C051-C060).

#![warn(missing_docs)]

pub use tor_functor_definition::TorComputation;
pub use tensor_product_module::TensorProductModule;
pub use resolution_tensored::TensoredComplex;
pub use derived_homology::compute_tor_from_resolution;
pub use tor_zero_structure::analyze_tor_zero;
pub use tor_higher_degrees::is_short_exact_sequence;
pub use functoriality_of_tor::ModuleMap;
pub use tor_invariants_computation::compute_betti_numbers;
pub use tor_chain_complex_interface::TorChainComplexData;

/// Full Tier 5 (Tor Functor) integration test
pub fn tier5_integration_test() -> bool {
    // 1. Create a tensor product module
    let module = TensorProductModule::new(2, 3);
    if module.free_rank() != 6 {
        return false;
    }

    // 2. Create a tensored complex
    let complex = TensoredComplex::new(vec![2, 3, 2], 4);
    if complex.total_rank() != 28 {
        return false;
    }

    // 3. Create Tor computation
    let tor = TorComputation::new();
    if !tor.groups.is_empty() {
        return false; // Should be empty initially
    }

    // 4. Test Tor_0 analysis
    let tor_0 = analyze_tor_zero(&module);
    if tor_0.rank != 6 {
        return false;
    }

    // 5. Test functoriality with module maps
    let map = ModuleMap::new(2, 3);
    if map.source_rank != 2 || map.target_rank != 3 {
        return false;
    }

    // 6. Test Betti number computation
    let betti = compute_betti_numbers(&tor);
    if betti.total_rank() != 0 {
        return false; // Empty tor, so total rank is 0
    }

    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tier5_tensor_product_module() {
        let module = TensorProductModule::new(3, 2);
        assert_eq!(module.free_rank(), 6);
        assert_eq!(module.basis_generators().len(), 6);
    }

    #[test]
    fn test_tier5_tensored_complex() {
        let complex = TensoredComplex::new(vec![1, 2, 1], 3);
        assert_eq!(complex.tensored_rank(0), Some(3));
        assert_eq!(complex.tensored_rank(1), Some(6));
        assert_eq!(complex.total_rank(), 12);
    }

    #[test]
    fn test_tier5_tor_computation() {
        let tor = TorComputation::new();
        assert!(tor.groups.is_empty());
        assert!(tor.is_split_exact());
    }

    #[test]
    fn test_tier5_tor_zero() {
        let module = TensorProductModule::new(2, 3);
        let tor_0 = analyze_tor_zero(&module);
        assert_eq!(tor_0.rank, 6);
        assert!(tor_0.torsion.is_empty());
    }

    #[test]
    fn test_tier5_module_map() {
        let mut map = ModuleMap::new(2, 3);
        map.set(0, 0, 1);
        map.set(1, 1, 1);
        assert!(map.is_injective());
    }

    #[test]
    fn test_tier5_betti_numbers() {
        let tor = TorComputation::new();
        let betti = compute_betti_numbers(&tor);
        assert_eq!(betti.total_rank(), 0);
    }

    #[test]
    fn test_tier5_integration() {
        assert!(tier5_integration_test());
    }
}

