//! resolution_certification
//!
//! Certification that a projective resolution is valid. Each level is only
//! granted after the corresponding check actually passes:
//!
//! 1. **Basic** — one differential per adjacent pair of modules, with source
//!    and target ranks matching the modules.
//! 2. **SquaredZeroVerified** — every composite `d_i ∘ d_{i+1}` (and
//!    `ε ∘ d_1`) is the zero matrix, computed exactly.
//! 3. **ExactnessVerified** — the augmented complex has zero homology at
//!    every `P_i` (ranks and torsion via Smith normal form).
//! 4. **FullyCertified** — the augmentation is surjective (or implicit: the
//!    quotient map onto `coker d_1`).

#![warn(missing_docs)]

pub use projective_resolution::{ProjectiveModule, ProjectiveModuleHomomorphism, ProjectiveResolution};

/// Certification level for a projective resolution.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CertificationLevel {
    /// Not certified.
    Uncertified,
    /// Basic checks passed (structurally sound).
    Basic,
    /// Differential squares to zero verified.
    SquaredZeroVerified,
    /// Exactness verified (homologically valid).
    ExactnessVerified,
    /// Full certification (all checks passed).
    FullyCertified,
}

impl CertificationLevel {
    /// Check if this level includes full certification.
    pub fn is_fully_certified(self) -> bool {
        self == CertificationLevel::FullyCertified
    }

    /// Pretty-print the level.
    pub fn to_string(self) -> &'static str {
        match self {
            CertificationLevel::Uncertified => "Uncertified",
            CertificationLevel::Basic => "Basic",
            CertificationLevel::SquaredZeroVerified => "SquaredZeroVerified",
            CertificationLevel::ExactnessVerified => "ExactnessVerified",
            CertificationLevel::FullyCertified => "FullyCertified",
        }
    }
}

/// Certification report for a projective resolution.
#[derive(Debug, Clone)]
pub struct ResolutionCertificate {
    /// The resolution being certified.
    pub resolution_len: usize,
    /// Certification level achieved.
    pub level: CertificationLevel,
    /// Number of modules checked.
    pub modules_checked: usize,
    /// Number of differentials checked.
    pub differentials_checked: usize,
    /// Whether d² = 0 was verified.
    pub squared_zero_verified: bool,
    /// Whether exactness was verified.
    pub exactness_verified: bool,
    /// Whether augmentation is valid.
    pub augmentation_valid: bool,
    /// Detailed message.
    pub message: String,
}

impl ResolutionCertificate {
    /// Create a new certificate.
    pub fn new(resolution_len: usize) -> Self {
        Self {
            resolution_len,
            level: CertificationLevel::Uncertified,
            modules_checked: 0,
            differentials_checked: 0,
            squared_zero_verified: false,
            exactness_verified: false,
            augmentation_valid: false,
            message: String::new(),
        }
    }

    /// Mark as basic certified.
    pub fn mark_basic(mut self) -> Self {
        self.level = CertificationLevel::Basic;
        self
    }

    /// Mark d² = 0 as verified.
    pub fn mark_squared_zero_verified(mut self) -> Self {
        self.squared_zero_verified = true;
        if self.level == CertificationLevel::Basic {
            self.level = CertificationLevel::SquaredZeroVerified;
        }
        self
    }

    /// Mark exactness as verified.
    pub fn mark_exactness_verified(mut self) -> Self {
        self.exactness_verified = true;
        if self.level == CertificationLevel::SquaredZeroVerified {
            self.level = CertificationLevel::ExactnessVerified;
        }
        self
    }

    /// Mark augmentation as valid.
    pub fn mark_augmentation_valid(mut self) -> Self {
        self.augmentation_valid = true;
        if self.level == CertificationLevel::ExactnessVerified {
            self.level = CertificationLevel::FullyCertified;
        }
        self
    }

    /// Generate a full summary.
    pub fn summary(&self) -> String {
        format!(
            "ResolutionCertificate {{\n  level: {},\n  resolution_len: {},\n  d²=0: {},\n  exact: {},\n  aug_valid: {},\n  message: {}\n}}",
            self.level.to_string(),
            self.resolution_len,
            self.squared_zero_verified,
            self.exactness_verified,
            self.augmentation_valid,
            self.message
        )
    }
}

/// Resolution certifier: verifies that a projective resolution is valid.
pub struct ResolutionCertifier;

