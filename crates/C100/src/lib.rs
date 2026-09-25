//! final_certification_report
//!
//! The pipeline's final report. It
//!
//! 1. decides every standard cross-layer lemma with the Tier 9 checks;
//! 2. aggregates all tier and cross-layer obligations (Tier 7), re-checking
//!    every proof;
//! 3. runs the full regression suite and the counterexample harness;
//! 4. issues a verdict that says exactly what is and is not established.
//!
//! The verdict is `Complete` only if every obligation is closed without
//! assumptions and nothing failed. Obligations over unbounded domains (for
//! example "is_prime is correct for all n") cannot be closed by computation;
//! while they are open the verdict is `Incomplete` and lists them.

#![warn(missing_docs)]

use counterexample_harness::{run_counterexamples, CounterexampleReport};
use cross_layer_invariants::{check_arena_preserves_tensors, check_runtime_matches_static};
use cross_layer_types::{standard_family, CorrespondenceReport, Tier};
use end_to_end_trace_verification::check_trace_replay_matches_execution;
use full_regression_test_suite::{run_regression, RegressionReport};
use lean_obligation_aggregator::{
    extract_tier_from_id, AggregatedObligationReport, CrossLayerLemmaLibrary, FullObligationContext,
    VerificationStatus, STANDARD_CORRESPONDENCES,
};
use prime_gap_correspondence::{check_candidate_gaps_match_engine, check_gap_pairs_become_consonant_nodes};
use rust_lean_correspondence::check_certificates_discharge_obligations;
use std::collections::BTreeMap;
use std::fmt::Write as _;
use tensor_homology_correspondence::check_dissonance_equals_path_components;
use tor_spectrum_correspondence::check_tor_dimension_bounded_by_krull;
pub use type_checking_interface::Evidence;

/// Outcome of deciding one cross-layer lemma.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CorrespondenceOutcome {
    /// Lemma id.
    pub id: String,
    /// Crate that decided it.
    pub decided_by: String,
    /// Cases checked, or the counterexample.
    pub result: Result<u64, String>,
}

/// An obligation that is still open, with what it needs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OpenItem {
    /// Obligation id.
    pub id: String,
    /// Note from its library (what remains to be done).
    pub note: Option<String>,
}

/// Final verdict.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Verdict {
    /// Every obligation closed without assumptions; everything passed.
    Complete,
    /// Every obligation closed, some resting on axioms; everything passed.
    CompleteWithAssumptions,
    /// Nothing failed, but these obligations are open.
    Incomplete {
        /// Open obligation ids.
        open: Vec<String>,
    },
    /// Something failed.
    Failed {
        /// What failed.
        reasons: Vec<String>,
    },
}

/// The final certification report.
#[derive(Debug, Clone)]
pub struct FinalCertificationReport {
    /// Aggregated obligations.
    pub obligations: AggregatedObligationReport,
    /// Cross-layer decisions.
    pub correspondences: Vec<CorrespondenceOutcome>,
    /// Regression suites.
    pub regression: RegressionReport,
    /// Counterexample harness.
    pub counterexamples: CounterexampleReport,
    /// Open obligations with notes.
    pub open_items: Vec<OpenItem>,
    /// Verdict.
    pub verdict: Verdict,
}

fn run_check(id: &str) -> CorrespondenceReport {
    let family = standard_family();
    match id {
        "arena_preserves_tensors" => check_arena_preserves_tensors(&family),
        "candidate_gaps_match_engine" => check_candidate_gaps_match_engine(),
        "gap_pairs_become_consonant_nodes" => check_gap_pairs_become_consonant_nodes(),
        "dissonance_equals_path_components" => check_dissonance_equals_path_components(&family),
        "tor_dimension_bounded_by_krull" => check_tor_dimension_bounded_by_krull(24),
        "runtime_invariants_match_static" => check_runtime_matches_static(&family),
        "certificates_discharge_obligations" => check_certificates_discharge_obligations(),
        "trace_replay_matches_execution" => check_trace_replay_matches_execution(),
        other => {
            let mut r = CorrespondenceReport::new(other);
            r.error(format!("no Tier 9 check for `{other}`"));
            r
        }
    }
}

/// Decide every standard cross-layer lemma in `lib`.
pub fn decide_correspondences(lib: &mut CrossLayerLemmaLibrary) -> Vec<CorrespondenceOutcome> {
    STANDARD_CORRESPONDENCES
        .iter()
        .map(|&(id, decided_by)| {
            let report = run_check(id);
            let cases = report.cases_checked;
            let result = lib
                .decide(id, decided_by, || report.into_result())
                .map(|_| cases);
            CorrespondenceOutcome {
                id: id.to_string(),
                decided_by: decided_by.to_string(),
                result,
            }
        })
        .collect()
}

fn open_items(lib: &CrossLayerLemmaLibrary, report: &AggregatedObligationReport) -> Vec<OpenItem> {
    let mut notes: BTreeMap<String, Option<String>> = BTreeMap::new();
    for record in lib.tier_lemmas.values() {
        notes.insert(format!("tier_{}_{}", record.tier, record.name), record.note.clone());
    }
    for lemma in lib.lemmas.values() {
        notes.insert(format!("tier_9_{}", lemma.id), lemma.note.clone());
    }
    report
        .open_ids
        .iter()
        .map(|id| OpenItem {
            id: id.clone(),
            note: notes.get(id).cloned().flatten(),
        })
        .collect()
}

