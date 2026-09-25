//! projective_resolution
//!
//! Projective resolutions of modules over Z. A projective resolution of a
//! module M is an exact sequence
//!
//! `… → P_2 → P_1 → P_0 → M → 0`
//!
//! where each `P_i` is projective (over a PID: free of finite rank).
//!
//! Conventions:
//!
//! * `modules[i]` is `P_i`.
//! * `differentials[k]` is `d_{k+1}: P_{k+1} → P_k` (source `modules[k+1]`,
//!   target `modules[k]`).
//! * If an augmentation `ε: P_0 → M` is set, `M` is the free target of `ε`.
//!   If no augmentation is set, the resolution is a *presentation*: `M` is
//!   defined as `coker(d_1)` and `ε` is the quotient map, so the sequence is
//!   exact at `P_0` by construction.
//!
//! Exactness is decided exactly with Smith normal form: the homology at
//! `P_i` has free rank `rank P_i − rank(out) − rank(d_{i+1})` and torsion
//! given by the non-unit invariant factors of `d_{i+1}`.

#![warn(missing_docs)]

use chain_complex_shape::integer_matrix::{self, SmithForm};
pub use chain_complex_shape::integer_matrix as matrix_ops;
use chain_complex_shape::{ChainComplexShape, ChainDegreeShape};
use chain_complex_types::ChainElement;
pub use projective_module_definition::{ProjectiveModule, ProjectiveModuleHomomorphism};

/// Homology of the augmented complex at one position: `Z^free_rank ⊕
/// ⊕ Z/t` for `t` in `torsion`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolutionHomology {
    /// Free rank.
    pub free_rank: usize,
    /// Torsion coefficients (each > 1).
    pub torsion: Vec<u64>,
}

impl ResolutionHomology {
    /// Zero homology (exactness).
    pub fn is_zero(&self) -> bool {
        self.free_rank == 0 && self.torsion.is_empty()
    }
}

/// A projective resolution of a module M.
#[derive(Debug, Clone)]
pub struct ProjectiveResolution {
    modules: Vec<ProjectiveModule>,
    differentials: Vec<ProjectiveModuleHomomorphism>,
    /// The augmentation `ε: P_0 → M`, if M is free; `None` means M = coker(d_1).
    pub augmentation: Option<ProjectiveModuleHomomorphism>,
    is_exact: bool,
}

fn smith(h: &ProjectiveModuleHomomorphism) -> Result<SmithForm, String> {
    h.smith_form().map_err(|e| format!("exact arithmetic failed: {e}"))
}

impl ProjectiveResolution {
    /// An empty resolution.
    pub fn new() -> Self {
        Self {
            modules: Vec::new(),
            differentials: Vec::new(),
            augmentation: None,
            is_exact: false,
        }
    }

    /// Append `P_{len}`.
    pub fn add_module(&mut self, module: ProjectiveModule) {
        self.modules.push(module);
    }

    /// Append the next differential `d_{k+1}: P_{k+1} → P_k` (k = number of
    /// differentials already added).
    pub fn add_differential(&mut self, diff: ProjectiveModuleHomomorphism) {
        self.differentials.push(diff);
    }

    /// Set the augmentation `ε: P_0 → M`.
    pub fn set_augmentation(&mut self, aug: ProjectiveModuleHomomorphism) {
        self.augmentation = Some(aug);
    }

    /// `P_i`.
    pub fn module_at(&self, i: usize) -> Option<&ProjectiveModule> {
        self.modules.get(i)
    }

    /// `differentials[k]`, i.e. `d_{k+1}: P_{k+1} → P_k`.
    pub fn differential_at(&self, k: usize) -> Option<&ProjectiveModuleHomomorphism> {
        self.differentials.get(k)
    }

    /// `d_i: P_i → P_{i-1}` for `i ≥ 1`.
    pub fn d(&self, i: usize) -> Option<&ProjectiveModuleHomomorphism> {
        i.checked_sub(1).and_then(|k| self.differentials.get(k))
    }

    /// Number of differentials.
    pub fn differentials_len(&self) -> usize {
        self.differentials.len()
    }

    /// Number of modules.
    pub fn len(&self) -> usize {
        self.modules.len()
    }

    /// No modules?
    pub fn is_empty(&self) -> bool {
        self.modules.is_empty()
    }

    /// Rank of `P_i` (0 past the end).
    pub fn rank_at(&self, i: usize) -> usize {
        self.modules.get(i).map(|m| m.rank).unwrap_or(0)
    }

