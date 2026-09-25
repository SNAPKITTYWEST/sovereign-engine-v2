//! rust_lean_correspondence
//!
//! The correspondence between runtime claims (Rust) and proof obligations
//! (the Lean-style layer). For every runtime claim, a certificate must hold
//! exactly one obligation whose statement is the claim's statement. The
//! obligation is closed if and only if an independent re-check of the claim
//! succeeds; a closed obligation's proof must type-check against its
//! statement with `Computed` evidence; a failed one carries no proof; and the
//! certificate's digests must match the sources' histories.
//!
//! [`check_certificates_discharge_obligations`] checks this over real
//! executions that deliberately include failing claims.

#![warn(missing_docs)]

pub use certificate_generation::{certify, claim_obligation_id, ExecutionCertificate, ObligationStatus};
pub use cross_layer_types::CorrespondenceReport;
use cross_layer_types::{vector_state, ClaimSource, GapTensorNode};
use multiplicity_state_binding::{ArenaBinding, ArenaLayout, Region};
use prime_state_binding::PrimeStateBinding;
use recursion_runtime_binding::RecursionBinding;
use tensor_runtime_binding::TensorBinding;
use type_checking_interface::{Evidence, LeanType, TypeContext};

/// Lean statement of a runtime claim, as written into certificates.
pub fn lean_statement(source: &str, statement: &str) -> LeanType {
    LeanType::atom(format!("[{source}] {statement}"))
}

/// Check `cert` against the sources it was issued for.
pub fn check_certificate_against_sources(
    cert: &ExecutionCertificate,
    sources: &[&dyn ClaimSource],
    report: &mut CorrespondenceReport,
) {
    let mut expected = 0;
    for source in sources {
        let name = source.source_name();
        report.check(cert.digests.get(name) == Some(&source.digest()), || format!("{name}: digest mismatch"));
        for claim in source.claims() {
            expected += 1;
            let id = claim_obligation_id(name, &claim.id);
            let Some(obligation) = cert.obligations.get_obligation(&id) else {
                report.error(format!("{id}: missing obligation"));
                continue;
            };
            let statement = lean_statement(name, &claim.statement);
            report.check(obligation.proposition == statement, || format!("{id}: statement differs"));
            let holds = source.recheck(&claim.id).is_ok();
            match obligation.status {
                ObligationStatus::Closed => {
                    report.check(holds, || format!("{id}: closed although the claim fails"));
                    let proof_ok = obligation.proof.as_ref().map_or(false, |p| {
                        TypeContext::new().check(p, &statement).is_ok() && p.evidence() == Evidence::Computed
                    });
                    report.check(proof_ok, || format!("{id}: proof missing, ill-typed or not computed"));
                }
                ObligationStatus::Failed => {
                    report.check(!holds, || format!("{id}: failed although the claim holds"));
                    report.check(obligation.proof.is_none(), || format!("{id}: failed obligation carries a proof"));
                }
                other => report.error(format!("{id}: unexpected status {other:?}")),
            }
        }
    }
    report.check(cert.obligations.obligations.len() == expected, || {
        format!("{} obligations for {expected} claims", cert.obligations.obligations.len())
    });
}

/// Real executions, some with deliberately failing claims.
pub struct Executions {
    /// Clean tensor run.
    pub clean_tensor: TensorBinding,
    /// Tensor run that introduces dissonance.
    pub dissonant_tensor: TensorBinding,
    /// Prime engine run.
    pub primes: PrimeStateBinding,
    /// Sealed arena, untouched after sealing.
    pub sealed_arena: ArenaBinding,
    /// Sealed arena modified behind the binding's back.
    pub tampered_arena: ArenaBinding,
    /// Clean solver run.
    pub clean_recursion: RecursionBinding,
    /// Solver run whose depth bookkeeping is corrupted.
    pub desynced_recursion: RecursionBinding,
}

impl Executions {
    /// All executions as claim sources.
    pub fn sources(&self) -> Vec<&dyn ClaimSource> {
        vec![
            &self.clean_tensor,
            &self.dissonant_tensor,
            &self.primes,
            &self.sealed_arena,
            &self.tampered_arena,
            &self.clean_recursion,
            &self.desynced_recursion,
        ]
    }
}

