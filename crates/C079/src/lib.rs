//! cross_layer_lemmas_library
//!
//! Statements that relate two tiers, and the bookkeeping to close them.
//!
//! [`CrossLayerLemmaLibrary::standard`] declares the cross-layer
//! correspondences the pipeline relies on (all `Open`) and imports every
//! proven lemma of the tier libraries (C073–C078) as a citable theorem named
//! `tier{N}.{name}`. The correspondences involve code from several tiers, so
//! they are decided by the Tier 9 crates (which depend on that code) through
//! [`CrossLayerLemmaLibrary::decide`]; nothing here closes them by
//! assumption.

#![warn(missing_docs)]

use gap_lemmas_library::GapLemmasLibrary;
use homological_lemmas_library::HomologyLemmasLibrary;
use krull_lemmas_library::KrullLemmasLibrary;
use memory_lemmas_library::MemoryLemmasLibrary;
use recursion_lemmas_library::RecursionLemmasLibrary;
use std::collections::BTreeMap;
use tor_resolution_lemmas_library::TorLemmasLibrary;

pub use type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError};

/// Summary of one tier lemma imported from a tier library.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TierLemmaRecord {
    /// Tier number.
    pub tier: usize,
    /// Lemma name within its library.
    pub name: String,
    /// Statement.
    pub statement: LeanType,
    /// Proof, if closed.
    pub proof: Option<ProofTerm>,
    /// True if a decision procedure refuted it.
    pub failed: bool,
    /// Counterexample or remaining work.
    pub note: Option<String>,
}

impl TierLemmaRecord {
    /// Qualified name `tier{N}.{name}`.
    pub fn qualified_name(&self) -> String {
        format!("tier{}.{}", self.tier, self.name)
    }
}

/// Collect every lemma of the six standard tier libraries.
pub fn standard_tier_lemmas() -> Vec<TierLemmaRecord> {
    let mut out = Vec::new();
    macro_rules! import {
        ($tier:expr, $lib:expr, $closed:path, $failed:path) => {
            for l in $lib.lemmas.values() {
                out.push(TierLemmaRecord {
                    tier: $tier,
                    name: l.name.clone(),
                    statement: l.statement.clone(),
                    proof: if l.status == $closed { l.proof.clone() } else { None },
                    failed: l.status == $failed,
                    note: l.note.clone(),
                });
            }
        };
    }
    use gap_lemmas_library::LemmaStatus as G;
    use homological_lemmas_library::HomologyLemmaStatus as H;
    use krull_lemmas_library::KrullLemmaStatus as K;
    use memory_lemmas_library::MemoryLemmaStatus as M;
    use recursion_lemmas_library::RecursionLemmaStatus as R;
    use tor_resolution_lemmas_library::TorLemmaStatus as T;
    import!(1, MemoryLemmasLibrary::standard(), M::Closed, M::Failed);
    import!(2, GapLemmasLibrary::standard(), G::Closed, G::Failed);
    import!(3, RecursionLemmasLibrary::standard(), R::Closed, R::Failed);
    import!(4, HomologyLemmasLibrary::standard(), H::Closed, H::Failed);
    import!(5, TorLemmasLibrary::standard(), T::Closed, T::Failed);
    import!(6, KrullLemmasLibrary::standard(), K::Closed, K::Failed);
    out
}

/// A cross-layer relationship between two tiers
#[derive(Clone, Debug)]
pub struct CrossLayerLemma {
    /// Lemma identifier
    pub id: String,
    /// Source tier (0-9)
    pub source_tier: usize,
    /// Target tier
    pub target_tier: usize,
    /// Statement of the lemma
    pub statement: LeanType,
    /// Proof term (if proven)
    pub proof: Option<ProofTerm>,
    /// Qualified tier lemmas (`tier{N}.{name}`) the statement builds on
    pub premises: Vec<String>,
    /// Counterexample, or what remains to be done
    pub note: Option<String>,
}

impl CrossLayerLemma {
    /// Create a cross-layer lemma
    pub fn new(id: String, source_tier: usize, target_tier: usize, statement: LeanType) -> Self {
        Self {
            id,
            source_tier,
            target_tier,
            statement,
            proof: None,
            premises: Vec::new(),
            note: None,
        }
    }

    /// Record the tier lemmas this statement builds on
    pub fn with_premises(mut self, premises: &[&str]) -> Self {
        self.premises = premises.iter().map(|p| p.to_string()).collect();
        self
    }

    /// Close with a self-contained proof (checked in an empty context).
    pub fn prove(&mut self, proof: ProofTerm) -> Result<(), TypeError> {
        TypeContext::new().check(&proof, &self.statement)?;
        self.proof = Some(proof);
        Ok(())
    }

    /// Is this lemma proven?
    pub fn is_proven(&self) -> bool {
        self.proof.is_some()
    }

    /// Evidence grade, if proven
    pub fn evidence(&self) -> Option<Evidence> {
        self.proof.as_ref().map(ProofTerm::evidence)
    }