/// Build the report.
pub fn generate() -> Result<FinalCertificationReport, String> {
    let mut lib = CrossLayerLemmaLibrary::standard();
    let correspondences = decide_correspondences(&mut lib);
    let context = FullObligationContext::from_library(&lib).map_err(|e| e.to_string())?;
    let obligations = context.report;
    let regression = run_regression();
    let counterexamples = run_counterexamples();
    let open_items = open_items(&lib, &obligations);

    let mut reasons = Vec::new();
    reasons.extend(obligations.failed_ids.iter().map(|id| format!("obligation {id} refuted")));
    reasons.extend(
        correspondences
            .iter()
            .filter_map(|c| c.result.as_ref().err().map(|e| format!("{}: {e}", c.id))),
    );
    reasons.extend(regression.failures().iter().map(|s| format!("regression {} failed: {}", s.name, s.detail)));
    reasons.extend(counterexamples.missed().iter().map(|c| format!("counterexample {} not caught", c.name)));

    let verdict = if !reasons.is_empty() {
        Verdict::Failed { reasons }
    } else {
        match obligations.status() {
            VerificationStatus::Complete => Verdict::Complete,
            VerificationStatus::CompleteWithAssumptions => Verdict::CompleteWithAssumptions,
            VerificationStatus::Incomplete => Verdict::Incomplete {
                open: obligations.open_ids.clone(),
            },
        }
    };

    Ok(FinalCertificationReport {
        obligations,
        correspondences,
        regression,
        counterexamples,
        open_items,
        verdict,
    })
}

impl FinalCertificationReport {
    /// Human-readable report (Markdown).
    pub fn render(&self) -> String {
        let mut out = String::new();
        let o = &self.obligations;
        let _ = writeln!(out, "# Final certification report\n");
        let verdict = match &self.verdict {
            Verdict::Complete => "COMPLETE — every obligation closed without assumptions".to_string(),
            Verdict::CompleteWithAssumptions => "COMPLETE WITH ASSUMPTIONS — some proofs rest on axioms".to_string(),
            Verdict::Incomplete { open } => format!(
                "INCOMPLETE — nothing failed, but {} obligation(s) remain open (see below)",
                open.len()
            ),
            Verdict::Failed { reasons } => format!("FAILED — {}", reasons.join("; ")),
        };
        let _ = writeln!(out, "**Verdict:** {verdict}\n");
        let _ = writeln!(
            out,
            "**Obligations:** {} total, {} closed, {} open, {} failed. Evidence of closed obligations: {:?}\n",
            o.total, o.closed, o.open, o.failed, o.evidence
        );
        let _ = writeln!(out, "| Tier | Area | Closed | Total |\n|---|---|---|---|");
        for (tier, stats) in &o.by_tier {
            let area = Tier::from_number(*tier).map_or("?", Tier::name);
            let _ = writeln!(out, "| {tier} | {area} | {} | {} |", stats.closed, stats.count);
        }
        let _ = writeln!(out, "\n## Cross-layer correspondences\n");
        for c in &self.correspondences {
            match &c.result {
                Ok(cases) => {
                    let _ = writeln!(out, "- `{}` — decided by `{}` over {cases} cases", c.id, c.decided_by);
                }
                Err(e) => {
                    let _ = writeln!(out, "- `{}` — FAILED: {e}", c.id);
                }
            }
        }
        let _ = writeln!(out, "\n## Regression suites\n");
        for s in &self.regression.suites {
            let mark = if s.passed { "pass" } else { "FAIL" };
            let _ = writeln!(out, "- Tier {} `{}`: {mark} — {}", s.tier, s.name, s.detail);
        }
        let _ = writeln!(out, "\n## Counterexample harness\n");
        for c in &self.counterexamples.cases {
            let mark = if c.caught { "caught" } else { "MISSED" };
            let _ = writeln!(out, "- `{}`: {mark} — {}", c.name, c.detail);
        }
        let _ = writeln!(out, "\n## Open obligations\n");
        if self.open_items.is_empty() {
            let _ = writeln!(out, "None.");
        }
        for item in &self.open_items {
            let tier = extract_tier_from_id(&item.id).map_or("?".to_string(), |t| t.to_string());
            let note = item.note.as_deref().unwrap_or("no note");
            let _ = writeln!(out, "- (tier {tier}) `{}` — {note}", item.id);
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn report_is_honest() {
        let report = generate().unwrap();
        for c in &report.correspondences {
            assert!(c.result.is_ok(), "{}: {:?}", c.id, c.result);
        }
        assert!(report.regression.all_passed(), "{:?}", report.regression.failures());
        assert!(report.counterexamples.all_caught(), "{:?}", report.counterexamples.missed());
        assert_eq!(report.obligations.failed, 0);
        assert_eq!(report.obligations.closed, 38 + 8);
        assert_eq!(report.obligations.open, 9);
        match &report.verdict {
            Verdict::Incomplete { open } => assert_eq!(open.len(), 9),
            other => panic!("unexpected verdict {other:?}"),
        }
        assert!(report.open_items.iter().all(|i| i.note.is_some()), "every open item explains itself");
        let text = report.render();
        assert!(text.contains("INCOMPLETE"));
        assert!(text.contains("tier_2_primality_correct"));
    }
}
