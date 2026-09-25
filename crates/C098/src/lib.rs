//! counterexample_harness
//!
//! Negative tests of the verification machinery itself. Each case feeds a
//! correspondence check a deliberately broken input — a corrupted arena, a
//! lax runtime checker, a wrong threshold, a forged certificate, a wrong
//! candidate list, an understated dimension — and passes only if the check
//! reports the failure. A harness where every case is caught is evidence
//! that the Tier 9 checks can detect real mismatches rather than passing
//! vacuously.

#![warn(missing_docs)]

use cross_layer_invariants::{
    check_arena_preserves_tensors_with, check_dissonance_matches_gap_constraint, check_runtime_matches_static_with,
    ArenaLayout, Region,
};
use cross_layer_types::{check_tensor, standard_family, CorrespondenceReport, GapTensor, GapTensorNode, MultiplicityArena, Violation};
use prime_gap_correspondence::{check_candidate_gaps_match_engine_with, check_gap_pairs_become_consonant_nodes_with};
use rust_lean_correspondence::{
    certify, check_certificate_against_sources, claim_obligation_id, standard_executions, ObligationStatus,
};
use tensor_homology_correspondence::check_dissonance_equals_path_components_with;
use tor_spectrum_correspondence::{check_tor_dimension_bounded_with, KrullDim};

/// One counterexample case.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CounterexampleCase {
    /// Case name.
    pub name: &'static str,
    /// Did the check report the broken input?
    pub caught: bool,
    /// First failure reported, or why the case was not caught.
    pub detail: String,
}

/// All counterexample cases.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CounterexampleReport {
    /// Cases in run order.
    pub cases: Vec<CounterexampleCase>,
}

impl CounterexampleReport {
    /// Was every broken input caught?
    pub fn all_caught(&self) -> bool {
        self.cases.iter().all(|c| c.caught)
    }

    /// Cases that were not caught.
    pub fn missed(&self) -> Vec<&CounterexampleCase> {
        self.cases.iter().filter(|c| !c.caught).collect()
    }
}

fn case(name: &'static str, report: CorrespondenceReport) -> CounterexampleCase {
    let caught = !report.holds();
    let detail = if caught {
        report.failures.first().cloned().unwrap_or_else(|| "no cases".into())
    } else {
        format!("{} cases all passed", report.cases_checked)
    };
    CounterexampleCase { name, caught, detail }
}

fn corrupt_arena(arena: &mut MultiplicityArena, layout: &ArenaLayout) {
    let i = layout.span(Region::Data).start;
    // SAFETY: the DATA region is non-empty, so i < layout.total() == arena.len().
    unsafe { arena.set_node(i, GapTensorNode::new(11, 9, 9.0)) };
}

fn lax_runtime_checker(t: &GapTensor) -> Vec<Violation> {
    check_tensor(t)
        .violations
        .into_iter()
        .filter(|v| !matches!(v, Violation::Dissonance { .. }))
        .collect()
}

fn forged_certificate() -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("forged_certificate");
    match standard_executions() {
        Ok(executions) => {
            let sources = executions.sources();
            let mut cert = certify(&sources);
            let id = claim_obligation_id("dissonant_tensor", "invariants_hold");
            match cert.obligations.get_obligation_mut(&id) {
                Some(o) => o.status = ObligationStatus::Closed,
                None => report.error(format!("{id} missing")),
            }
            check_certificate_against_sources(&cert, &sources, &mut report);
        }
        Err(e) => report.error(e),
    }
    report
}

fn forged_digest() -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("forged_digest");
    match standard_executions() {
        Ok(executions) => {
            let sources = executions.sources();
            let mut cert = certify(&sources);
            cert.digests.insert("primes".into(), 0);
            check_certificate_against_sources(&cert, &sources, &mut report);
        }
        Err(e) => report.error(e),
    }
    report
}

/// Run every counterexample case.
pub fn run_counterexamples() -> CounterexampleReport {
    let family = standard_family();
    CounterexampleReport {
        cases: vec![
            case("arena_corruption", check_arena_preserves_tensors_with(&family, corrupt_arena)),
            case("lax_runtime_checker", check_runtime_matches_static_with(&family, lax_runtime_checker)),
            case("wrong_dissonance_threshold", check_dissonance_matches_gap_constraint(&family, 4)),
            case("forged_certificate", forged_certificate()),
            case("forged_digest", forged_digest()),
            case("wrong_candidate_list", check_candidate_gaps_match_engine_with(&[2, 3, 5, 7, 11, 17])),
            case("non_candidate_prime_pairs", check_gap_pairs_become_consonant_nodes_with(17)),
            case("wrong_path_threshold", check_dissonance_equals_path_components_with(&family, 4)),
            case("understated_krull_dimension", check_tor_dimension_bounded_with(6, KrullDim(0))),
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_counterexample_is_caught() {
        let report = run_counterexamples();
        assert_eq!(report.cases.len(), 9);
        assert!(report.all_caught(), "missed: {:?}", report.missed());
    }
}