    /// Get direction name
    pub fn direction_name(&self) -> String {
        format!("Tier {} -> Tier {}", self.source_tier, self.target_tier)
    }
}

/// Cross-layer lemmas plus the imported tier lemmas.
#[derive(Clone, Debug)]
pub struct CrossLayerLemmaLibrary {
    /// Cross-layer lemmas by id
    pub lemmas: BTreeMap<String, CrossLayerLemma>,
    /// Imported tier lemmas by qualified name
    pub tier_lemmas: BTreeMap<String, TierLemmaRecord>,
    /// Proven tier lemmas and closed cross-layer lemmas, citable by name
    pub context: TypeContext,
}

/// Ids of the standard cross-layer lemmas, with the Tier 9 crate that
/// decides each.
pub const STANDARD_CORRESPONDENCES: [(&str, &str); 8] = [
    ("arena_preserves_tensors", "cross_layer_invariants"),
    ("candidate_gaps_match_engine", "prime_gap_correspondence"),
    ("gap_pairs_become_consonant_nodes", "prime_gap_correspondence"),
    ("dissonance_equals_path_components", "tensor_homology_correspondence"),
    ("tor_dimension_bounded_by_krull", "tor_spectrum_correspondence"),
    ("runtime_invariants_match_static", "cross_layer_invariants"),
    ("certificates_discharge_obligations", "rust_lean_correspondence"),
    ("trace_replay_matches_execution", "end_to_end_trace_verification"),
];

impl CrossLayerLemmaLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            tier_lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// The standard cross-layer statements (all open) with the six tier
    /// libraries imported.
    pub fn standard() -> Self {
        fn lemma(id: &str, from: usize, to: usize, statement: &str) -> CrossLayerLemma {
            CrossLayerLemma::new(id.into(), from, to, LeanType::atom(statement))
        }
        let mut lib = Self::new();
        lib.import_tier_lemmas(standard_tier_lemmas());
        lib.add_lemma(
            lemma("arena_preserves_tensors", 0, 1, "∀ tensors in the test family, writing to an arena DATA region and reading back preserves every node bit-for-bit and every tensor invariant")
                .with_premises(&["tier1.layout_partitions_arena", "tier1.arena_nil_initialized"]),
        );
        lib.add_lemma(
            lemma("candidate_gaps_match_engine", 0, 2, "the gaps between consecutive CANDIDATE_PRIMES equal the prime engine's gaps for primes ≤ 13")
                .with_premises(&["tier2.enumeration_complete_below_limit"]),
        );
        lib.add_lemma(
            lemma("gap_pairs_become_consonant_nodes", 2, 0, "every consecutive prime pair p < q ≤ 13 maps to candidate nodes with no dissonance violation")
                .with_premises(&["tier2.gaps_even_after_two"]),
        );
        lib.add_lemma(
            lemma("dissonance_equals_path_components", 0, 4, "for every gap tensor in the test family, rank H₀ of its consonance path complex = 1 + the number of dissonance violations")
                .with_premises(&["tier4.euler_characteristic_two_term"]),
        );
        lib.add_lemma(
            lemma("tor_dimension_bounded_by_krull", 5, 6, "∀ 0 ≤ m, n ≤ 24: the highest non-vanishing Tor degree of (ℤ/m, ℤ/n) is at most dim of the Spec(ℤ) prefix")
                .with_premises(&["tier5.higher_tor_vanishes", "tier6.spec_z_prefix_dimension_one"]),
        );
        lib.add_lemma(
            lemma("runtime_invariants_match_static", 8, 0, "the runtime invariant checker reports exactly the violations the static tensor invariants report, on the test family"),
        );
        lib.add_lemma(
            lemma("certificates_discharge_obligations", 8, 7, "runtime certificates close exactly the obligations whose runtime checks passed, and no other obligation"),
        );
        lib.add_lemma(
            lemma("trace_replay_matches_execution", 8, 9, "replaying a recorded runtime trace reproduces every recorded state, and any tampering is detected"),
        );
        lib
    }

    /// Import tier lemmas; proven ones become theorems `tier{N}.{name}`.
    pub fn import_tier_lemmas(&mut self, records: Vec<TierLemmaRecord>) {
        for record in records {
            if record.proof.is_some() {
                self.context.add_theorem(record.qualified_name(), record.statement.clone());
            }
            self.tier_lemmas.insert(record.qualified_name(), record);
        }
    }

    /// Premises of `id` that are not proven tier lemmas.
    pub fn unmet_premises(&self, id: &str) -> Vec<String> {
        self.lemmas.get(id).map_or_else(Vec::new, |l| {
            l.premises
                .iter()
                .filter(|p| self.tier_lemmas.get(*p).map_or(true, |r| r.proof.is_none()))
                .cloned()
                .collect()
        })
    }

    /// Run a decision procedure for cross-layer lemma `id`. Refuses if a
    /// premise is unproven; on failure the counterexample is recorded.
    pub fn decide(
        &mut self,
        id: &str,
        procedure: &str,
        check: impl FnOnce() -> Result<u64, String>,
    ) -> Result<(), String> {
        let unmet = self.unmet_premises(id);
        let lemma = self.lemmas.get_mut(id).ok_or_else(|| format!("unknown lemma `{id}`"))?;
        if !unmet.is_empty() {
            let msg = format!("unproven premises: {}", unmet.join(", "));
            lemma.note = Some(msg.clone());
            return Err(msg);
        }
        match DecisionCertificate::run(lemma.statement.clone(), procedure, check) {
            Ok(cert) => {
                lemma.proof = Some(ProofTerm::Decided(cert));
                lemma.note = None;
                let statement = lemma.statement.clone();
                self.context.add_theorem(id.to_string(), statement);
                Ok(())
            }
            Err(counterexample) => {
                lemma.proof = None;
                lemma.note = Some(counterexample.clone());
                Err(counterexample)
            }
        }
    }

    /// Add a lemma to the library
    pub fn add_lemma(&mut self, lemma: CrossLayerLemma) {
        self.lemmas.insert(lemma.id.clone(), lemma);
    }

    /// Get a lemma by ID
    pub fn get_lemma(&self, id: &str) -> Option<&CrossLayerLemma> {
        self.lemmas.get(id)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.lemmas.values().filter(|l| l.is_proven()).count()
    }

    /// Get all lemmas for a given tier transition
    pub fn lemmas_for_transition(&self, from: usize, to: usize) -> Vec<&CrossLayerLemma> {
        self.lemmas
            .values()
            .filter(|l| l.source_tier == from && l.target_tier == to)
            .collect()
    }

    /// Check if two tiers are related (direct lemma exists)
    pub fn are_tiers_related(&self, tier1: usize, tier2: usize) -> bool {
        !self.lemmas_for_transition(tier1, tier2).is_empty()
            || !self.lemmas_for_transition(tier2, tier1).is_empty()
    }

    /// Fraction of cross-layer lemmas proven (1.0 when empty)
    pub fn proof_coverage(&self) -> f64 {
        if self.lemmas.is_empty() {
            return 1.0;
        }
        self.count_proven() as f64 / self.lemmas.len() as f64
    }
}

