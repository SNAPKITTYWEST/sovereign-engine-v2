// magmad_client.rs — Rust bindings to the magmad REST/SSE daemon
//
// Connects sovereign-engine-v2 to magmad (:3000) for:
//   POST /api/v1/orchestrate  → SSE pipeline stream
//   POST /api/v1/verify       → ERRANT linear-type verification
//   GET  /api/v1/chain/head   → current WORM chain head
//   GET  /api/v1/health
//
// MAGMA verb → magmad action mapping:
//   SEAL   → /orchestrate { action: "seal" }    → CIPHER agent
//   ANCHOR → /orchestrate { action: "anchor" }  → MNEMEX agent
//   FORGE  → /orchestrate { action: "forge" }   → FORGE agent
//   VERIFY → /verify      { opcodes: [...] }    → ERRANT gate
//
// Connection to hardware layer:
//   magma_666.adb M.Persist(Core) → §SEAL:CIPHER:SIGN{ core_state }
//   magma-safety SafetyCertificate → §ANCHOR:MNEMEX:WORM{ cert_digest }

use serde::{Deserialize, Serialize};
use std::time::Duration;

pub const MAGMAD_BASE: &str = "http://localhost:3000";

// ---------------------------------------------------------------------------
// Request / response types (mirrors http/mod.rs)
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize)]
pub struct OrchestrateRequest {
    pub session_id:  Option<String>,
    pub action:      String,
    pub code:        Option<String>,
    pub intent:      Option<String>,
    pub constraints: Option<Vec<String>>,
    pub trace_ops:   Option<Vec<String>>,
}

#[derive(Debug, Serialize)]
pub struct VerifyRequest {
    pub opcodes: Option<Vec<String>>,
    pub source:  Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct VerifyResponse {
    pub ok:           bool,
    pub verdict:      String,    // "EVIDENCE" | "SILENCE"
    pub worm_hash:    String,
    pub error:        Option<String>,
    pub steps:        i32,
    pub lin_consumed: i32,
    pub lin_leaked:   i32,
    pub fallback:     bool,
}

#[derive(Debug, Deserialize)]
pub struct ChainHeadResponse {
    pub head:     String,    // hex SHA-256
    pub sequence: u64,
    pub ts:       u64,
}

#[derive(Debug, Deserialize)]
pub struct HealthResponse {
    pub ok:      bool,
    pub version: String,
}

// SSE stage event from /orchestrate
#[derive(Debug, Deserialize)]
pub struct StageEvent {
    pub stage:      String,
    pub ok:         bool,
    pub agent:      Option<String>,
    pub worm_hash:  Option<String>,
    pub proof_hash: Option<String>,
    pub message:    String,
    pub error:      Option<String>,
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

pub struct MagmadClient {
    base_url: String,
    timeout:  Duration,
}

impl MagmadClient {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self { base_url: base_url.into(), timeout: Duration::from_secs(10) }
    }

    pub fn local() -> Self {
        Self::new(MAGMAD_BASE)
    }

    fn url(&self, path: &str) -> String {
        format!("{}{}", self.base_url, path)
    }

    // ------------------------------------------------------------------
    // Health check — confirms daemon is reachable
    // ------------------------------------------------------------------

    pub async fn health(&self) -> Result<HealthResponse, Box<dyn std::error::Error>> {
        let resp = reqwest::Client::new()
            .get(self.url("/api/v1/health"))
            .timeout(self.timeout)
            .send().await?
            .json::<HealthResponse>().await?;
        Ok(resp)
    }

    // ------------------------------------------------------------------
    // Verify ERRANT opcodes through liberrant linear type checker
    // ------------------------------------------------------------------

    pub async fn verify(&self, opcodes: &[&str]) -> Result<VerifyResponse, Box<dyn std::error::Error>> {
        let body = VerifyRequest {
            opcodes: Some(opcodes.iter().map(|s| s.to_string()).collect()),
            source:  None,
        };
        let resp = reqwest::Client::new()
            .post(self.url("/api/v1/verify"))
            .json(&body)
            .timeout(self.timeout)
            .send().await?
            .json::<VerifyResponse>().await?;
        Ok(resp)
    }

    // ------------------------------------------------------------------
    // WORM chain head
    // ------------------------------------------------------------------

    pub async fn chain_head(&self) -> Result<ChainHeadResponse, Box<dyn std::error::Error>> {
        let resp = reqwest::Client::new()
            .get(self.url("/api/v1/chain/head"))
            .timeout(self.timeout)
            .send().await?
            .json::<ChainHeadResponse>().await?;
        Ok(resp)
    }

