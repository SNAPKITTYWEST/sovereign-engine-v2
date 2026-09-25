//! gap_tensor_spectral
//!
//! Spectral decomposition of a set of gap tensor nodes: resonance per
//! candidate-prime axis, dominant prime, normalized spectrum and spectral
//! entropy.

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;
use gap_tensor_primes::{candidate_at, candidate_index, NUM_CANDIDATES};

/// Resonance per candidate-prime axis, indexed like `CANDIDATE_PRIMES`.
pub type Spectrum = [f32; NUM_CANDIDATES];

/// Resonance of a node set, split by candidate-prime axis.
#[derive(Debug, Clone, PartialEq)]
pub struct SpectralDecomposition {
    /// Resonance on each candidate axis.
    pub spectrum: Spectrum,
    /// Resonance carried by non-nil nodes whose prime is not a candidate.
    pub off_axis: f32,
    /// Number of Nil nodes skipped.
    pub nil_count: usize,
}

/// Decompose the resonance of `nodes` onto the candidate-prime axes.
pub fn decompose(nodes: &[GapTensorNode]) -> SpectralDecomposition {
    let mut spectrum = [0.0f32; NUM_CANDIDATES];
    let mut off_axis = 0.0f32;
    let mut nil_count = 0;
    for node in nodes {
        if node.is_nil() {
            nil_count += 1;
            continue;
        }
        match candidate_index(node.prime_val) {
            Some(axis) => spectrum[axis] += node.resonance(),
            None => off_axis += node.resonance(),
        }
    }
    SpectralDecomposition {
        spectrum,
        off_axis,
        nil_count,
    }
}

impl SpectralDecomposition {
    /// Total resonance, on-axis plus off-axis.
    pub fn total(&self) -> f32 {
        self.on_axis_total() + self.off_axis
    }

    /// Resonance carried by the candidate axes only.
    pub fn on_axis_total(&self) -> f32 {
        self.spectrum.iter().sum()
    }

    /// The candidate prime with the largest positive, finite resonance.
    /// Ties go to the smaller prime.
    pub fn dominant_prime(&self) -> Option<u32> {
        let mut best: Option<(usize, f32)> = None;
        for (axis, &value) in self.spectrum.iter().enumerate() {
            if !value.is_finite() || value <= 0.0 {
                continue;
            }
            if best.map_or(true, |(_, b)| value > b) {
                best = Some((axis, value));
            }
        }
        best.and_then(|(axis, _)| candidate_at(axis))
    }

    /// The on-axis spectrum scaled to sum to 1. `None` unless every axis is
    /// finite and non-negative and the sum is positive.
    pub fn normalized(&self) -> Option<Spectrum> {
        if self
            .spectrum
            .iter()
            .any(|v| !v.is_finite() || *v < 0.0)
        {
            return None;
        }
        let sum = self.on_axis_total();
        if !(sum > 0.0) || !sum.is_finite() {
            return None;
        }
        let mut out = self.spectrum;
        for v in out.iter_mut() {
            *v /= sum;
        }
        Some(out)
    }

    /// Shannon entropy (bits) of the normalized spectrum.
    pub fn entropy(&self) -> Option<f32> {
        let p = self.normalized()?;
        Some(
            -p.iter()
                .filter(|&&x| x > 0.0)
                .map(|&x| x * x.log2())
                .sum::<f32>(),
        )
    }
}

/// Nodes whose resonance reaches [`GapTensorNode::RESONANCE_MIN`].
pub fn participating(nodes: &[GapTensorNode]) -> Vec<GapTensorNode> {
    nodes
        .iter()
        .filter(|n| n.is_prime() && n.resonance() >= GapTensorNode::RESONANCE_MIN)
        .copied()
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<GapTensorNode> {
        vec![
            GapTensorNode::new(2, 1, 1.0),
            GapTensorNode::new(3, 2, 1.5),
            GapTensorNode::NIL,
            GapTensorNode::new(2, 1, 2.0),
            GapTensorNode::new(17, 1, 1.0),
        ]
    }

    #[test]
    fn decomposition_splits_by_axis() {
        let d = decompose(&sample());
        assert_eq!(d.spectrum[0], 3.0);
        assert_eq!(d.spectrum[1], 3.0);
        assert_eq!(d.spectrum[2..], [0.0; 4]);
        assert_eq!(d.off_axis, 1.0);
        assert_eq!(d.nil_count, 1);
        assert_eq!(d.total(), 7.0);
    }

    #[test]
    fn dominant_prime_prefers_smaller_on_tie() {
        assert_eq!(decompose(&sample()).dominant_prime(), Some(2));
        let d = decompose(&[
            GapTensorNode::new(2, 1, 1.0),
            GapTensorNode::new(11, 3, 1.0),
        ]);
        assert_eq!(d.dominant_prime(), Some(11));
        assert_eq!(decompose(&[]).dominant_prime(), None);
    }

    #[test]
    fn normalized_spectrum_sums_to_one() {
        let p = decompose(&sample()).normalized().unwrap();
        let sum: f32 = p.iter().sum();
        assert!((sum - 1.0).abs() < 1e-6);
        assert_eq!(decompose(&[]).normalized(), None);
        let negative = decompose(&[GapTensorNode::new(2, 1, -1.0)]);
        assert_eq!(negative.normalized(), None);
    }

    #[test]
    fn entropy_of_simple_spectra() {
        let single = decompose(&[GapTensorNode::new(5, 2, 1.0)]);
        assert_eq!(single.entropy(), Some(0.0));
        let uniform = decompose(&[GapTensorNode::new(2, 1, 1.0), GapTensorNode::new(3, 1, 1.0)]);
        assert!((uniform.entropy().unwrap() - 1.0).abs() < 1e-6);
    }

    #[test]
    fn participation_threshold() {
        let nodes = [
            GapTensorNode::new(2, 1, 0.5),
            GapTensorNode::new(3, 2, 0.5),
            GapTensorNode::NIL,
        ];
        let p = participating(&nodes);
        assert_eq!(p, vec![GapTensorNode::new(3, 2, 0.5)]);
    }
}
