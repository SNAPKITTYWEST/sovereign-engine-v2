//! end_to_end_trace_verification
//!
//! End-to-end check of a whole runtime execution: the standard execution of
//! all four bindings is certified and recorded in one trace; every state in
//! the trace must replay to exactly the binding's recorded snapshot, the
//! certificate entry must equal the issued certificate, and every kind of
//! tampering (payload bit flip, label edit, deletion, reordering) must be
//! detected.

#![warn(missing_docs)]

use runtime_bridge_tests_integration::{standard_execution, StandardExecution};
use runtime_state_snapshot::{tensors_bitwise_equal, SnapshotStore};
pub use rust_lean_correspondence::CorrespondenceReport;
use rust_lean_correspondence::check_certificates_discharge_obligations;
use trace_recording_runtime::{EntryKind, RuntimeTrace};

fn store_of<'a>(run: &'a StandardExecution, source: &str) -> Option<&'a SnapshotStore> {
    match source {
        "tensor" => Some(run.tensor.store()),
        "primes" => Some(run.primes.store()),
        "arena" => Some(run.arena.store()),
        "recursion" => Some(run.recursion.store()),
        _ => None,
    }
}

/// Replay the standard execution's trace and try to tamper with it.
pub fn check_trace_replay_matches_execution() -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("trace_replay_matches_execution");
    let run = match standard_execution() {
        Ok(run) => run,
        Err(e) => {
            report.error(e);
            return report;
        }
    };
    let trace = run.trace();
    report.check(trace.verify().is_ok(), || "untouched trace does not verify".into());

    let certificate = run.certificate().summary();
    for i in 0..trace.len() {
        match trace.kind(i) {
            Some(EntryKind::State { source, step }) => {
                let recorded = store_of(&run, &source).and_then(|s| s.get(step as usize));
                match (recorded, trace.replay(i)) {
                    (Some(snapshot), Ok(state)) => report.check(tensors_bitwise_equal(&state, &snapshot.tensor), || {
                        format!("entry {i} ({source}#{step}) replays differently")
                    }),
                    _ => report.error(format!("entry {i} ({source}#{step}) cannot be matched")),
                }
            }
            Some(EntryKind::Certificate(label)) => {
                report.check(label == certificate, || format!("entry {i}: certificate differs"))
            }
            other => report.error(format!("entry {i}: unexpected {other:?}")),
        }
    }

    let entries = trace.entries().to_vec();
    let mut flipped = entries.clone();
    flipped[0].payload[20] ^= 1;
    report.check(RuntimeTrace::from_entries(flipped).is_err(), || "payload bit flip not detected".into());
    let mut relabelled = entries.clone();
    let last = relabelled.len() - 1;
    relabelled[last].label = relabelled[last].label.replace("failed=0", "failed=1");
    report.check(RuntimeTrace::from_entries(relabelled).is_err(), || "certificate edit not detected".into());
    let mut shortened = entries.clone();
    shortened.remove(1);
    report.check(RuntimeTrace::from_entries(shortened).is_err(), || "deleted entry not detected".into());
    let mut reordered = entries;
    reordered.swap(1, 2);
    report.check(RuntimeTrace::from_entries(reordered).is_err(), || "reordering not detected".into());
    report
}

/// All end-to-end checks: trace replay and certificate correspondence.
pub fn run_end_to_end() -> Vec<CorrespondenceReport> {
    vec![check_trace_replay_matches_execution(), check_certificates_discharge_obligations()]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn end_to_end_checks_hold() {
        for report in run_end_to_end() {
            assert!(report.holds(), "{}: {:?}", report.name, report.failures);
        }
        assert!(check_trace_replay_matches_execution().cases_checked > 10);
    }
}