    /// Check that there is one differential per adjacent pair of modules and
    /// that every map's source and target ranks match its modules.
    pub fn check_structure(&self) -> Result<(), String> {
        if self.modules.is_empty() {
            return Err("resolution has no modules".into());
        }
        if self.differentials.len() != self.modules.len() - 1 {
            return Err(format!(
                "{} modules need {} differentials, found {}",
                self.modules.len(),
                self.modules.len() - 1,
                self.differentials.len()
            ));
        }
        for (k, d) in self.differentials.iter().enumerate() {
            if d.source.rank != self.modules[k + 1].rank || d.target.rank != self.modules[k].rank {
                return Err(format!(
                    "d_{} must map rank {} → rank {}, found {} → {}",
                    k + 1,
                    self.modules[k + 1].rank,
                    self.modules[k].rank,
                    d.source.rank,
                    d.target.rank
                ));
            }
        }
        if let Some(e) = &self.augmentation {
            if e.source.rank != self.modules[0].rank {
                return Err(format!(
                    "augmentation source rank {} ≠ rank P_0 = {}",
                    e.source.rank, self.modules[0].rank
                ));
            }
        }
        Ok(())
    }

    /// Is the composite of the map out of `P_i` with `d_{i+1}` zero? For
    /// `i = 0` this is `ε ∘ d_1` (vacuous without an augmentation).
    pub fn composition_is_zero(&self, i: usize) -> Result<bool, String> {
        let outgoing = if i == 0 { self.augmentation.as_ref() } else { self.d(i) };
        let (Some(out), Some(inc)) = (outgoing, self.differentials.get(i)) else {
            return Ok(true);
        };
        let product = integer_matrix::multiply(out.matrix(), out.source.rank, inc.matrix(), inc.source.rank)
            .map_err(|e| format!("composition at P_{i}: {e}"))?;
        Ok(integer_matrix::is_zero(&product))
    }

    /// Homology of the augmented complex at `P_i`. Errors if the structure
    /// is inconsistent or the composite through `P_i` is non-zero.
    pub fn homology_at(&self, i: usize) -> Result<ResolutionHomology, String> {
        self.check_structure()?;
        if i >= self.modules.len() {
            return Err(format!("P_{i} does not exist"));
        }
        if i == 0 && self.augmentation.is_none() {
            return Ok(ResolutionHomology { free_rank: 0, torsion: Vec::new() });
        }
        if !self.composition_is_zero(i)? {
            return Err(format!("not a complex at P_{i}: composite through P_{i} is non-zero"));
        }
        let outgoing = if i == 0 { self.augmentation.as_ref() } else { self.d(i) };
        let out_rank = match outgoing {
            Some(h) => smith(h)?.rank(),
            None => 0,
        };
        let (in_rank, torsion) = match self.differentials.get(i) {
            Some(h) => {
                let s = smith(h)?;
                (s.rank(), s.torsion())
            }
            None => (0, Vec::new()),
        };
        let free_rank = self.modules[i]
            .rank
            .checked_sub(out_rank + in_rank)
            .ok_or_else(|| format!("ranks through P_{i} exceed rank P_{i}"))?;
        Ok(ResolutionHomology { free_rank, torsion })
    }

    /// Is the augmented complex exact at `P_i`?
    pub fn is_exact_at(&self, i: usize) -> bool {
        self.homology_at(i).map(|h| h.is_zero()).unwrap_or(false)
    }

    /// Is the augmentation surjective? Always true for a presentation
    /// (implicit quotient map).
    pub fn augmentation_is_surjective(&self) -> Result<bool, String> {
        match &self.augmentation {
            None => Ok(true),
            Some(e) => {
                let s = smith(e)?;
                Ok(s.rank() == e.target.rank && s.is_torsion_free())
            }
        }
    }

    /// The module being resolved: `coker(d_1)` for a presentation, or the
    /// free target of the augmentation.
    pub fn resolved_module(&self) -> Result<ResolutionHomology, String> {
        self.check_structure()?;
        match (&self.augmentation, self.differentials.first()) {
            (Some(e), _) => Ok(ResolutionHomology { free_rank: e.target.rank, torsion: Vec::new() }),
            (None, None) => Ok(ResolutionHomology { free_rank: self.modules[0].rank, torsion: Vec::new() }),
            (None, Some(d1)) => {
                let s = smith(d1)?;
                Ok(ResolutionHomology {
                    free_rank: self.modules[0].rank - s.rank(),
                    torsion: s.torsion(),
                })
            }
        }
    }