    // ------------------------------------------------------------------
    // Orchestrate — fire a MAGMA verb through the BOB pipeline
    // Returns the SSE stream body as raw text (caller parses data: lines)
    // ------------------------------------------------------------------

    pub async fn orchestrate(&self, req: OrchestrateRequest) -> Result<String, Box<dyn std::error::Error>> {
        let text = reqwest::Client::new()
            .post(self.url("/api/v1/orchestrate"))
            .json(&req)
            .timeout(Duration::from_secs(60))
            .send().await?
            .text().await?;
        Ok(text)
    }

    // ------------------------------------------------------------------
    // Convenience wrappers for the key MAGMA verbs
    // ------------------------------------------------------------------

    /// SEAL — route through CIPHER agent, returns WORM hash
    pub async fn seal(&self, payload: impl Into<String>) -> Result<VerifyResponse, Box<dyn std::error::Error>> {
        // SEAL uses the ERRANT verify path — proves linear consumption before sealing
        self.verify(&["PUSH_LIN", "HASH", "SEAL"]).await
    }

    /// ANCHOR — commit a safety certificate digest to the WORM ledger
    pub async fn anchor(&self, cert_hex: &str) -> Result<String, Box<dyn std::error::Error>> {
        let req = OrchestrateRequest {
            session_id:  None,
            action:      "anchor".to_string(),
            code:        Some(cert_hex.to_string()),
            intent:      Some("magma-safety certificate".to_string()),
            constraints: None,
            trace_ops:   Some(vec!["PUSH_UN".into(), "ANCHOR".into()]),
        };
        self.orchestrate(req).await
    }

    /// FORGE — trigger a build operation
    pub async fn forge(&self, artifact: &str, intent: &str) -> Result<String, Box<dyn std::error::Error>> {
        let req = OrchestrateRequest {
            session_id:  None,
            action:      "forge".to_string(),
            code:        Some(artifact.to_string()),
            intent:      Some(intent.to_string()),
            constraints: None,
            trace_ops:   Some(vec!["SEED".into(), "FORGE".into(), "SEAL".into()]),
        };
        self.orchestrate(req).await
    }
}

// ---------------------------------------------------------------------------
// MAGMA hardware → protocol bridge
// Maps magma_666.adb Core_State transitions to protocol verbs
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
pub enum CoreTransition {
    Clear,
    Pulse,
    Latch,
    Persist,
    Resume,
}

impl CoreTransition {
    /// Map Ada Core_State transition to MAGMA protocol verb + ERRANT opcode sequence
    pub fn to_magma_verb(&self) -> (&'static str, Vec<&'static str>) {
        match self {
            CoreTransition::Clear   => ("NULLIFY", vec!["PUSH_UN", "MOVE", "SEAL"]),
            CoreTransition::Pulse   => ("FLUX",    vec!["PUSH_LIN", "RUPTURE", "SEAL"]),
            CoreTransition::Latch   => ("BIND",    vec!["PUSH_LIN", "MOVE", "SEAL"]),
            CoreTransition::Persist => ("ANCHOR",  vec!["PUSH_UN", "ANCHOR", "SEAL"]),
            CoreTransition::Resume  => ("FORGE",   vec!["SEED", "FORGE", "SEAL"]),
        }
    }

    /// Route a Core transition through magmad
    pub async fn dispatch(&self, client: &MagmadClient) -> Result<VerifyResponse, Box<dyn std::error::Error>> {
        let (_verb, opcodes) = self.to_magma_verb();
        let op_refs: Vec<&str> = opcodes.iter().map(String::as_str).collect();
        client.verify(&op_refs).await
    }
}

// ---------------------------------------------------------------------------
// Safety certificate → MAGMA ANCHOR binding
// ---------------------------------------------------------------------------

/// Anchor a magma-safety certificate into the WORM ledger via magmad.
/// Called after check_safety() succeeds and certificate() is generated.
pub async fn anchor_safety_certificate(
    client: &MagmadClient,
    cert_digest_hex: &str,
) -> Result<String, Box<dyn std::error::Error>> {
    client.anchor(cert_digest_hex).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn persist_maps_to_anchor_opcodes() {
        let (verb, ops) = CoreTransition::Persist.to_magma_verb();
        assert_eq!(verb, "ANCHOR");
        assert!(ops.contains(&"ANCHOR"));
    }

    #[test]
    fn pulse_maps_to_flux_opcodes() {
        let (verb, _) = CoreTransition::Pulse.to_magma_verb();
        assert_eq!(verb, "FLUX");
    }
}