impl ResolutionCertifier {
    /// Structural checks: modules present, one differential per adjacent
    /// pair, ranks consistent.
    pub fn check_basic(resolution: &ProjectiveResolution) -> ResolutionCertificate {
        let mut cert = ResolutionCertificate::new(resolution.len());
        if let Err(problem) = resolution.check_structure() {
            cert.message = format!("Structure check failed: {problem}");
            return cert;
        }
        cert.modules_checked = resolution.len();
        cert.differentials_checked = resolution.differentials_len();
        cert.message = "Basic structure is sound".to_string();
        cert.mark_basic()
    }

    /// Verify that every composite through a module is exactly zero.
    pub fn verify_squared_zero(resolution: &ProjectiveResolution) -> ResolutionCertificate {
        let mut cert = Self::check_basic(resolution);
        if cert.level != CertificationLevel::Basic {
            return cert;
        }
        let mut failures = Vec::new();
        for i in 0..resolution.len() {
            match resolution.composition_is_zero(i) {
                Ok(true) => {}
                Ok(false) => failures.push(format!("composite through P_{i} is non-zero")),
                Err(e) => failures.push(e),
            }
        }
        if failures.is_empty() {
            cert.message = "d² = 0 verified at every module".to_string();
            cert.mark_squared_zero_verified()
        } else {
            cert.message = format!("d² ≠ 0: {}", failures.join("; "));
            cert
        }
    }

    /// Verify that the augmented complex has zero homology at every module.
    pub fn verify_exactness(resolution: &ProjectiveResolution) -> ResolutionCertificate {
        let mut cert = Self::verify_squared_zero(resolution);
        if cert.level != CertificationLevel::SquaredZeroVerified {
            return cert;
        }
        let mut failures = Vec::new();
        for i in 0..resolution.len() {
            match resolution.homology_at(i) {
                Ok(h) if h.is_zero() => {}
                Ok(h) => failures.push(format!(
                    "homology at P_{i} is Z^{} with torsion {:?}",
                    h.free_rank, h.torsion
                )),
                Err(e) => failures.push(e),
            }
        }
        if failures.is_empty() {
            cert.message = "Exact at every module".to_string();
            cert.mark_exactness_verified()
        } else {
            cert.message = format!("Not exact: {}", failures.join("; "));
            cert
        }
    }

    /// Verify that the augmentation is surjective.
    pub fn verify_augmentation(resolution: &ProjectiveResolution) -> ResolutionCertificate {
        let mut cert = Self::verify_exactness(resolution);
        if cert.level != CertificationLevel::ExactnessVerified {
            return cert;
        }
        match resolution.augmentation_is_surjective() {
            Ok(true) => {
                let kind = if resolution.augmentation.is_some() {
                    "Augmentation is surjective"
                } else {
                    "Augmentation is the quotient map onto coker(d_1)"
                };
                cert.message = format!("{}\n{kind}", cert.message);
                cert.mark_augmentation_valid()
            }
            Ok(false) => {
                cert.message = format!("{}\nAugmentation is not surjective", cert.message);
                cert
            }
            Err(e) => {
                cert.message = format!("{}\nAugmentation check failed: {e}", cert.message);
                cert
            }
        }
    }

    /// Perform full certification.
    pub fn certify_fully(resolution: &ProjectiveResolution) -> ResolutionCertificate {
        let mut cert = Self::verify_augmentation(resolution);

        if cert.level != CertificationLevel::FullyCertified {
            cert.message = format!("{}\nFull certification failed", cert.message);
        } else {
            cert.message = format!("{}\nFull certification PASSED", cert.message);
        }

        cert
    }

    /// Batch certification of multiple resolutions.
    pub fn certify_batch(resolutions: &[ProjectiveResolution]) -> Vec<ResolutionCertificate> {
        resolutions
            .iter()
            .map(|res| Self::certify_fully(res))
            .collect()
    }

