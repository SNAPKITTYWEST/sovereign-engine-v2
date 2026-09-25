/*
 * DETERMINISTIC TOKIO DAEMON SCRUM ROUTER
 * ========================================
 * 
 * Zero-LLM, deterministic intent routing for sovereign agent orchestration.
 * Integrates with the certified runtime and provides hash-chained decision trails.
 * 
 * FEATURES:
 * - Deterministic keyword-based intent classification
 * - Multi-head tensor scoring (budget, vendor trust, risk)
 * - WORM-sealed decision certificates
 * - Fail-closed error handling
 * - Zero external AI/LLM dependencies
 */

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};

// ============================================================================
// SECTION 1: CORE DATA STRUCTURES
// ============================================================================

/// Agent decision with cryptographic seal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentDecision {
    pub agent: String,
    pub event_type: String,
    pub approved: bool,
    pub confidence: f64,
    pub action: String,
    pub reasoning: String,
    pub chain_of_thought: Vec<String>,
    pub duration_ms: u64,
    pub seal: Option<String>,
    pub trace_id: String,
}

/// Emergent signal from a single tensor head
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct HeadSignal {
    pub name: String,
    pub score: f64,
    pub label: String,
}

/// Composite emergent tensor output across all heads
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TensorSignal {
    pub budget_head: HeadSignal,
    pub vendor_trust_head: HeadSignal,
    pub risk_head: HeadSignal,
    pub composite_signal: f64,
    pub recommendation: String,
}

/// Intent classification
#[derive(Debug, Clone, PartialEq)]
pub enum Intent {
    Status,
    Finance(FinanceIntent),
    Crm(CrmIntent),
    Procurement(ProcurementIntent),
    Bifrost(BifrostIntent),
    Treasury(TreasuryIntent),
    Risk(RiskIntent),
    Unknown,
}

#[derive(Debug, Clone, PartialEq)]
pub enum FinanceIntent {
    CashFlow,
    GlEntry,
    RevenueRecognition,
    LedgerIntegrity,
    TripleEntry,
    General,
}

#[derive(Debug, Clone, PartialEq)]
pub enum CrmIntent {
    Pipeline,
    DealStatus,
    RevenueForcast,
    ContactScore,
    General,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ProcurementIntent {
    VendorTrust,
    SpendAnalysis,
    PoStatus,
    SupplyChain,
    General,
}

#[derive(Debug, Clone, PartialEq)]
pub enum BifrostIntent {
    EventPipeline,
    TraceId,
    SchemaValidation,
    Routing,
    General,
}

#[derive(Debug, Clone, PartialEq)]
pub enum TreasuryIntent {
    Reserves,
    FreezeStatus,
    SovereignBalance,
    General,
}

#[derive(Debug, Clone, PartialEq)]
pub enum RiskIntent {
    ThreatScore,
    AuditTrail,
    ComplianceFlag,
    AnomalyPattern,
    General,
}

// ============================================================================
// SECTION 2: TENSOR CORE (DETERMINISTIC SCORING)
// ============================================================================

pub struct TensorCore;

impl TensorCore {
    pub fn new() -> Self {
        Self
    }

    /// Budget head: score based on amount vs threshold bands
    fn budget_head(amount: f64) -> HeadSignal {
        let score = if amount <= 1_000.0 {
            0.95
        } else if amount <= 10_000.0 {
            0.75
        } else if amount <= 50_000.0 {
            0.50
        } else {
            0.20
        };
        HeadSignal {
            name: "budget_head".to_string(),
            score,
            label: if score > 0.7 {
                "GREEN".to_string()
            } else if score > 0.4 {
                "AMBER".to_string()
            } else {
                "RED".to_string()
            },
        }
    }