    /// A Z-basis of the kernel of the map leaving `P_i`: `d_i` for `i ≥ 1`,
    /// `ε` for `i = 0` (empty when no augmentation is set).
    pub fn kernel_at(&self, i: usize) -> Vec<ChainElement> {
        let map = if i == 0 { self.augmentation.as_ref() } else { self.d(i) };
        let (Some(map), Some(module)) = (map, self.modules.get(i)) else {
            return Vec::new();
        };
        let Ok(snf) = map.smith_form() else {
            return Vec::new();
        };
        snf.kernel_basis
            .iter()
            .map(|v| {
                let mut e = ChainElement::new(module.degree);
                for (idx, &c) in v.iter().enumerate() {
                    if c != 0 {
                        e.set_coeff(idx, c);
                    }
                }
                e
            })
            .collect()
    }

    /// Images in `P_i` of the generators of `P_{i+1}` under `d_{i+1}`.
    pub fn image_at(&self, i: usize) -> Vec<ChainElement> {
        let Some(diff) = self.differentials.get(i) else {
            return Vec::new();
        };
        (0..diff.source.rank)
            .map(|g| {
                let mut elem = ChainElement::new(diff.source.degree);
                elem.set_coeff(g, 1);
                diff.apply(&elem)
            })
            .collect()
    }

    /// Check exactness everywhere and surjectivity of the augmentation, and
    /// record the result.
    pub fn verify_exactness(&mut self) -> bool {
        let exact = self.check_structure().is_ok()
            && (0..self.len()).all(|i| self.is_exact_at(i))
            && self.augmentation_is_surjective().unwrap_or(false);
        self.is_exact = exact;
        exact
    }

    /// Record exactness established elsewhere.
    pub fn mark_exact(&mut self, exact: bool) {
        self.is_exact = exact;
    }

    /// Recorded exactness.
    pub fn is_marked_exact(&self) -> bool {
        self.is_exact
    }

    /// Resolution of the free module Z: `0 → Z --id--> Z → 0`.
    pub fn free_of_rank_one() -> Self {
        let mut res = Self::new();
        let p0 = ProjectiveModule::new(1, 0);
        res.add_module(p0.clone());
        res.set_augmentation(ProjectiveModuleHomomorphism::new(p0.clone(), p0, vec![vec![1]]));
        res.mark_exact(true);
        res
    }

    /// Presentation of the cyclic group Z/n: `0 → Z --·n--> Z → Z/n → 0`.
    /// For `n = 0` (Z/0 = Z) the resolution is just `P_0 = Z`.
    pub fn cyclic_resolution(n: i64) -> Self {
        let mut res = Self::new();
        let p0 = ProjectiveModule::new(1, 0);
        res.add_module(p0.clone());
        if n != 0 {
            let p1 = ProjectiveModule::new(1, 1);
            res.add_module(p1.clone());
            res.add_differential(ProjectiveModuleHomomorphism::new(p1, p0, vec![vec![n]]));
        }
        res.verify_exactness();
        res
    }

    /// The chain complex shape, with `P_i` at degree `-i`.
    pub fn to_chain_shape(&self) -> ChainComplexShape {
        let mut shape = ChainComplexShape::new();
        for (i, module) in self.modules.iter().enumerate() {
            shape.add_degree(ChainDegreeShape::new(-(i as i32), module.rank));
        }
        shape
    }

    /// One-line summary.
    pub fn summary(&self) -> String {
        let ranks: Vec<_> = self.modules.iter().map(|m| m.rank).collect();
        format!(
            "ProjectiveResolution {{ ranks: {:?}, differentials: {}, exact: {} }}",
            ranks,
            self.differentials.len(),
            self.is_exact
        )
    }
}

impl Default for ProjectiveResolution {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hom(src: &ProjectiveModule, tgt: &ProjectiveModule, m: Vec<Vec<i64>>) -> ProjectiveModuleHomomorphism {
        ProjectiveModuleHomomorphism::new(src.clone(), tgt.clone(), m)
    }

    #[test]
    fn test_projective_resolution_new() {
        let res = ProjectiveResolution::new();
        assert!(res.is_empty());
        assert!(res.check_structure().is_err());
    }

    #[test]
    fn test_projective_resolution_add_module() {
        let mut res = ProjectiveResolution::new();
        res.add_module(ProjectiveModule::new(2, 0));
        assert_eq!(res.len(), 1);
        assert_eq!(res.rank_at(0), 2);
    }

    #[test]
    fn free_rank_one_is_exact() {
        let mut res = ProjectiveResolution::free_of_rank_one();
        assert_eq!(res.len(), 1);
        assert!(res.is_exact_at(0));
        assert!(res.verify_exactness());
        assert_eq!(res.resolved_module().unwrap(), ResolutionHomology { free_rank: 1, torsion: vec![] });
    }

