//! lean_obligation_aggregator
//!
//! Aggregates every proof obligation of the pipeline: each tier lemma
//! (`tier_{N}_{name}`) and each cross-layer lemma (`tier_9_{id}`, depending
//! on its tier premises). Proven lemmas are discharged through the
//! obligation manager (so their proofs are type-checked again), refuted ones
//! are marked failed, and the report states exactly what is closed, open or
//! failed, broken down by tier and by evidence grade.

#![warn(missing_docs)]

pub use cross_layer_lemmas_library::{CrossLayerLemmaLibrary, STANDARD_CORRESPONDENCES};
use std::collections::BTreeMap;

pub use obligation_management::{
    DischargeError, Evidence, Obligation, ObligationManager, ObligationStatus,
};
pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};

/// Overall verification status.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum VerificationStatus {
    /// Every obligation closed, none resting on an axiom.
    Complete,
    /// Every obligation closed, but some rest on axioms.
    CompleteWithAssumptions,
    /// Some obligations are open or failed.
    Incomplete,
}

/// Aggregated proof obligation report
#[derive(Clone, Debug)]
pub struct AggregatedObligationReport {
    /// Total number of obligations
    pub total: usize,
    /// Number of closed obligations
    pub closed: usize,
    /// Number of open obligations
    pub open: usize,
    /// Number of failed obligations
    pub failed: usize,
    /// Number of obligations in progress
    pub in_progress: usize,
    /// Completion percentage
    pub completion_percent: f64,
    /// Obligations grouped by tier (ids of the form `tier_N_…`)
    pub by_tier: BTreeMap<usize, ObligationStats>,
    /// Obligations whose id carries no tier
    pub unclassified: ObligationStats,
    /// Closed obligations by evidence grade
    pub evidence: BTreeMap<Evidence, usize>,
    /// Ids of open obligations
    pub open_ids: Vec<String>,
    /// Ids of failed obligations
    pub failed_ids: Vec<String>,
}

/// Statistics for a group of obligations
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ObligationStats {
    /// Tier number (0 for the unclassified group)
    pub tier: usize,
    /// Number of obligations in this group
    pub count: usize,
    /// Number closed in this group
    pub closed: usize,
}

impl AggregatedObligationReport {
    /// Create from an obligation manager
    pub fn from_manager(manager: &ObligationManager) -> Self {
        let total = manager.obligations.len();
        let closed = manager.count_closed();
        let open = manager.count_open();
        let failed = manager.count_status(ObligationStatus::Failed);
        let in_progress = manager.count_status(ObligationStatus::InProgress);
        let completion_percent = if total == 0 {
            100.0
        } else {
            closed as f64 / total as f64 * 100.0
        };

        let mut by_tier: BTreeMap<usize, ObligationStats> = BTreeMap::new();
        let mut unclassified = ObligationStats::default();
        let mut open_ids = Vec::new();
        let mut failed_ids = Vec::new();
        for obl in manager.obligations.values() {
            let entry = match extract_tier_from_id(&obl.id) {
                Some(tier) => by_tier.entry(tier).or_insert_with(|| ObligationStats {
                    tier,
                    ..ObligationStats::default()
                }),
                None => &mut unclassified,
            };
            entry.count += 1;
            match obl.status {
                ObligationStatus::Closed => entry.closed += 1,
                ObligationStatus::Open => open_ids.push(obl.id.clone()),
                ObligationStatus::Failed => failed_ids.push(obl.id.clone()),
                ObligationStatus::InProgress => {}
            }
        }

        Self {
            total,
            closed,
            open,
            failed,
            in_progress,
            completion_percent,
            by_tier,
            unclassified,
            evidence: manager.evidence_counts(),
            open_ids,
            failed_ids,
        }
    }

    /// Check if all obligations are closed
    pub fn all_closed(&self) -> bool {
        self.closed == self.total
    }

    /// Overall status.
    pub fn status(&self) -> VerificationStatus {
        if !self.all_closed() {
            VerificationStatus::Incomplete
        } else if self.evidence.get(&Evidence::Assumed).copied().unwrap_or(0) > 0 {
            VerificationStatus::CompleteWithAssumptions
        } else {
            VerificationStatus::Complete
        }
    }

    /// Get completion status
    pub fn status_string(&self) -> String {
        format!(
            "{}/{} obligations proven ({:.1}%)",
            self.closed, self.total, self.completion_percent
        )
    }
}

/// Tier number from an id of the form `tier_N_…`.
pub fn extract_tier_from_id(id: &str) -> Option<usize> {
    let mut parts = id.split('_');
    match (parts.next(), parts.next()) {
        (Some("tier"), Some(n)) => n.parse().ok(),
        _ => None,
    }
}

/// Obligation id of a tier lemma.
pub fn tier_obligation_id(tier: usize, name: &str) -> String {
    format!("tier_{tier}_{name}")
}

/// Obligation id of a cross-layer lemma.
pub fn cross_layer_obligation_id(id: &str) -> String {
    format!("tier_9_{id}")
}

/// Build the obligation manager for a cross-layer library and the tier
/// lemmas it imported. Proven lemmas are discharged (their proofs are
/// re-checked), refuted ones are marked failed.
pub fn collect_obligations(lib: &CrossLayerLemmaLibrary) -> Result<ObligationManager, DischargeError> {
    let mut manager = ObligationManager::new();
    let mut qualified_to_id = BTreeMap::new();
    for record in lib.tier_lemmas.values() {
        let id = tier_obligation_id(record.tier, &record.name);
        qualified_to_id.insert(record.qualified_name(), id.clone());
        manager.add_obligation(Obligation::new(id.clone(), record.statement.clone()));
        if let Some(proof) = &record.proof {
            manager.discharge(&id, proof.clone())?;
        } else if record.failed {
            manager.mark_failed(&id)?;
        }
    }
    for lemma in lib.lemmas.values() {
        let id = cross_layer_obligation_id(&lemma.id);
        let mut obligation = Obligation::new(id.clone(), lemma.statement.clone());
        for premise in &lemma.premises {
            obligation.add_dependency(qualified_to_id.get(premise).cloned().unwrap_or_else(|| premise.clone()));
        }
        manager.add_obligation(obligation);
        if let Some(proof) = &lemma.proof {
            manager.discharge(&id, proof.clone())?;
        }
    }
    Ok(manager)
}

