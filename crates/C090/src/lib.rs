//! runtime_bridge_tests_integration
//!
//! End-to-end scenarios for the runtime bridge (C081–C089): bindings record
//! real executions of Tiers 0–3, invariants are re-checked, certificates are
//! issued, rollbacks keep state valid, and the whole execution is captured
//! in one verifiable trace. [`run_runtime_integration`] reports each
//! scenario by name.

#![warn(missing_docs)]

use certificate_generation::{certify, ExecutionCertificate};
use multiplicity_state_binding::ArenaLayout;
use rollback_mechanism::TransactionalTensor;
use runtime_invariant_checking::RuntimeInvariantChecker;
use runtime_state_snapshot::{vector_state, GapTensorNode};
use trace_recording_runtime::RuntimeTrace;

pub use multiplicity_state_binding::ArenaBinding;
pub use prime_state_binding::PrimeStateBinding;
pub use recursion_runtime_binding::RecursionBinding;
pub use tensor_runtime_binding::TensorBinding;

/// A complete, clean execution of the four bindings.
pub struct StandardExecution {
    /// Tensor binding.
    pub tensor: TensorBinding,
    /// Prime engine run.
    pub primes: PrimeStateBinding,
    /// Arena binding.
    pub arena: ArenaBinding,
    /// Solver run.
    pub recursion: RecursionBinding,
}

/// Run the standard execution.
pub fn standard_execution() -> Result<StandardExecution, String> {
    let mut tensor = TensorBinding::new(
        "tensor",
        vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL, GapTensorNode::NIL]),
    );
    tensor.set_node(1, GapTensorNode::new(3, 2, 0.5)).map_err(|e| e.to_string())?;
    tensor.set_node(2, GapTensorNode::new(7, 1, 1.0)).map_err(|e| e.to_string())?;

    let primes = PrimeStateBinding::run("primes", 500).map_err(|e| format!("{e:?}"))?;

    let layout = ArenaLayout::new(1, 3, 1, 1).map_err(|e| e.to_string())?;
    let mut arena = ArenaBinding::new("arena", layout).map_err(|e| e.to_string())?;
    arena
        .write_data(&[GapTensorNode::new(5, 1, 1.0), GapTensorNode::new(7, 1, 1.0)])
        .map_err(|e| e.to_string())?;
    arena.seal().map_err(|e| e.to_string())?;

    let mut recursion = RecursionBinding::new("recursion", 4);
    for p in [2, 3, 5] {
        recursion.push(GapTensorNode::new(p, 1, 1.0)).map_err(|e| format!("{e:?}"))?;
    }
    recursion.pop().map_err(|e| format!("{e:?}"))?;

    Ok(StandardExecution {
        tensor,
        primes,
        arena,
        recursion,
    })
}

impl StandardExecution {
    /// Certificate for all four bindings.
    pub fn certificate(&self) -> ExecutionCertificate {
        certify(&[&self.tensor, &self.primes, &self.arena, &self.recursion])
    }

    /// Whole-execution trace: every binding's history, then the certificate.
    pub fn trace(&self) -> RuntimeTrace {
        let mut trace = RuntimeTrace::new();
        trace.record_store("tensor", self.tensor.store());
        trace.record_store("primes", self.primes.store());
        trace.record_store("arena", self.arena.store());
        trace.record_store("recursion", self.recursion.store());
        trace.record_certificate(&self.certificate());
        trace
    }
}

/// Outcome of one scenario.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScenarioResult {
    /// Scenario name.
    pub name: &'static str,
    /// Failure description, if any.
    pub failure: Option<String>,
}

/// Outcome of all scenarios.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeIntegrationReport {
    /// Per-scenario results.
    pub scenarios: Vec<ScenarioResult>,
}

impl RuntimeIntegrationReport {
    /// True iff every scenario passed.
    pub fn all_passed(&self) -> bool {
        self.scenarios.iter().all(|s| s.failure.is_none())
    }

    /// Failed scenarios.
    pub fn failures(&self) -> Vec<&ScenarioResult> {
        self.scenarios.iter().filter(|s| s.failure.is_some()).collect()
    }
}

fn ensure(condition: bool, message: &str) -> Result<(), String> {
    if condition {
        Ok(())
    } else {
        Err(message.to_string())
    }
}