    #[test]
    fn cyclic_resolution_resolves_z_mod_n() {
        let res = ProjectiveResolution::cyclic_resolution(6);
        assert_eq!(res.len(), 2);
        assert!(res.is_marked_exact());
        assert!(res.is_exact_at(0) && res.is_exact_at(1));
        assert_eq!(res.resolved_module().unwrap(), ResolutionHomology { free_rank: 0, torsion: vec![6] });
        let z = ProjectiveResolution::cyclic_resolution(0);
        assert_eq!(z.resolved_module().unwrap().free_rank, 1);
        assert!(z.is_marked_exact());
    }

    #[test]
    fn longer_exact_resolution_of_zero() {
        let (p0, p1, p2) = (ProjectiveModule::new(1, 0), ProjectiveModule::new(2, 1), ProjectiveModule::new(1, 2));
        let mut res = ProjectiveResolution::new();
        res.add_module(p0.clone());
        res.add_module(p1.clone());
        res.add_module(p2.clone());
        res.add_differential(hom(&p1, &p0, vec![vec![0, 1]]));
        res.add_differential(hom(&p2, &p1, vec![vec![1], vec![0]]));
        assert!(res.composition_is_zero(1).unwrap());
        assert!(res.verify_exactness());
        assert!(res.resolved_module().unwrap().is_zero());
    }

    #[test]
    fn non_exact_and_non_complex_are_detected() {
        let (p0, p1) = (ProjectiveModule::new(1, 0), ProjectiveModule::new(1, 1));
        let mut zero_map = ProjectiveResolution::new();
        zero_map.add_module(p0.clone());
        zero_map.add_module(p1.clone());
        zero_map.add_differential(hom(&p1, &p0, vec![vec![0]]));
        assert_eq!(zero_map.homology_at(1).unwrap(), ResolutionHomology { free_rank: 1, torsion: vec![] });
        assert!(!zero_map.verify_exactness());

        let p2 = ProjectiveModule::new(1, 2);
        let mut not_complex = ProjectiveResolution::new();
        not_complex.add_module(p0.clone());
        not_complex.add_module(p1.clone());
        not_complex.add_module(p2.clone());
        not_complex.add_differential(hom(&p1, &p0, vec![vec![2]]));
        not_complex.add_differential(hom(&p2, &p1, vec![vec![3]]));
        assert!(!not_complex.composition_is_zero(1).unwrap());
        assert!(not_complex.homology_at(1).is_err());
        assert!(!not_complex.is_exact_at(1));
    }

    #[test]
    fn augmentation_checks() {
        let p0 = ProjectiveModule::new(2, 0);
        let m = ProjectiveModule::new(1, 0);
        let mut res = ProjectiveResolution::new();
        res.add_module(p0.clone());
        res.set_augmentation(hom(&p0, &m, vec![vec![2, 0]]));
        assert_eq!(res.augmentation_is_surjective(), Ok(false));
        assert!(!res.is_exact_at(0));
        res.set_augmentation(hom(&p0, &m, vec![vec![1, 1]]));
        assert_eq!(res.augmentation_is_surjective(), Ok(true));
        assert_eq!(res.homology_at(0).unwrap().free_rank, 1);
    }

    #[test]
    fn structure_mismatch_is_reported() {
        let (p0, p1) = (ProjectiveModule::new(1, 0), ProjectiveModule::new(2, 1));
        let wrong = ProjectiveModule::new(3, 1);
        let mut res = ProjectiveResolution::new();
        res.add_module(p0.clone());
        res.add_module(p1);
        res.add_differential(hom(&wrong, &p0, vec![vec![1, 0, 0]]));
        assert!(res.check_structure().is_err());
        assert!(!res.verify_exactness());
    }

    #[test]
    fn kernel_and_image() {
        let (p0, p1) = (ProjectiveModule::new(1, 0), ProjectiveModule::new(2, 1));
        let mut res = ProjectiveResolution::new();
        res.add_module(p0.clone());
        res.add_module(p1.clone());
        res.add_differential(hom(&p1, &p0, vec![vec![2, 4]]));
        let kernel = res.kernel_at(1);
        assert_eq!(kernel.len(), 1);
        let d1 = res.d(1).unwrap();
        assert!(d1.apply(&kernel[0]).is_zero());
        let image = res.image_at(0);
        assert_eq!(image.len(), 2);
        assert_eq!((image[0].coeff(0), image[1].coeff(0)), (2, 4));
        assert_eq!(res.homology_at(1).unwrap().free_rank, 1);
    }

    #[test]
    fn test_projective_resolution_to_chain_shape() {
        let mut res = ProjectiveResolution::new();
        res.add_module(ProjectiveModule::new(2, 0));
        res.add_module(ProjectiveModule::new(3, 0));
        let shape = res.to_chain_shape();
        assert_eq!(shape.rank_at(0), 2);
        assert_eq!(shape.rank_at(-1), 3);
    }
}
