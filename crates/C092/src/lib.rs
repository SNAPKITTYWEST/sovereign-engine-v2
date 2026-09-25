//! cross_layer_invariants
//!
//! Invariants that must survive the boundaries between tiers, checked over
//! finite families:
//!
//! * **arena_preserves_tensors** (Tier 0 ↔ 1): writing a tensor to an arena's
//!   DATA region and reading it back preserves every node bit-for-bit and
//!   every invariant verdict;
//! * **runtime_invariants_match_static** (Tier 8 ↔ 0): the runtime invariant
//!   checker reports exactly the static violations, directly and through a
//!   recorded history;
//! * dissonance (Tier 0) agrees with gap-constraint satisfaction (Tier 2);
//! * every gap size occurring between candidate primes has a certified
//!   resolution of `Z/g` (Tier 2 ↔ 4).
//!
//! Each check takes its inputs (and, where useful, the component under
//! test) as parameters so the counterexample harness can feed broken ones.

#![warn(missing_docs)]

use cross_layer_types::{
    check_tensor, tensors_bitwise_equal, vector_state, CorrespondenceReport, GapTensor, MultiplicityArena,
    SnapshotStore, Violation, SIGMA_GAP_MAX,
};
use gap_constraint_satisfaction::GapConstraint;
pub use multiplicity_arena_layout::{ArenaLayout, Region};
use resolution_certification::{ProjectiveResolution, ResolutionCertifier};
use runtime_invariant_checking::RuntimeInvariantChecker;

/// Round-trip every tensor of `family` through an arena. `tamper` runs
/// between the write and the read (identity for the real check).
pub fn check_arena_preserves_tensors_with(
    family: &[GapTensor],
    tamper: impl Fn(&mut MultiplicityArena, &ArenaLayout),
) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("arena_preserves_tensors");
    for (i, tensor) in family.iter().enumerate() {
        let nodes = tensor.nodes();
        let layout = match ArenaLayout::new(1, nodes.len(), 1, 1) {
            Ok(l) => l,
            Err(e) => {
                report.error(format!("tensor {i}: {e:?}"));
                continue;
            }
        };
        let mut arena = layout.allocate();
        if let Err(e) = layout.write_region(&mut arena, Region::Data, nodes) {
            report.error(format!("tensor {i}: {e:?}"));
            continue;
        }
        tamper(&mut arena, &layout);
        match layout.read_region(&arena, Region::Data) {
            Ok(read) => {
                let back = vector_state(read);
                report.check(
                    tensors_bitwise_equal(&back, tensor) && check_tensor(&back) == check_tensor(tensor),
                    || format!("tensor {i} changed through the arena"),
                );
            }
            Err(e) => report.error(format!("tensor {i}: {e:?}")),
        }
    }
    report
}

/// The real arena check.
pub fn check_arena_preserves_tensors(family: &[GapTensor]) -> CorrespondenceReport {
    check_arena_preserves_tensors_with(family, |_, _| {})
}

/// Compare a runtime checker with the static one, directly and through a
/// recorded history.
pub fn check_runtime_matches_static_with(
    family: &[GapTensor],
    runtime: impl Fn(&GapTensor) -> Vec<Violation>,
) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("runtime_invariants_match_static");
    let mut store = SnapshotStore::new();
    for (i, tensor) in family.iter().enumerate() {
        let expected = check_tensor(tensor).violations;
        report.check(runtime(tensor) == expected, || format!("tensor {i}: direct check differs"));
        store.capture(format!("t{i}"), tensor);
    }
    let recorded = RuntimeInvariantChecker::check_store("family", &store);
    report.check(recorded.disagreements.is_empty(), || "stored reports disagree".into());
    for (i, tensor) in family.iter().enumerate() {
        let expected = check_tensor(tensor).violations;
        let got: Vec<Violation> = recorded
            .violations
            .iter()
            .filter(|(step, _)| *step == i as u64)
            .map(|(_, v)| v.clone())
            .collect();
        report.check(got == expected, || format!("tensor {i}: recorded check differs"));
    }
    report
}

/// The real runtime-vs-static check.
pub fn check_runtime_matches_static(family: &[GapTensor]) -> CorrespondenceReport {
    check_runtime_matches_static_with(family, RuntimeInvariantChecker::check_state)
}

/// The number of dissonance violations equals the number of consecutive
/// non-nil prime pairs whose gap fails `GapConstraint::range(0, max_gap)`.
pub fn check_dissonance_matches_gap_constraint(family: &[GapTensor], max_gap: u64) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("dissonance_matches_gap_constraint");
    let constraint = GapConstraint::range(0, max_gap);
    for (i, tensor) in family.iter().enumerate() {
        let primes: Vec<u64> = tensor.nodes().iter().filter(|n| n.is_prime()).map(|n| n.prime_val as u64).collect();
        let failing = primes
            .windows(2)
            .filter(|w| !constraint.satisfies(w[0].abs_diff(w[1])))
            .count();
        let dissonances = check_tensor(tensor)
            .violations
            .iter()
            .filter(|v| matches!(v, Violation::Dissonance { .. }))
            .count();
        report.check(failing == dissonances, || format!("tensor {i}: {failing} failing gaps vs {dissonances} dissonances"));
    }
    report
}

/// Every gap between distinct candidate primes has a fully certified
/// resolution of `Z/g`.
pub fn check_candidate_gap_resolutions(candidates: &[u32]) -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("candidate_gap_resolutions");
    for (i, &p) in candidates.iter().enumerate() {
        for &q in &candidates[i + 1..] {
            let g = p.abs_diff(q) as i64;
            let cert = ResolutionCertifier::certify_fully(&ProjectiveResolution::cyclic_resolution(g));
            report.check(cert.level.is_fully_certified(), || format!("Z/{g}: {}", cert.message));
        }
    }
    report
}

/// Run every check of this crate on the standard inputs.
pub fn run_all(family: &[GapTensor], candidates: &[u32]) -> Vec<CorrespondenceReport> {
    vec![
        check_arena_preserves_tensors(family),
        check_runtime_matches_static(family),
        check_dissonance_matches_gap_constraint(family, SIGMA_GAP_MAX as u64),
        check_candidate_gap_resolutions(candidates),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use cross_layer_types::{standard_family, GapTensorNode, CANDIDATE_PRIMES};

    #[test]
    fn standard_checks_hold() {
        for report in run_all(&standard_family(), &CANDIDATE_PRIMES) {
            assert!(report.holds(), "{}: {:?}", report.name, report.failures.first());
        }
    }

    #[test]
    fn broken_inputs_are_caught() {
        let family = standard_family();
        let flip = |arena: &mut MultiplicityArena, layout: &ArenaLayout| {
            let i = layout.span(Region::Data).start;
            unsafe { arena.set_node(i, GapTensorNode::new(11, 9, 9.0)) };
        };
        assert!(!check_arena_preserves_tensors_with(&family, flip).holds());
        let lax = |t: &GapTensor| {
            check_tensor(t)
                .violations
                .into_iter()
                .filter(|v| !matches!(v, Violation::Dissonance { .. }))
                .collect()
        };
        assert!(!check_runtime_matches_static_with(&family, lax).holds());
        assert!(!check_dissonance_matches_gap_constraint(&family, 4).holds());
    }
}