fn tensor(name: &str, second: u32) -> Result<TensorBinding, String> {
    let mut t = TensorBinding::new(name, vector_state(vec![GapTensorNode::new(2, 1, 1.0), GapTensorNode::NIL]));
    t.set_node(1, GapTensorNode::new(second, 1, 1.0)).map_err(|e| e.to_string())?;
    Ok(t)
}

fn sealed_arena(name: &str) -> Result<ArenaBinding, String> {
    let layout = ArenaLayout::new(1, 2, 1, 1).map_err(|e| e.to_string())?;
    let mut a = ArenaBinding::new(name, layout).map_err(|e| e.to_string())?;
    a.write_data(&[GapTensorNode::new(5, 1, 1.0)]).map_err(|e| e.to_string())?;
    a.seal().map_err(|e| e.to_string())?;
    Ok(a)
}

/// Build the executions.
pub fn standard_executions() -> Result<Executions, String> {
    let mut tampered_arena = sealed_arena("tampered_arena")?;
    let data_start = tampered_arena.layout().span(Region::Data).start;
    // SAFETY: data_start < layout.total() == arena.len().
    unsafe {
        tampered_arena
            .arena_mut_for_testing()
            .set_node(data_start, GapTensorNode::new(7, 1, 1.0))
    };

    let mut clean_recursion = RecursionBinding::new("clean_recursion", 4);
    let mut desynced_recursion = RecursionBinding::new("desynced_recursion", 4);
    for p in [2, 3] {
        clean_recursion.push(GapTensorNode::new(p, 1, 1.0)).map_err(|e| format!("{e:?}"))?;
        desynced_recursion.push(GapTensorNode::new(p, 1, 1.0)).map_err(|e| format!("{e:?}"))?;
    }
    desynced_recursion.state_mut_for_testing().increase_depth();

    Ok(Executions {
        clean_tensor: tensor("clean_tensor", 3)?,
        dissonant_tensor: tensor("dissonant_tensor", 13)?,
        primes: PrimeStateBinding::run("primes", 300).map_err(|e| format!("{e:?}"))?,
        sealed_arena: sealed_arena("sealed_arena")?,
        tampered_arena,
        clean_recursion,
        desynced_recursion,
    })
}

/// Certificates close exactly the claims that hold, per source and for all
/// sources together.
pub fn check_certificates_discharge_obligations() -> CorrespondenceReport {
    let mut report = CorrespondenceReport::new("certificates_discharge_obligations");
    let executions = match standard_executions() {
        Ok(e) => e,
        Err(e) => {
            report.error(e);
            return report;
        }
    };
    let sources = executions.sources();
    for source in &sources {
        check_certificate_against_sources(&certify(&[*source]), &[*source], &mut report);
    }
    check_certificate_against_sources(&certify(&sources), &sources, &mut report);
    report
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn correspondence_holds_including_failing_claims() {
        let report = check_certificates_discharge_obligations();
        assert!(report.holds(), "{:?}", report.failures);
        let executions = standard_executions().unwrap();
        let cert = certify(&executions.sources());
        assert!(cert.failed() >= 3, "expected the deliberate failures, got {}", cert.failed());
        assert!(cert.closed() > cert.failed());
    }

    #[test]
    fn tampered_certificates_are_caught() {
        let executions = standard_executions().unwrap();
        let sources = executions.sources();
        let mut cert = certify(&sources);
        let id = claim_obligation_id("dissonant_tensor", "invariants_hold");
        cert.obligations.get_obligation_mut(&id).unwrap().status = ObligationStatus::Closed;
        let mut report = CorrespondenceReport::new("tampered");
        check_certificate_against_sources(&cert, &sources, &mut report);
        assert!(!report.holds());

        let mut cert = certify(&sources);
        cert.digests.insert("primes".into(), 0);
        let mut report = CorrespondenceReport::new("digest");
        check_certificate_against_sources(&cert, &sources, &mut report);
        assert!(!report.holds());
    }
}