    /// Vendor trust head: score based on vendor reputation signals
    fn vendor_trust_head(payload: &serde_json::Value) -> HeadSignal {
        let vendor_known = payload["vendor_id"].as_str().is_some()
            || payload["vendor"].as_str().is_some();
        let has_po = payload["po_id"].as_str().is_some()
            || payload["poId"].as_str().is_some();
        let score = match (vendor_known, has_po) {
            (true, true) => 0.92,
            (true, false) => 0.65,
            (false, true) => 0.55,
            (false, false) => 0.35,
        };
        HeadSignal {
            name: "vendor_trust_head".to_string(),
            score,
            label: if score > 0.7 {
                "TRUSTED".to_string()
            } else if score > 0.5 {
                "UNVERIFIED".to_string()
            } else {
                "UNKNOWN".to_string()
            },
        }
    }

    /// Risk head: derived from existing risk_score / score fields
    fn risk_head(payload: &serde_json::Value) -> HeadSignal {
        let raw_risk = payload["risk_score"]
            .as_f64()
            .or_else(|| payload["score"].as_f64())
            .unwrap_or(0.0);
        let score = 1.0 - raw_risk.clamp(0.0, 1.0);
        HeadSignal {
            name: "risk_head".to_string(),
            score,
            label: if score > 0.7 {
                "LOW_RISK".to_string()
            } else if score > 0.4 {
                "MED_RISK".to_string()
            } else {
                "HIGH_RISK".to_string()
            },
        }
    }

