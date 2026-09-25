//! tor_zero_structure
//!
//! `Tor_0(M, N) = M ⊗ N`. This crate computes `M ⊗ N` directly from
//! presentations and cross-checks it against `Tor_0` computed as homology of
//! the tensored resolution — two independent computations that must agree.

#![warn(missing_docs)]

pub use derived_homology::verify_tor_computation;
use derived_homology::tor_of;
pub use tensor_product_module::TensorProductModule;
pub use tor_functor_definition::{ProjectiveResolution, TorGroup, TorIndex};

/// Summary of `Tor_0`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Tor0Properties {
    /// Is Tor_0 free (no torsion)?
    pub is_free: bool,
    /// Free rank of Tor_0
    pub rank: usize,
}

impl Tor0Properties {
    /// Create Tor_0 properties
    pub fn new(rank: usize, has_torsion: bool) -> Self {
        Self {
            is_free: !has_torsion,
            rank,
        }
    }

    /// Properties of a computed `Tor_0` group.
    pub fn from_group(group: &TorGroup) -> Self {
        Self::new(group.rank, !group.torsion.is_empty())
    }

    /// Check if Tor_0 is the trivial group
    pub fn is_trivial(&self) -> bool {
        self.rank == 0 && self.is_free
    }
}

/// `Tor_0(M, N) = M ⊗ N` from a tensor product module, respecting its
/// relations.
pub fn analyze_tor_zero(module: &TensorProductModule) -> Result<TorGroup, String> {
    let (rank, torsion) = module.quotient_structure().map_err(|e| e.to_string())?;
    Ok(TorGroup::from_invariants(TorIndex::new(0), rank, &torsion))
}

/// Presentation `(generators, relation matrix, relation count)` of the
/// module a resolution resolves.
pub fn presentation(r: &ProjectiveResolution) -> (usize, Vec<Vec<i64>>, usize) {
    match (&r.augmentation, r.differential_at(0)) {
        (Some(e), _) => (e.target.rank, vec![Vec::new(); e.target.rank], 0),
        (None, Some(d1)) => (r.rank_at(0), d1.matrix().to_vec(), d1.source.rank),
        (None, None) => (r.rank_at(0), vec![Vec::new(); r.rank_at(0)], 0),
    }
}

/// `M ⊗ N` built from the presentations of the resolved modules.
pub fn tensor_of_presentations(
    p: &ProjectiveResolution,
    q: &ProjectiveResolution,
) -> Result<TensorProductModule, String> {
    let (m, a, a_cols) = presentation(p);
    let (n, b, b_cols) = presentation(q);
    TensorProductModule::from_presentations(m, &a, a_cols, n, &b, b_cols).map_err(|e| e.to_string())
}

/// Check the defining property `Tor_0(M, N) ≅ M ⊗ N`: `Tor_0` computed as
/// homology of `Tot(P ⊗ Q)` must equal `M ⊗ N` computed from presentations.
pub fn verify_tor_zero_universal_property(
    p: &ProjectiveResolution,
    q: &ProjectiveResolution,
) -> Result<bool, String> {
    let tor0 = tor_of(p, q)?
        .tor(0)
        .cloned()
        .unwrap_or_else(|| TorGroup::new(TorIndex::new(0), 0));
    let tensor = analyze_tor_zero(&tensor_of_presentations(p, q)?)?;
    Ok(tor0 == tensor)
}

/// `Tor_0(Z^m, Z^n) = Z^{mn}` for free modules.
pub fn compute_tor_zero_from_ranks(rank_m: usize, rank_n: usize) -> TorGroup {
    TorGroup::new(TorIndex::new(0), rank_m * rank_n)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tor0_properties() {
        let props = Tor0Properties::new(0, false);
        assert!(props.is_trivial());
        let props = Tor0Properties::new(3, true);
        assert!(!props.is_trivial());
        assert!(!props.is_free);
    }

    #[test]
    fn free_tensor_products() {
        let group = analyze_tor_zero(&TensorProductModule::new(2, 3)).unwrap();
        assert_eq!(group.rank, 6);
        assert!(group.torsion.is_empty());
        assert_eq!(compute_tor_zero_from_ranks(2, 3), group);
    }

    #[test]
    fn tor_zero_agrees_with_tensor_product() {
        let cases = [(4, 6), (2, 3), (12, 18), (5, 0), (0, 0), (7, 7)];
        for (m, n) in cases {
            let p = ProjectiveResolution::cyclic_resolution(m);
            let q = ProjectiveResolution::cyclic_resolution(n);
            assert_eq!(verify_tor_zero_universal_property(&p, &q), Ok(true), "Z/{m} ⊗ Z/{n}");
        }
        let z = ProjectiveResolution::free_of_rank_one();
        let p = ProjectiveResolution::cyclic_resolution(9);
        assert_eq!(verify_tor_zero_universal_property(&p, &z), Ok(true));
    }

    #[test]
    fn tensor_of_cyclic_groups_is_cyclic_of_gcd() {
        let p = ProjectiveResolution::cyclic_resolution(12);
        let q = ProjectiveResolution::cyclic_resolution(18);
        let group = analyze_tor_zero(&tensor_of_presentations(&p, &q).unwrap()).unwrap();
        assert_eq!(group.torsion_orders(), vec![6]);
        assert_eq!(Tor0Properties::from_group(&group), Tor0Properties::new(0, true));
    }
}