fn clean_execution_is_certified() -> Result<(), String> {
    let run = standard_execution()?;
    let cert = run.certificate();
    ensure(cert.all_hold(), &format!("claims failed: {:?}", cert.failures))?;
    ensure(cert.digests.len() == 4, "a binding digest is missing")
}

fn invariant_violations_are_certified_as_failures() -> Result<(), String> {
    let mut t = TensorBinding::new("tensor", vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL]));
    t.set_node(1, GapTensorNode::new(13, 1, 1.0)).map_err(|e| e.to_string())?;
    let cert = certify(&[&t]);
    ensure(cert.holds("tensor", "invariants_hold") == Some(false), "dissonance not reported")?;
    ensure(cert.holds("tensor", "history_intact") == Some(true), "history claim should still hold")
}

fn runtime_checker_agrees_with_recordings() -> Result<(), String> {
    let run = standard_execution()?;
    let report = RuntimeInvariantChecker::check_bindings(&run.tensor, &run.primes, &run.arena, &run.recursion);
    ensure(report.stored_reports_agree(), "stored and recomputed invariant reports differ")?;
    ensure(
        report.stores.iter().find(|s| s.source == "tensor").map_or(false, |s| s.is_clean()),
        "the clean tensor history has violations",
    )
}

fn rollbacks_keep_state_valid() -> Result<(), String> {
    let mut t = TransactionalTensor::new(vector_state(vec![GapTensorNode::new(5, 1, 1.0), GapTensorNode::new(7, 1, 1.0)]))
        .map_err(|v| format!("{v:?}"))?;
    t.apply("ok", |x| x.nodes_mut()[1] = GapTensorNode::new(11, 1, 1.0)).map_err(|r| r.label)?;
    ensure(t.apply("bad", |x| x.nodes_mut()[0] = GapTensorNode::new(2, 1, 1.0)).is_err(), "dissonant update committed")?;
    ensure(t.history_valid() && t.commits() == 1 && t.rollbacks().len() == 1, "rollback bookkeeping wrong")
}

fn trace_verifies_and_detects_tampering() -> Result<(), String> {
    let trace = standard_execution()?.trace();
    trace.verify().map_err(|e| format!("{e:?}"))?;
    ensure(trace.certificates().len() == 1, "certificate missing from trace")?;
    let mut entries = trace.entries().to_vec();
    let last = entries.len() - 1;
    entries[last].label.push('!');
    ensure(RuntimeTrace::from_entries(entries).is_err(), "edited certificate not detected")
}

fn depth_limit_is_enforced() -> Result<(), String> {
    let mut r = RecursionBinding::new("r", 2);
    r.push(GapTensorNode::new(2, 1, 1.0)).map_err(|e| format!("{e:?}"))?;
    r.push(GapTensorNode::new(3, 1, 1.0)).map_err(|e| format!("{e:?}"))?;
    ensure(r.push(GapTensorNode::new(5, 1, 1.0)).is_err(), "depth limit ignored")?;
    ensure(certify(&[&r]).all_hold(), "depth claims should hold")
}

/// Run every scenario.
pub fn run_runtime_integration() -> RuntimeIntegrationReport {
    type Scenario = fn() -> Result<(), String>;
    let scenarios: [(&'static str, Scenario); 6] = [
        ("clean_execution_is_certified", clean_execution_is_certified),
        ("invariant_violations_are_certified_as_failures", invariant_violations_are_certified_as_failures),
        ("runtime_checker_agrees_with_recordings", runtime_checker_agrees_with_recordings),
        ("rollbacks_keep_state_valid", rollbacks_keep_state_valid),
        ("trace_verifies_and_detects_tampering", trace_verifies_and_detects_tampering),
        ("depth_limit_is_enforced", depth_limit_is_enforced),
    ];
    RuntimeIntegrationReport {
        scenarios: scenarios
            .iter()
            .map(|&(name, run)| ScenarioResult {
                name,
                failure: run().err(),
            })
            .collect(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_scenario_passes() {
        let report = run_runtime_integration();
        assert_eq!(report.scenarios.len(), 6);
        assert!(report.all_passed(), "{:?}", report.failures());
    }
}
