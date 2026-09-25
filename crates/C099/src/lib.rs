//! full_regression_test_suite
//!
//! Runs one regression suite per tier (0–8) and reports each by tier and
//! name: the integration suites of Tiers 1, 2, 4, 5, 6 and 8, the decided
//! recursion lemmas (Tier 3), serialization and trace round trips (Tier 0),
//! and the obligation aggregation (Tier 7, no refuted obligations).

#![warn(missing_docs)]

use gap_tensor_core::GapTensorNode;
use gap_tensor_serialization::round_trips;
use gap_tensor_shape::{GapTensor, TensorShape};
use gap_tensor_trace::TensorTrace;
use homological_tests_integration::HomologicalTestSuite;
use krull_spectrum_tests_integration::KrullIntegrationSuite;
use lean_obligation_aggregator::FullObligationContext;
use multiplicity_arena_tests_integration::run_arena_integration;
use prime_gap_tests_integration::run_prime_gap_integration;
use recursion_lemmas_library::RecursionLemmasLibrary;
use runtime_bridge_tests_integration::run_runtime_integration;
use tor_tests_integration::run_tor_integration;

/// Result of one suite.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SuiteResult {
    /// Tier the suite covers.
    pub tier: usize,
    /// Suite name.
    pub name: &'static str,
    /// Did it pass?
    pub passed: bool,
    /// Summary or failure detail.
    pub detail: String,
}

/// Results of all suites.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegressionReport {
    /// Suites in tier order.
    pub suites: Vec<SuiteResult>,
}

impl RegressionReport {
    /// Did every suite pass?
    pub fn all_passed(&self) -> bool {
        self.suites.iter().all(|s| s.passed)
    }

    /// Failed suites.
    pub fn failures(&self) -> Vec<&SuiteResult> {
        self.suites.iter().filter(|s| !s.passed).collect()
    }
}

fn result(tier: usize, name: &'static str, passed: bool, detail: String) -> SuiteResult {
    SuiteResult { tier, name, passed, detail }
}

fn tier0_round_trips() -> SuiteResult {
    let alphabet = [
        GapTensorNode::NIL,
        GapTensorNode::new(2, 1, 1.0),
        GapTensorNode::new(13, 7, -0.0),
        GapTensorNode::new(5, 3, f32::NAN),
    ];
    let mut trace = TensorTrace::new();
    let mut cases = 0;
    let mut failures = Vec::new();
    for a in alphabet {
        for b in alphabet {
            let t = GapTensor::from_nodes(TensorShape::vector(2).expect("valid shape"), vec![a, b]).expect("length 2");
            if !round_trips(&t) {
                failures.push(format!("{a:?}, {b:?}"));
            }
            trace.record(format!("case {cases}"), &t);
            cases += 1;
        }
    }
    let trace_ok = trace.verify().is_ok();
    result(
        0,
        "serialization_and_trace_round_trips",
        failures.is_empty() && trace_ok,
        if failures.is_empty() && trace_ok {
            format!("{cases} tensors round-tripped; trace verified")
        } else {
            format!("failures: {failures:?}; trace ok: {trace_ok}")
        },
    )
}

fn tier3_recursion_lemmas() -> SuiteResult {
    let lib = RecursionLemmasLibrary::standard();
    let failed = lib.count_failed();
    result(
        3,
        "recursion_lemmas_decided",
        failed == 0 && lib.count_proven() > 0,
        format!("{} decided, {} open, {failed} refuted", lib.count_proven(), lib.count_open()),
    )
}

fn tier7_obligations() -> SuiteResult {
    match FullObligationContext::standard() {
        Ok(ctx) => result(
            7,
            "obligation_aggregation",
            ctx.report.failed == 0,
            format!("{} closed, {} open, {} failed", ctx.report.closed, ctx.report.open, ctx.report.failed),
        ),
        Err(e) => result(7, "obligation_aggregation", false, e.to_string()),
    }
}

/// Run every suite.
pub fn run_regression() -> RegressionReport {
    let arena = run_arena_integration();
    let homology = HomologicalTestSuite::run_all();
    let tor = run_tor_integration();
    let krull = KrullIntegrationSuite::run_all();
    let runtime = run_runtime_integration();
    let tier2 = run_prime_gap_integration();
    RegressionReport {
        suites: vec![
            tier0_round_trips(),
            result(1, "arena_integration", arena.all_passed(), format!("{} scenarios; failed: {:?}", arena.scenarios.len(), arena.failures())),
            result(2, "prime_gap_integration", tier2.all_passed(), format!("{} scenarios; failed: {:?}", tier2.scenarios.len(), tier2.failures())),
            tier3_recursion_lemmas(),
            result(4, "homological_integration", homology.all_passed(), format!("{}/{} passed", homology.passed, homology.total)),
            result(5, "tor_integration", tor.all_passed(), format!("{} scenarios; failed: {:?}", tor.scenarios.len(), tor.failures())),
            result(6, "krull_integration", krull.all_passed(), format!("{}/{} passed; failed: {:?}", krull.passed_count(), krull.total_count(), krull.failed_tests())),
            tier7_obligations(),
            result(8, "runtime_integration", runtime.all_passed(), format!("{} scenarios; failed: {:?}", runtime.scenarios.len(), runtime.failures())),
        ],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_suite_passes() {
        let report = run_regression();
        assert_eq!(report.suites.len(), 9);
        assert!(report.all_passed(), "{:?}", report.failures());
        let tiers: Vec<usize> = report.suites.iter().map(|s| s.tier).collect();
        assert_eq!(tiers, (0..=8).collect::<Vec<_>>());
    }
}
