//! derived_homology
//!
//! Tor groups as homology of the tensored complex:
//! `Tor_n(M, N) = H_n(Tot(P ⊗ Q))` for free resolutions `P → M`, `Q → N`.
//! Homology is computed exactly (Smith normal form), so torsion in Tor is
//! found, e.g. `Tor_1(Z/4, Z/6) = Z/2`.

#![warn(missing_docs)]

pub use homology_computation::HomologyGroup;
use homology_computation::HomologyComputer;
pub use resolution_tensored::TensoredComplex;
pub use tensor_product_module::TensorProductModule;
pub use tor_functor_definition::{ProjectiveResolution, TorComputation, TorGroup, TorIndex};

/// Tor groups of a tensored complex: `Tor_n = H_n(complex)` for every degree
/// of the complex.
pub fn compute_tor_from_resolution(complex: &TensoredComplex) -> Result<TorComputation, String> {
    let mut tor = TorComputation::new();
    for n in 0..complex.num_degrees() {
        let h = HomologyComputer::compute_at_degree(complex.operator(), n as i32)
            .map_err(|e| format!("H_{n}: {e}"))?;
        tor.insert_tor(n, TorGroup::from_homology(TorIndex::new(n), &h));
    }
    Ok(tor)
}

/// Ranks and differential matrices of a resolution, in the layout used by
/// [`TensoredComplex::from_complexes`].
pub fn resolution_data(r: &ProjectiveResolution) -> (Vec<usize>, Vec<Vec<Vec<i64>>>) {
    let ranks = (0..r.len()).map(|i| r.rank_at(i)).collect();
    let diffs = (0..r.differentials_len())
        .filter_map(|k| r.differential_at(k))
        .map(|d| d.matrix().to_vec())
        .collect();
    (ranks, diffs)
}

fn require_resolution(name: &str, r: &ProjectiveResolution) -> Result<(), String> {
    r.check_structure().map_err(|e| format!("{name}: {e}"))?;
    if let Some(i) = (0..r.len()).find(|&i| !r.is_exact_at(i)) {
        return Err(format!("{name} is not exact at P_{i}"));
    }
    if !r.augmentation_is_surjective()? {
        return Err(format!("{name}: augmentation is not surjective"));
    }
    Ok(())
}

/// `Tot(P ⊗ Q)` for two exact resolutions.
pub fn tensor_resolutions(
    p: &ProjectiveResolution,
    q: &ProjectiveResolution,
) -> Result<TensoredComplex, String> {
    require_resolution("resolution of M", p)?;
    require_resolution("resolution of N", q)?;
    let (p_ranks, p_diffs) = resolution_data(p);
    let (q_ranks, q_diffs) = resolution_data(q);
    TensoredComplex::from_complexes(p_ranks, &p_diffs, q_ranks, &q_diffs)
}

/// `Tor_*(M, N)` for modules given by exact resolutions.
pub fn tor_of(p: &ProjectiveResolution, q: &ProjectiveResolution) -> Result<TorComputation, String> {
    compute_tor_from_resolution(&tensor_resolutions(p, q)?)
}

/// Recompute Tor from the complex and compare with `tor`.
pub fn verify_tor_computation(complex: &TensoredComplex, tor: &TorComputation) -> bool {
    compute_tor_from_resolution(complex).map_or(false, |expected| &expected == tor)
}

/// Tor groups of the complex in degrees below `max_degree`.
pub fn truncated_tor(complex: &TensoredComplex, max_degree: usize) -> Result<TorComputation, String> {
    let mut tor = compute_tor_from_resolution(complex)?;
    tor.groups.retain(|&degree, _| degree < max_degree);
    Ok(tor)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn z_mod(n: i64) -> ProjectiveResolution {
        ProjectiveResolution::cyclic_resolution(n)
    }

    fn invariants(tor: &TorComputation, n: usize) -> (usize, Vec<u64>) {
        tor.tor(n).map_or((0, vec![]), |g| (g.rank, g.torsion_orders()))
    }

    #[test]
    fn tor_of_cyclic_groups() {
        let tor = tor_of(&z_mod(4), &z_mod(6)).unwrap();
        assert_eq!(invariants(&tor, 0), (0, vec![2]));
        assert_eq!(invariants(&tor, 1), (0, vec![2]));
        assert!(tor.tor(2).unwrap().is_trivial());

        let coprime = tor_of(&z_mod(2), &z_mod(3)).unwrap();
        assert!(coprime.groups.values().all(|g| g.is_trivial()));
    }

    #[test]
    fn tor_with_free_modules() {
        let z = ProjectiveResolution::free_of_rank_one();
        let tor = tor_of(&z_mod(5), &z).unwrap();
        assert_eq!(invariants(&tor, 0), (0, vec![5]));
        assert!(tor.tor(1).unwrap().is_trivial());
        let zz = tor_of(&z, &z).unwrap();
        assert_eq!(invariants(&zz, 0), (1, vec![]));
    }

    #[test]
    fn tor_is_symmetric() {
        let a = tor_of(&z_mod(12), &z_mod(18)).unwrap();
        let b = tor_of(&z_mod(18), &z_mod(12)).unwrap();
        for n in 0..3 {
            assert_eq!(invariants(&a, n), invariants(&b, n));
        }
        assert_eq!(invariants(&a, 0), (0, vec![6]));
    }

    #[test]
    fn verification_and_truncation() {
        let complex = tensor_resolutions(&z_mod(4), &z_mod(6)).unwrap();
        let tor = compute_tor_from_resolution(&complex).unwrap();
        assert!(verify_tor_computation(&complex, &tor));
        let mut wrong = tor.clone();
        wrong.tor_mut(1).unwrap().rank = 1;
        assert!(!verify_tor_computation(&complex, &wrong));
        assert_eq!(truncated_tor(&complex, 1).unwrap().max_degree(), Some(0));
    }

    #[test]
    fn non_resolutions_are_rejected() {
        let mut not_exact = ProjectiveResolution::new();
        let (p0, p1) = (
            tor_functor_definition::ProjectiveModule::new(1, 0),
            tor_functor_definition::ProjectiveModule::new(1, 1),
        );
        not_exact.add_module(p0.clone());
        not_exact.add_module(p1.clone());
        not_exact.add_differential(tor_functor_definition::ProjectiveModuleHomomorphism::new(p1, p0, vec![vec![0]]));
        assert!(tor_of(&not_exact, &z_mod(2)).is_err());
    }
}
