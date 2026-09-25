//! tor_spectrum_correspondence
//!
//! Correspondence between Tor (Tier 5) and the prime spectrum (Tier 6):
//! the highest non-vanishing Tor degree of any pair of cyclic groups is at
//! most the Krull dimension of Spec(ℤ) (computed on a finite prefix). This
//! is the finite, checkable shadow of "ℤ is regular of dimension 1, so its
//! global dimension — which bounds Tor dimension — equals its Krull
//! dimension".

#![warn(missing_docs)]

use cross_layer_types::CorrespondenceReport;
use derived_homology::{tor_of, ProjectiveResolution};
pub use dimension_upper_bounds::KrullDim;
use dimension_upper_bounds::{DimensionUpperBound, Spectrum};
use tor_invariants_computation::global_dimension;

/// Krull dimension of `{(0)} ∪ {(p) : p ≤ bound}`.
pub fn spec_z_prefix_dimension(bound: u64) -> KrullDim {
    KrullDim::from_spectrum(&Spectrum::new((0..=bound).collect()))
}

/// For `0 ≤ m, n ≤ max_order`, check that the Tor dimension of
/// `(ℤ/m, ℤ/n)` satisfies the upper bound `krull`.
pub fn check_tor_dimension_bounded_with(max_order: i64, krull: KrullDim) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("tor_dimension_bounded_by_krull");
    let bound = DimensionUpperBound::integral_extension_bound(krull);
    for m in 0..=max_order {
        for n in 0..=max_order {
            let resolutions = (ProjectiveResolution::cyclic_resolution(m), ProjectiveResolution::cyclic_resolution(n));
            match tor_of(&resolutions.0, &resolutions.1) {
                Ok(tor) => {
                    let tor_dim = global_dimension(&tor).unwrap_or(0);
                    report.check(bound.satisfies(KrullDim(tor_dim)), || {
                        format!("Tor dimension {tor_dim} of (ℤ/{m}, ℤ/{n}) exceeds {bound}")
                    });
                }
                Err(e) => report.error(format!("(ℤ/{m}, ℤ/{n}): {e}")),
            }
        }
    }
    report
}

/// The real check: bound by the dimension of the Spec(ℤ) prefix up to
/// `max_order` (at least up to 2).
pub fn check_tor_dimension_bounded_by_krull(max_order: i64) -> CorrespondenceReport {
    let krull = spec_z_prefix_dimension(max_order.max(2) as u64);
    check_tor_dimension_bounded_with(max_order, krull)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tor_dimension_is_bounded_by_krull_dimension() {
        assert_eq!(spec_z_prefix_dimension(24), KrullDim(1));
        let report = check_tor_dimension_bounded_by_krull(24);
        assert!(report.holds(), "{:?}", report.failures);
        assert_eq!(report.cases_checked, 25 * 25);
    }

    #[test]
    fn understated_dimension_is_caught() {
        let report = check_tor_dimension_bounded_with(6, KrullDim(0));
        assert!(!report.holds());
        assert!(report.failures.iter().any(|f| f.contains("ℤ/2, ℤ/2")));
    }
}