    /// Generate a certification report for a batch.
    pub fn batch_summary(certs: &[ResolutionCertificate]) -> String {
        let fully_certified = certs.iter().filter(|c| c.level.is_fully_certified()).count();
        let total = certs.len();
        let rate = if total == 0 {
            0.0
        } else {
            fully_certified as f64 / total as f64 * 100.0
        };

        format!(
            "Batch Certification Report\n  Total: {}\n  Fully certified: {}\n  Success rate: {:.1}%\n",
            total, fully_certified, rate
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_certification_level() {
        assert!(!CertificationLevel::Uncertified.is_fully_certified());
        assert!(CertificationLevel::FullyCertified.is_fully_certified());
    }

    #[test]
    fn test_resolution_certificate_new() {
        let cert = ResolutionCertificate::new(3);
        assert_eq!(cert.resolution_len, 3);
        assert_eq!(cert.level, CertificationLevel::Uncertified);
    }

    #[test]
    fn test_resolution_certificate_mark_basic() {
        let cert = ResolutionCertificate::new(3).mark_basic();
        assert_eq!(cert.level, CertificationLevel::Basic);
    }

    #[test]
    fn test_resolution_certificate_progression() {
        let cert = ResolutionCertificate::new(3)
            .mark_basic()
            .mark_squared_zero_verified()
            .mark_exactness_verified()
            .mark_augmentation_valid();
        assert_eq!(cert.level, CertificationLevel::FullyCertified);
    }

    #[test]
    fn test_resolution_certificate_summary() {
        let cert = ResolutionCertificate::new(2).mark_basic();
        let summary = cert.summary();
        assert!(summary.contains("Basic"));
    }

    #[test]
    fn test_certifier_check_basic_empty() {
        let res = ProjectiveResolution::new();
        let cert = ResolutionCertifier::check_basic(&res);
        assert_eq!(cert.level, CertificationLevel::Uncertified);
    }

    #[test]
    fn test_certifier_batch() {
        let res1 = ProjectiveResolution::free_of_rank_one();
        let res2 = ProjectiveResolution::cyclic_resolution(6);
        let certs = ResolutionCertifier::certify_batch(&[res1, res2]);
        assert_eq!(certs.len(), 2);
        assert!(certs.iter().all(|c| c.level.is_fully_certified()), "{:?}", certs);
        assert!(ResolutionCertifier::batch_summary(&certs).contains("100.0%"));
        assert!(ResolutionCertifier::batch_summary(&[]).contains("0.0%"));
    }


    fn two_step(d1: i64, d2: i64) -> ProjectiveResolution {
        let (p0, p1, p2) = (
            ProjectiveModule::new(1, 0),
            ProjectiveModule::new(1, 1),
            ProjectiveModule::new(1, 2),
        );
        let mut res = ProjectiveResolution::new();
        res.add_module(p0.clone());
        res.add_module(p1.clone());
        res.add_module(p2.clone());
        res.add_differential(ProjectiveModuleHomomorphism::new(p1.clone(), p0, vec![vec![d1]]));
        res.add_differential(ProjectiveModuleHomomorphism::new(p2, p1, vec![vec![d2]]));
        res
    }

    #[test]
    fn non_complex_stops_at_basic() {
        let cert = ResolutionCertifier::certify_fully(&two_step(2, 3));
        assert_eq!(cert.level, CertificationLevel::Basic);
        assert!(!cert.squared_zero_verified);
        assert!(cert.message.contains("d² ≠ 0"));
    }

    #[test]
    fn non_exact_stops_at_squared_zero() {
        let cert = ResolutionCertifier::certify_fully(&two_step(0, 0));
        assert_eq!(cert.level, CertificationLevel::SquaredZeroVerified);
        assert!(!cert.exactness_verified);
        assert!(cert.message.contains("Not exact"));
    }

    #[test]
    fn broken_structure_is_uncertified() {
        let (p0, p1) = (ProjectiveModule::new(1, 0), ProjectiveModule::new(1, 1));
        let mut res = ProjectiveResolution::new();
        res.add_module(p0);
        res.add_module(p1);
        let cert = ResolutionCertifier::certify_fully(&res);
        assert_eq!(cert.level, CertificationLevel::Uncertified);
        assert!(cert.message.contains("Structure check failed"));
    }

    #[test]
    fn non_surjective_augmentation_is_not_fully_certified() {
        let p0 = ProjectiveModule::new(1, 0);
        let mut res = ProjectiveResolution::new();
        res.add_module(p0.clone());
        res.set_augmentation(ProjectiveModuleHomomorphism::new(p0.clone(), p0, vec![vec![3]]));
        let cert = ResolutionCertifier::certify_fully(&res);
        assert!(!cert.level.is_fully_certified());
    }
}