impl Default for CrossLayerLemmaLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standard_library_imports_tiers_and_declares_open_correspondences() {
        let lib = CrossLayerLemmaLibrary::standard();
        assert_eq!(lib.lemmas.len(), STANDARD_CORRESPONDENCES.len());
        assert_eq!(lib.count_proven(), 0);
        assert!(lib.tier_lemmas.values().all(|r| !r.failed), "a tier lemma was refuted");
        assert_eq!(lib.tier_lemmas.values().filter(|r| r.proof.is_some()).count(), 6 + 9 + 5 + 6 + 7 + 5);
        for (id, _) in STANDARD_CORRESPONDENCES {
            assert!(lib.unmet_premises(id).is_empty(), "{id} has unmet premises");
        }
        assert!(lib.context.lookup_theorem("tier2.gaps_even_after_two").is_some());
        assert!(lib.context.lookup_theorem("tier2.primality_correct").is_none());
    }

    #[test]
    fn deciding_cross_layer_lemmas() {
        let mut lib = CrossLayerLemmaLibrary::standard();
        lib.decide("candidate_gaps_match_engine", "trivial_check", || Ok(1)).unwrap();
        assert!(lib.get_lemma("candidate_gaps_match_engine").unwrap().is_proven());
        assert_eq!(lib.count_proven(), 1);
        let err = lib.decide("trace_replay_matches_execution", "broken", || Err("state 3 differs".into()));
        assert!(err.unwrap_err().contains("state 3 differs"));
        assert!(!lib.get_lemma("trace_replay_matches_execution").unwrap().is_proven());
        assert!(lib.decide("missing", "x", || Ok(1)).is_err());
    }

    #[test]
    fn unmet_premises_block_decisions() {
        let mut lib = CrossLayerLemmaLibrary::new();
        lib.add_lemma(
            CrossLayerLemma::new("x".into(), 0, 1, LeanType::atom("X")).with_premises(&["tier9.nothing"]),
        );
        assert_eq!(lib.unmet_premises("x"), vec!["tier9.nothing".to_string()]);
        assert!(lib.decide("x", "p", || Ok(1)).is_err());
        assert!(!lib.get_lemma("x").unwrap().is_proven());
    }

    #[test]
    fn prove_is_checked() {
        let mut lemma = CrossLayerLemma::new("t".into(), 0, 1, LeanType::prop());
        assert!(lemma.prove(ProofTerm::Trivial).is_err());
        assert!(!lemma.is_proven());
        let mut truth = CrossLayerLemma::new("t".into(), 0, 1, LeanType::truth());
        assert!(truth.prove(ProofTerm::Trivial).is_ok());
    }

    #[test]
    fn transitions() {
        let lib = CrossLayerLemmaLibrary::standard();
        assert_eq!(lib.lemmas_for_transition(0, 2).len(), 1);
        assert!(lib.are_tiers_related(6, 5));
        assert!(!lib.are_tiers_related(3, 7));
        assert_eq!(lib.proof_coverage(), 0.0);
    }
}
