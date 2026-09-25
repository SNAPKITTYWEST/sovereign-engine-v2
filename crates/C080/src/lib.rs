//! lean_obligation_aggregator
//!
//! Aggregate all proof obligations from Tier 7 lemma libraries.

#![warn(missing_docs)]

use std::collections::BTreeMap;

pub use type_checking_interface::{LeanType, ProofTerm, TypeContext};
pub use obligation_management::{Obligation, ObligationManager, ObligationStatus};

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
    /// Completion percentage
    pub completion_percent: f64,
    /// Obligations grouped by tier
    pub by_tier: BTreeMap<usize, ObligationStats>,
}

/// Statistics for a single tier
#[derive(Clone, Debug)]
pub struct ObligationStats {
    /// Tier number
    pub tier: usize,
    /// Number of obligations in this tier
    pub count: usize,
    /// Number closed in this tier
    pub closed: usize,
}

impl AggregatedObligationReport {
    /// Create from an obligation manager
    pub fn from_manager(manager: &ObligationManager) -> Self {
        let total = manager.obligations.len();
        let closed = manager.count_closed();
        let open = manager.count_open();
        let failed = total - closed - open;
        let completion_percent = if total == 0 {
            100.0
        } else {
            (closed as f64 / total as f64) * 100.0
        };

        let mut by_tier: BTreeMap<usize, ObligationStats> = BTreeMap::new();

        for (_, obl) in &manager.obligations {
            // Extract tier from obligation ID (format: "tier_N_...")
            let tier = extract_tier_from_id(&obl.id).unwrap_or(0);
            let entry = by_tier
                .entry(tier)
                .or_insert_with(|| ObligationStats {
                    tier,
                    count: 0,
                    closed: 0,
                });
            entry.count += 1;
            if obl.status == ObligationStatus::Closed {
                entry.closed += 1;
            }
        }

        Self {
            total,
            closed,
            open,
            failed,
            completion_percent,
            by_tier,
        }
    }

    /// Check if all obligations are closed
    pub fn all_closed(&self) -> bool {
        self.open == 0 && self.failed == 0
    }

    /// Get completion status
    pub fn status_string(&self) -> String {
        format!(
            "{}/{} obligations proven ({:.1}%)",
            self.closed, self.total, self.completion_percent
        )
    }
}

/// Extract tier number from obligation ID
fn extract_tier_from_id(id: &str) -> Option<usize> {
    // Simple extraction: look for "tier_N" pattern
    let parts: Vec<&str> = id.split('_').collect();
    if parts.len() >= 2 && parts[0] == "tier" {
        parts[1].parse::<usize>().ok()
    } else {
        None
    }
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
    /// Create a new full context
    pub fn new() -> Self {
        let manager = ObligationManager::new();
        let report = AggregatedObligationReport::from_manager(&manager);
        Self { manager, report }
    }

    /// Add an obligation to the context
    pub fn add_obligation(&mut self, obligation: Obligation) {
        self.manager.add_obligation(obligation);
        self.report = AggregatedObligationReport::from_manager(&self.manager);
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
            "Tier 7 Obligations: {} total, {} closed, {} open, {} failed\n{}",
            self.report.total,
            self.report.closed,
            self.report.open,
            self.report.failed,
            self.report.status_string()
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
        let manager = ObligationManager::new();
        let report = AggregatedObligationReport::from_manager(&manager);
        assert_eq!(report.total, 0);
        assert_eq!(report.completion_percent, 100.0);
    }

    #[test]
    fn test_aggregated_report_with_obligations() {
        let mut manager = ObligationManager::new();
        let mut obl1 = Obligation::new("tier_2_test1".to_string(), LeanType::prop());
        obl1.prove(ProofTerm::Trivial);
        let obl2 = Obligation::new("tier_2_test2".to_string(), LeanType::prop());

        manager.add_obligation(obl1);
        manager.add_obligation(obl2);

        let report = AggregatedObligationReport::from_manager(&manager);
        assert_eq!(report.total, 2);
        assert_eq!(report.closed, 1);
        assert_eq!(report.open, 1);
        assert_eq!(report.completion_percent, 50.0);
    }

    #[test]
    fn test_extract_tier_from_id() {
        assert_eq!(extract_tier_from_id("tier_2_test"), Some(2));
        assert_eq!(extract_tier_from_id("tier_7_lemma"), Some(7));
        assert_eq!(extract_tier_from_id("notier_1"), None);
    }

    #[test]
    fn test_full_obligation_context() {
        let mut ctx = FullObligationContext::new();
        let obl = Obligation::new("tier_3_test".to_string(), LeanType::prop());
        ctx.add_obligation(obl);
        assert!(!ctx.is_complete());
    }

    #[test]
    fn test_full_obligation_context_statistics() {
        let ctx = FullObligationContext::new();
        let stats = ctx.statistics();
        assert!(stats.contains("Tier 7 Obligations"));
    }
}