/// Full aggregation context combining all obligations
#[derive(Clone, Debug)]
pub struct FullObligationContext {
    /// Master obligation manager
    pub manager: ObligationManager,
    /// Report snapshot
    pub report: AggregatedObligationReport,
}

impl FullObligationContext {
    /// Create an empty context
    pub fn new() -> Self {
        let manager = ObligationManager::new();
        let report = AggregatedObligationReport::from_manager(&manager);
        Self { manager, report }
    }

    /// Aggregate a cross-layer library and its imported tier lemmas.
    pub fn from_library(lib: &CrossLayerLemmaLibrary) -> Result<Self, DischargeError> {
        let manager = collect_obligations(lib)?;
        let report = AggregatedObligationReport::from_manager(&manager);
        Ok(Self { manager, report })
    }

    /// Aggregate the standard libraries (cross-layer lemmas not yet decided).
    pub fn standard() -> Result<Self, DischargeError> {
        Self::from_library(&CrossLayerLemmaLibrary::standard())
    }

    /// Add an obligation to the context
    pub fn add_obligation(&mut self, obligation: Obligation) {
        self.manager.add_obligation(obligation);
        self.refresh_report();
    }

    /// Update the report
    pub fn refresh_report(&mut self) {
        self.report = AggregatedObligationReport::from_manager(&self.manager);
    }

    /// Check overall completion
    pub fn is_complete(&self) -> bool {
        self.report.all_closed()
    }

    /// Get aggregated statistics
    pub fn statistics(&self) -> String {
        format!(
            "Obligations: {} total, {} closed, {} open, {} failed\n{}\nEvidence: {:?}",
            self.report.total,
            self.report.closed,
            self.report.open,
            self.report.failed,
            self.report.status_string(),
            self.report.evidence
        )
    }
}

impl Default for FullObligationContext {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_aggregated_report_empty() {
        let report = AggregatedObligationReport::from_manager(&ObligationManager::new());
        assert_eq!(report.total, 0);
        assert_eq!(report.completion_percent, 100.0);
        assert_eq!(report.status(), VerificationStatus::Complete);
    }

    #[test]
    fn test_aggregated_report_with_obligations() {
        let mut manager = ObligationManager::new();
        let mut obl1 = Obligation::new("tier_2_test1".to_string(), LeanType::truth());
        obl1.prove(ProofTerm::Trivial).unwrap();
        manager.add_obligation(obl1);
        manager.add_obligation(Obligation::new("tier_2_test2".to_string(), LeanType::atom("P")));
        manager.add_obligation(Obligation::new("orphan".to_string(), LeanType::atom("Q")));

        let report = AggregatedObligationReport::from_manager(&manager);
        assert_eq!((report.total, report.closed, report.open), (3, 1, 2));
        assert_eq!(report.by_tier[&2].count, 2);
        assert_eq!(report.unclassified.count, 1);
        assert!(!report.by_tier.contains_key(&0));
        assert_eq!(report.status(), VerificationStatus::Incomplete);
    }

    #[test]
    fn test_extract_tier_from_id() {
        assert_eq!(extract_tier_from_id("tier_2_test"), Some(2));
        assert_eq!(extract_tier_from_id("tier_7_lemma"), Some(7));
        assert_eq!(extract_tier_from_id("notier_1"), None);
        assert_eq!(extract_tier_from_id("tier_x_bad"), None);
    }

    #[test]
    fn standard_aggregation_is_honest() {
        let ctx = FullObligationContext::standard().unwrap();
        let r = &ctx.report;
        assert_eq!(r.closed, 38);
        assert_eq!(r.failed, 0);
        assert_eq!(r.open, 9 + 8);
        assert_eq!(r.total, 38 + 9 + 8);
        assert_eq!(r.evidence.get(&Evidence::Computed), Some(&38));
        assert_eq!(r.unclassified.count, 0);
        assert_eq!(r.status(), VerificationStatus::Incomplete);
        assert!(r.open_ids.contains(&"tier_5_tor_balanced".to_string()));
        assert!(!ctx.is_complete());
    }

    #[test]
    fn deciding_cross_layer_lemmas_updates_the_report() {
        let mut lib = CrossLayerLemmaLibrary::standard();
        lib.decide("candidate_gaps_match_engine", "stub_for_test", || Ok(1)).unwrap();
        let ctx = FullObligationContext::from_library(&lib).unwrap();
        assert_eq!(ctx.report.closed, 39);
        assert_eq!(ctx.report.by_tier[&9].closed, 1);
    }

    #[test]
    fn assumptions_are_reported() {
        let mut manager = ObligationManager::new();
        manager.context.add_axiom("ax".into(), LeanType::atom("P"));
        manager.add_obligation(Obligation::new("tier_1_p".into(), LeanType::atom("P")));
        manager.discharge("tier_1_p", ProofTerm::axiom("ax")).unwrap();
        let report = AggregatedObligationReport::from_manager(&manager);
        assert_eq!(report.status(), VerificationStatus::CompleteWithAssumptions);
    }
}
