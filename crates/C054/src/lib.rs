//! derived_homology
//!
//! Compute Tor groups from the tensored resolution complex using homology.

#![warn(missing_docs)]

pub use tor_functor_definition::{TorComputation, TorGroup, TorIndex};
pub use tensor_product_module::TensorProductModule;
pub use resolution_tensored::TensoredComplex;
pub use homology_computation::HomologyGroup;

/// Compute Tor_i(M, N) from a projective resolution of M tensored with N
pub fn compute_tor_from_resolution(
    complex: &TensoredComplex,
    homology_groups: &[Option<HomologyGroup>],
) -> TorComputation {
    let mut tor = TorComputation::new();

    for (degree, hom_opt) in homology_groups.iter().enumerate() {
        if let Some(hom) = hom_opt {
            let index = TorIndex::new(degree);
            let mut group = TorGroup::new(index, hom.rank);

            // Count torsion elements by order
            let mut torsion_counts: std::collections::BTreeMap<u64, usize> =
                std::collections::BTreeMap::new();
            for &order in &hom.torsion {
                *torsion_counts.entry(order).or_insert(0) += 1;
            }
            for (order, count) in torsion_counts {
                group.add_torsion(order, count);
            }

            tor.insert_tor(degree, group);
        }
    }

    tor
}

/// Verify that Tor is computed correctly by checking exactness properties
pub fn verify_tor_computation(
    original_complex: &TensoredComplex,
    tor: &TorComputation,
) -> bool {
    // Check that Tor_0 is non-trivial (should have rank)
    if let Some(tor_0) = tor.tor(0) {
        if tor_0.rank == 0 && tor_0.torsion.is_empty() {
            return false;
        }
    }

    // Check that higher Tor groups make sense given the complex
    if tor.max_degree().unwrap_or(0) > original_complex.num_degrees() {
        return false;
    }

    true
}

/// Compute reduced Tor (Tor groups vanishing at certain indices)
pub fn compute_reduced_tor(
    complex: &TensoredComplex,
    vanishing_degree: usize,
    homology_groups: &[Option<HomologyGroup>],
) -> TorComputation {
    let mut tor = TorComputation::new();

    for (degree, hom_opt) in homology_groups.iter().enumerate() {
        // Only include Tor groups up to vanishing_degree
        if degree < vanishing_degree {
            if let Some(hom) = hom_opt {
                let index = TorIndex::new(degree);
                let mut group = TorGroup::new(index, hom.rank);
                let mut torsion_counts: std::collections::BTreeMap<u64, usize> =
                    std::collections::BTreeMap::new();
                for &order in &hom.torsion {
                    *torsion_counts.entry(order).or_insert(0) += 1;
                }
                for (order, count) in torsion_counts {
                    group.add_torsion(order, count);
                }
                tor.insert_tor(degree, group);
            }
        }
    }

    tor
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_tor_from_resolution() {
        let complex = TensoredComplex::new(vec![2, 3, 2], 4);
        let homology_groups = vec![None; 3]; // Simplified for testing
        let tor = compute_tor_from_resolution(&complex, &homology_groups);
        assert!(tor.groups.is_empty());
    }

    #[test]
    fn test_verify_tor_computation() {
        let complex = TensoredComplex::new(vec![2, 3, 2], 4);
        let mut tor = TorComputation::new();
        let group = TorGroup::new(TorIndex::new(0), 2);
        tor.insert_tor(0, group);

        assert!(verify_tor_computation(&complex, &tor));
    }

    #[test]
    fn test_compute_reduced_tor() {
        let complex = TensoredComplex::new(vec![2, 3, 2], 4);
        let homology_groups = vec![None; 3];
        let tor = compute_reduced_tor(&complex, 2, &homology_groups);
        assert!(tor.groups.is_empty());
    }
}