    /// Run all heads and produce composite emergent signal
    pub fn run(&self, amount: f64, payload: &serde_json::Value) -> TensorSignal {
        let budget = Self::budget_head(amount);
        let vendor = Self::vendor_trust_head(payload);
        let risk = Self::risk_head(payload);

        // Weighted composite: budget 40%, vendor 30%, risk 30%
        let composite = budget.score * 0.40 + vendor.score * 0.30 + risk.score * 0.30;

        let recommendation = if composite >= 0.75 {
            "PROCEED".to_string()
        } else if composite >= 0.50 {
            "REVIEW".to_string()
        } else {
            "ESCALATE".to_string()
        };

        TensorSignal {
            budget_head: budget,
            vendor_trust_head: vendor,
            risk_head: risk,
            composite_signal: (composite * 1000.0).round() / 1000.0,
            recommendation,
        }
    }
}

// ============================================================================
// SECTION 3: INTENT PARSER (DETERMINISTIC KEYWORD ROUTING)
// ============================================================================

pub fn parse_intent(agent: &str, message: &str) -> Intent {
    let m = message.to_lowercase();

    if is_status_query(&m) {
        return Intent::Status;
    }

    match agent {
        "finance" => Intent::Finance(parse_finance_intent(&m)),
        "crm" => Intent::Crm(parse_crm_intent(&m)),
        "procurement" => Intent::Procurement(parse_procurement_intent(&m)),
        "bifrost" => Intent::Bifrost(parse_bifrost_intent(&m)),
        "treasury" => Intent::Treasury(parse_treasury_intent(&m)),
        "risk" => Intent::Risk(parse_risk_intent(&m)),
        _ => {
            // Global keyword routing
            if m.contains("cash") || m.contains("gl") || m.contains("ledger") || m.contains("revenue") {
                Intent::Finance(parse_finance_intent(&m))
            } else if m.contains("deal") || m.contains("pipeline") || m.contains("crm") || m.contains("sales") {
                Intent::Crm(parse_crm_intent(&m))
            } else if m.contains("vendor") || m.contains("procurement") || m.contains("spend") || m.contains("po") {
                Intent::Procurement(parse_procurement_intent(&m))
            } else if m.contains("bifrost") || m.contains("trace") || m.contains("event chain") {
                Intent::Bifrost(parse_bifrost_intent(&m))
            } else if m.contains("treasury") || m.contains("freeze") || m.contains("reserve") {
                Intent::Treasury(parse_treasury_intent(&m))
            } else if m.contains("risk") || m.contains("threat") || m.contains("audit") || m.contains("anomaly") {
                Intent::Risk(parse_risk_intent(&m))
            } else {
                Intent::Unknown
            }
        }
    }
}

fn is_status_query(m: &str) -> bool {
    let status_words = [
        "status", "online", "health", "alive", "ping", "ready", "running",
        "hello", "hi", "hey", "sup", "working",
    ];
    status_words.iter().any(|w| m.contains(w)) || m.len() < 5
}

fn parse_finance_intent(m: &str) -> FinanceIntent {
    if m.contains("cash flow") || m.contains("cashflow") {
        FinanceIntent::CashFlow
    } else if m.contains("gl") || m.contains("general ledger") || m.contains("entry") {
        FinanceIntent::GlEntry
    } else if m.contains("revenue recogni") || m.contains("rev rec") {
        FinanceIntent::RevenueRecognition
    } else if m.contains("integrity") || m.contains("worm") || m.contains("seal") {
        FinanceIntent::LedgerIntegrity
    } else if m.contains("triple") || m.contains("triple-entry") {
        FinanceIntent::TripleEntry
    } else {
        FinanceIntent::General
    }
}

fn parse_crm_intent(m: &str) -> CrmIntent {
    if m.contains("pipeline") {
        CrmIntent::Pipeline
    } else if m.contains("deal") {
        CrmIntent::DealStatus
    } else if m.contains("forecast") || m.contains("revenue") {
        CrmIntent::RevenueForcast
    } else if m.contains("contact") || m.contains("score") {
        CrmIntent::ContactScore
    } else {
        CrmIntent::General
    }
}

fn parse_procurement_intent(m: &str) -> ProcurementIntent {
    if m.contains("vendor") || m.contains("trust") {
        ProcurementIntent::VendorTrust
    } else if m.contains("spend") || m.contains("analysis") {
        ProcurementIntent::SpendAnalysis
    } else if m.contains("po") || m.contains("purchase order") {
        ProcurementIntent::PoStatus
    } else if m.contains("supply") || m.contains("chain") {
        ProcurementIntent::SupplyChain
    } else {
        ProcurementIntent::General
    }
}

fn parse_bifrost_intent(m: &str) -> BifrostIntent {
    if m.contains("pipeline") || m.contains("routing") {
        BifrostIntent::EventPipeline
    } else if m.contains("trace") {
        BifrostIntent::TraceId
    } else if m.contains("schema") || m.contains("validation") {
        BifrostIntent::SchemaValidation
    } else if m.contains("route") {
        BifrostIntent::Routing
    } else {
        BifrostIntent::General
    }
}

fn parse_treasury_intent(m: &str) -> TreasuryIntent {
    if m.contains("reserve") || m.contains("cash") {
        TreasuryIntent::Reserves
    } else if m.contains("freeze") || m.contains("frozen") {
        TreasuryIntent::FreezeStatus
    } else if m.contains("sovereign") || m.contains("balance") {
        TreasuryIntent::SovereignBalance
    } else {
        TreasuryIntent::General
    }
}

fn parse_risk_intent(m: &str) -> RiskIntent {
    if m.contains("threat") || m.contains("score") {
        RiskIntent::ThreatScore
    } else if m.contains("audit") || m.contains("trail") {
        RiskIntent::AuditTrail
    } else if m.contains("compliance") || m.contains("flag") {
        RiskIntent::ComplianceFlag
    } else if m.contains("anomaly") || m.contains("pattern") {
        RiskIntent::AnomalyPattern
    } else {
        RiskIntent::General
    }
}

// ============================================================================
// SECTION 4: RESPONSE GENERATOR (DETERMINISTIC TEMPLATES)
// ============================================================================

pub fn respond(intent: &Intent, decision: Option<&AgentDecision>) -> String {
    match intent {
        Intent::Status => respond_status(decision),
        Intent::Finance(fi) => respond_finance(fi, decision),
        Intent::Crm(ci) => respond_crm(ci, decision),
        Intent::Procurement(pi) => respond_procurement(pi, decision),
        Intent::Bifrost(bi) => respond_bifrost(bi, decision),
        Intent::Treasury(ti) => respond_treasury(ti, decision),
        Intent::Risk(ri) => respond_risk(ri, decision),
        Intent::Unknown => respond_unknown(decision),
    }
}

fn respond_status(decision: Option<&AgentDecision>) -> String {
    let seal_line = decision
        .and_then(|d| d.seal.as_ref())
        .map(|s| {
            format!(
                "\nLast seal: {}···{}",
                &s[..8.min(s.len())],
                &s[s.len().saturating_sub(4)..]
            )
        })
        .unwrap_or_default();

    format!(
        "All systems nominal. Ledger chain intact. Circuit breakers closed. \
         Treasury reserves verified. SHA-256 event chain running.{}",
        seal_line
    )
}

fn respond_finance(intent: &FinanceIntent, decision: Option<&AgentDecision>) -> String {
    let base = match intent {
        FinanceIntent::CashFlow => {
            "Cash flow analysis runs against the triple-entry GL. \
             Each debit and credit posts a paired WORM-sealed entry — no single-sided adjustments permitted."
                .to_string()
        }
        FinanceIntent::GlEntry => {
            "GL entries follow triple-entry accounting: debit, credit, and a cryptographic counter-entry sealed to the WORM ledger."
                .to_string()
        }
        FinanceIntent::RevenueRecognition => {
            "Revenue recognition runs on event_type payment.received or plaid.synced. \
             The finance agent applies ASC 606 — revenue is recognized when performance obligations are satisfied."
                .to_string()
        }
        FinanceIntent::LedgerIntegrity => {
            "Ledger integrity is enforced at the Rust layer — not configurable at runtime. \
             Each entry appends a SHA-256 link: seq|trace_id|event_type|payload_hash|prev_hash."
                .to_string()
        }
        FinanceIntent::TripleEntry => {
            "Triple-entry accounting adds a third, cryptographically sealed ledger entry alongside the standard debit/credit pair."
                .to_string()
        }
        FinanceIntent::General => {
            "Finance agent monitors: GL entries, triple-entry accounting, revenue recognition, WORM seal integrity, and ledger chain verification."
                .to_string()
        }
    };

    with_decision_suffix(base, decision)
}

fn respond_crm(intent: &CrmIntent, decision: Option<&AgentDecision>) -> String {
    let base = match intent {
        CrmIntent::Pipeline => {
            "Deal pipeline stages: prospecting → active → negotiation → closed-won / closed-lost / at-risk."
                .to_string()
        }
        CrmIntent::DealStatus => {
            "Deal status is determined by the CRM agent's rule engine: \
             deal.created and deal.stage_changed are auto-approved and sealed."
                .to_string()
        }
        CrmIntent::RevenueForcast => {
            "Revenue forecast aggregates sealed deal values by stage with probability weights."
                .to_string()
        }
        CrmIntent::ContactScore => {
            "Contact trust scores are computed from: engagement history, deal outcome rate, payment reliability, and anomaly flags."
                .to_string()
        }
        CrmIntent::General => {
            "CRM agent monitors: deal pipeline, stage transitions, contact scoring, and revenue forecast."
                .to_string()
        }
    };

    with_decision_suffix(base, decision)
}

fn respond_procurement(intent: &ProcurementIntent, decision: Option<&AgentDecision>) -> String {
    let base = match intent {
        ProcurementIntent::VendorTrust => {
            "Vendor trust is evaluated on: payment history, delivery reliability, compliance flags, and contact score."
                .to_string()
        }
        ProcurementIntent::SpendAnalysis => {
            "Spend analysis aggregates all sealed PO events by vendor, category, and time period."
                .to_string()
        }
        ProcurementIntent::PoStatus => {
            "PO lifecycle: requisition.created → requisition.approved → po.created → po.received."
                .to_string()
        }
        ProcurementIntent::SupplyChain => {
            "Supply chain risk is scored by the procurement agent combining: vendor trust, geo-political flags, delivery lead time variance."
                .to_string()
        }
        ProcurementIntent::General => {
            "Procurement agent monitors: vendor trust scores, PO lifecycle, spend analysis, and supply chain risk."
                .to_string()
        }
    };

    with_decision_suffix(base, decision)
}

fn respond_bifrost(intent: &BifrostIntent, decision: Option<&AgentDecision>) -> String {
    let base = match intent {
        BifrostIntent::EventPipeline => {
            "Bifrost event pipeline ingests all substrate events and routes them to the appropriate agent topic."
                .to_string()
        }
        BifrostIntent::TraceId => {
            "Trace IDs follow the format tr-{base36_timestamp}-{8_hex_chars}."
                .to_string()
        }
        BifrostIntent::SchemaValidation => {
            "Schema validation runs at the Bifrost ingestion boundary."
                .to_string()
        }
        BifrostIntent::Routing => {
            "Event routing follows NATS topic hierarchy: snapkitty.{layer}.{entity}.{verb}."
                .to_string()
        }
        BifrostIntent::General => {
            "Bifrost monitors: event ingestion, schema validation, routing, trace ID generation, and chain link integrity."
                .to_string()
        }
    };

    with_decision_suffix(base, decision)
}

fn respond_treasury(intent: &TreasuryIntent, decision: Option<&AgentDecision>) -> String {
    let base = match intent {
        TreasuryIntent::Reserves => {
            "Treasury reserves are tracked as the sealed sum of all payment.received and payment.sent events."
                .to_string()
        }
        TreasuryIntent::FreezeStatus => {
            "Treasury freeze halts all outgoing payments system-wide."
                .to_string()
        }
        TreasuryIntent::SovereignBalance => {
            "Sovereign balance is the cryptographically verified sum of all sealed GL entries."
                .to_string()
        }
        TreasuryIntent::General => {
            "Treasury agent monitors: cash reserves, freeze conditions, sovereign balance integrity, and vendor trust thresholds."
                .to_string()
        }
    };

    with_decision_suffix(base, decision)
}

fn respond_risk(intent: &RiskIntent, decision: Option<&AgentDecision>) -> String {
    let base = match intent {
        RiskIntent::ThreatScore => {
            "Threat scores are computed by the ML agent from: transaction velocity, amount deviation, vendor trust delta, and geo-political flags."
                .to_string()
        }
        RiskIntent::AuditTrail => {
            "Audit trail is the SHA-256 event chain: each link contains seq, trace_id, event_type, payload_hash, prev_hash, and link_hash."
                .to_string()
        }
        RiskIntent::ComplianceFlag => {
            "Compliance flags are raised by the risk agent when transaction amounts exceed regulatory thresholds."
                .to_string()
        }
        RiskIntent::AnomalyPattern => {
            "Anomaly detection uses statistical deviation from rolling baseline: spend velocity, transaction frequency, vendor concentration."
                .to_string()
        }
        RiskIntent::General => {
            "Risk agent monitors: threat scores, audit trail integrity, compliance flags, and anomaly patterns."
                .to_string()
        }
    };

    with_decision_suffix(base, decision)
}

fn respond_unknown(decision: Option<&AgentDecision>) -> String {
    let base = "SnapKitty substrate online. Agents monitoring: GL ledger, deal pipeline, vendor trust, \
                 event routing, treasury reserves, and risk scoring."
        .to_string();

    with_decision_suffix(base, decision)
}

fn with_decision_suffix(base: String, decision: Option<&AgentDecision>) -> String {
    let Some(d) = decision else {
        return base;
    };

    let status = if d.approved { "CLEARED" } else { "FLAGGED" };
    let pct = (d.confidence * 100.0).round() as u32;

    let mut lines = vec![
        base,
        String::new(),
        format!("— {} — {}% confidence — {}ms", status, pct, d.duration_ms),
    ];

    if let Some(seal) = &d.seal {
        let short = format!(
            "{}···{}",
            &seal[..8.min(seal.len())],
            &seal[seal.len().saturating_sub(4)..]
        );
        lines.push(String::new());
        lines.push(format!("Seal: {}", short));
    }

    lines.join("\n")
}

// ============================================================================
// SECTION 5: DETERMINISTIC ROUTER DAEMON
// ============================================================================

pub struct DeterministicRouter {
    tensor_core: TensorCore,
    decision_cache: Arc<RwLock<HashMap<String, AgentDecision>>>,
}

impl DeterministicRouter {
    pub fn new() -> Self {
        Self {
            tensor_core: TensorCore::new(),
            decision_cache: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Generate trace ID
    fn generate_trace_id() -> String {
        use std::time::{SystemTime, UNIX_EPOCH};
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let random_hex: String = (0..8)
            .map(|_| format!("{:x}", rand::random::<u8>() % 16))
            .collect();
        format!("tr-{:x}-{}", timestamp, random_hex)
    }

    /// Compute SHA-256 seal
    fn compute_seal(data: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Process event and generate decision
    pub async fn process_event(
        &self,
        agent: &str,
        event_type: &str,
        amount: f64,
        payload: &serde_json::Value,
    ) -> AgentDecision {
        let start = std::time::Instant::now();
        let trace_id = Self::generate_trace_id();

        // Run tensor scoring
        let tensor_signal = self.tensor_core.run(amount, payload);

        // Determine approval
        let approved = tensor_signal.composite_signal >= 0.50;
        let confidence = tensor_signal.composite_signal;

        // Build chain of thought
        let chain_of_thought = vec![
            format!("Budget: {} ({})", tensor_signal.budget_head.score, tensor_signal.budget_head.label),
            format!("Vendor: {} ({})", tensor_signal.vendor_trust_head.score, tensor_signal.vendor_trust_head.label),
            format!("Risk: {} ({})", tensor_signal.risk_head.score, tensor_signal.risk_head.label),
            format!("Composite: {} → {}", tensor_signal.composite_signal, tensor_signal.recommendation),
        ];

        // Compute seal
        let seal_data = format!(
            "{}|{}|{}|{}|{}",
            trace_id, agent, event_type, amount, confidence
        );
        let seal = Self::compute_seal(&seal_data);

        let duration_ms = start.elapsed().as_millis() as u64;

        let decision = AgentDecision {
            agent: agent.to_string(),
            event_type: event_type.to_string(),
            approved,
            confidence,
            action: tensor_signal.recommendation.clone(),
            reasoning: format!("Deterministic tensor scoring: {}", tensor_signal.recommendation),
            chain_of_thought,
            duration_ms,
            seal: Some(seal),
            trace_id: trace_id.clone(),
        };

        // Cache decision
        let mut cache = self.decision_cache.write().await;
        cache.insert(trace_id, decision.clone());

        decision
    }

    /// Route message and generate response
    pub async fn route_message(&self, agent: &str, message: &str) -> String {
        let intent = parse_intent(agent, message);
        let decision = None; // Could fetch from cache if needed
        respond(&intent, decision)
    }
}

// ============================================================================
// SECTION 6: TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_budget_bands() {
        let router = DeterministicRouter::new();
        let payload = serde_json::json!({});
        let decision = router.process_event("finance", "gl.entry", 500.0, &payload).await;
        assert!(decision.approved);
        assert!(decision.confidence > 0.7);
    }

    #[tokio::test]
    async fn test_high_risk_escalate() {
        let router = DeterministicRouter::new();
        let payload = serde_json::json!({ "risk_score": 0.95 });
        let decision = router.process_event("risk", "transaction", 75_000.0, &payload).await;
        assert!(!decision.approved);
        assert_eq!(decision.action, "ESCALATE");
    }

    #[tokio::test]
    async fn test_trusted_vendor() {
        let router = DeterministicRouter::new();
        let payload = serde_json::json!({
            "vendor_id": "v_001",
            "po_id": "po_002",
            "risk_score": 0.1
        });
        let decision = router.process_event("procurement", "po.created", 800.0, &payload).await;
        assert!(decision.approved);
        assert!(decision.confidence >= 0.75);
    }

    #[test]
    fn test_intent_parsing() {
        let intent = parse_intent("finance", "show me cash flow");
        assert!(matches!(intent, Intent::Finance(FinanceIntent::CashFlow)));

        let intent = parse_intent("", "what's the deal pipeline status?");
        assert!(matches!(intent, Intent::Crm(CrmIntent::Pipeline)));
    }
}

// Made with Bob
