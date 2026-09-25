//! gap_absolute_difference
//!
//! Compute differences and distance metrics for prime gaps.

#![warn(missing_docs)]

pub use gap_candidate_set::GapCandidateSet;
pub use gap_ordering::order_gaps;

/// Compute gap differences (consecutive gaps).
pub fn gap_differences(candidates: &[(u64, u64, u64)]) -> Vec<i64> {
    let gaps: Vec<u64> = candidates.iter().map(|&(_, _, g)| g).collect();
    gaps.windows(2)
        .map(|w| (w[1] as i64) - (w[0] as i64))
        .collect()
}

/// Compute absolute differences between gap sizes.
pub fn absolute_gap_differences(candidates: &[(u64, u64, u64)]) -> Vec<u64> {
    let gaps: Vec<u64> = candidates.iter().map(|&(_, _, g)| g).collect();
    gaps.windows(2)
        .map(|w| (w[1] as i64 - w[0] as i64).abs() as u64)
        .collect()
}

/// Compute deviations from a target gap size.
pub fn gap_deviations(candidates: &[(u64, u64, u64)], target: u64) -> Vec<i64> {
    candidates
        .iter()
        .map(|&(_, _, g)| (g as i64) - (target as i64))
        .collect()
}

/// Compute the L2 distance between two sequences of gaps.
pub fn gap_sequence_distance(gaps1: &[u64], gaps2: &[u64]) -> f64 {
    let max_len = gaps1.len().max(gaps2.len());
    let mut sum = 0.0;

    for i in 0..max_len {
        let g1 = gaps1.get(i).copied().unwrap_or(0);
        let g2 = gaps2.get(i).copied().unwrap_or(0);
        let diff = (g1 as i64) - (g2 as i64);
        sum += (diff * diff) as f64;
    }

    sum.sqrt()
}

/// "Roughness" of a gap sequence: the population standard deviation (divide
/// by n) of consecutive gap differences. Note that `gap_multiplicity`'s
/// `gap_std_dev` uses the sample convention (divide by n − 1).
pub fn sequence_roughness(candidates: &[(u64, u64, u64)]) -> f64 {
    let diffs = gap_differences(candidates);
    if diffs.is_empty() {
        return 0.0;
    }

    let mean: f64 = diffs.iter().map(|&d| d as f64).sum::<f64>() / diffs.len() as f64;
    let variance: f64 = diffs
        .iter()
        .map(|&d| {
            let diff = d as f64 - mean;
            diff * diff
        })
        .sum::<f64>()
        / diffs.len() as f64;

    variance.sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gap_differences() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let diffs = gap_differences(&candidates);
        assert_eq!(diffs, vec![1, 0, 2]);
    }

    #[test]
    fn test_absolute_gap_differences() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4), (11, 13, 2)];
        assert_eq!(absolute_gap_differences(&candidates), vec![1, 0, 2, 2]);
        assert!(absolute_gap_differences(&candidates[..1]).is_empty());
    }

    #[test]
    fn test_gap_deviations() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let deviations = gap_deviations(&candidates, 2);
        assert_eq!(deviations[0], -1); // 1 - 2 = -1
        assert_eq!(deviations[1], 0);  // 2 - 2 = 0
    }

    #[test]
    fn test_gap_sequence_distance() {
        let gaps1 = vec![1, 2, 2, 4];
        let gaps2 = vec![1, 2, 2, 4];
        let distance = gap_sequence_distance(&gaps1, &gaps2);
        assert_eq!(distance, 0.0);
    }

    #[test]
    fn test_sequence_roughness() {
        let candidates = vec![(2, 3, 1), (3, 5, 2), (5, 7, 2), (7, 11, 4)];
        let roughness = sequence_roughness(&candidates);
        assert!((roughness - (2.0f64 / 3.0).sqrt()).abs() < 1e-12);
        assert_eq!(sequence_roughness(&candidates[..1]), 0.0);
    }
}
