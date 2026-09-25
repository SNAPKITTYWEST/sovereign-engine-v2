//! gap_lemmas_library
//!
//! Lemmas about primes and prime gaps that the Tier 2 engine relies on.
//!
//! [`GapLemmasLibrary::standard`] registers each lemma with a precise
//! statement. Lemmas over a finite domain are *decided*: a decision procedure
//! runs the real Tier 2 code over every case and the lemma is closed with a
//! [`DecisionCertificate`] (evidence grade `Computed`), or marked `Failed`
//! with the counterexample. Unbounded statements stay `Open` — they need a
//! Lean proof, which this crate does not claim.

#![warn(missing_docs)]

use gap_candidate_set::GapCandidateSet;
use gap_verification::verify_gaps_around_primes;
use prime_enumeration::{prime_count, primes_up_to};
use prime_gap_relationship::prime_gap_pairs;
use prime_predicate::is_prime;
use std::collections::BTreeMap;

pub use type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError};

/// Upper bound of the decided prime lemmas.
pub const DECIDED_LIMIT: u64 = 10_000;

/// Status of a lemma proof
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Refuted (a decision procedure found a counterexample)
    Failed,
}

/// A gap lemma statement and its proof
#[derive(Clone, Debug)]
pub struct GapLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: LemmaStatus,
    /// Proof, once closed
    pub proof: Option<ProofTerm>,
    /// Gap size the lemma is about, if any
    pub gap_size: Option<usize>,
    /// Counterexample, or what remains to be done
    pub note: Option<String>,
}

impl GapLemma {
    /// Create a new open lemma
    pub fn new(name: String, statement: LeanType) -> Self {
        Self {
            name,
            statement,
            status: LemmaStatus::Open,
            proof: None,
            gap_size: None,
            note: None,
        }
    }

    /// Set the gap size this lemma applies to
    pub fn with_gap_size(mut self, size: usize) -> Self {
        self.gap_size = Some(size);
        self
    }

    /// Attach a note
    pub fn with_note(mut self, note: impl Into<String>) -> Self {
        self.note = Some(note.into());
        self
    }

    /// Close with a self-contained proof (checked in an empty context).
    pub fn prove(&mut self, proof: ProofTerm) -> Result<(), TypeError> {
        TypeContext::new().check(&proof, &self.statement)?;
        self.proof = Some(proof);
        self.status = LemmaStatus::Closed;
        Ok(())
    }

    /// Check if lemma is proven
    pub fn is_proven(&self) -> bool {
        self.status == LemmaStatus::Closed
    }

    /// Evidence grade, if proven
    pub fn evidence(&self) -> Option<Evidence> {
        self.proof.as_ref().filter(|_| self.is_proven()).map(ProofTerm::evidence)
    }
}

/// Library of gap lemmas
#[derive(Clone, Debug)]
pub struct GapLemmasLibrary {
    /// All lemmas indexed by name
    pub lemmas: BTreeMap<String, GapLemma>,
    /// Theorems and axioms available to proofs
    pub context: TypeContext,
}

fn trial_division(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    let mut d = 2u64;
    while d * d <= n {
        if n % d == 0 {
            return false;
        }
        d += 1;
    }
    true
}

impl GapLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// The Tier 2 lemma set, with every finite lemma decided.
    pub fn standard() -> Self {
        fn atom(s: impl Into<String>) -> LeanType {
            LeanType::atom(s)
        }
        let mut lib = Self::new();
        let n = DECIDED_LIMIT;

        lib.add_lemma(GapLemma::new("primality_correct".into(), atom("∀ n : ℕ, is_prime n ↔ Nat.Prime n")).with_note(
            "unbounded: needs a Lean proof; decided below the limit by primality_correct_below_limit",
        ));
        lib.add_lemma(GapLemma::new(
            "infinitely_many_primes".into(),
            atom("∀ n : ℕ, ∃ p ≥ n, Nat.Prime p"),
        )
        .with_note("unbounded (Euclid); Mathlib's Nat.exists_infinite_primes is not checked here"));

        lib.decide(
            GapLemma::new(
                "primality_correct_below_limit".into(),
                atom(&format!("∀ n < {n}, is_prime n ↔ trial_division n")),
            ),
            "compare_with_trial_division",
            || {
                for k in 0..n {
                    if is_prime(k) != trial_division(k) {
                        return Err(format!("disagreement at n = {k}"));
                    }
                }
                Ok(n)
            },
        );
        lib.decide(
            GapLemma::new(
                "enumeration_complete_below_limit".into(),
                atom(&format!("primes_up_to {n} = [p ≤ {n} | Nat.Prime p] (increasing)")),
            ),
            "compare_sieve_with_trial_division",
            || {
                let expected: Vec<u64> = (0..=n).filter(|&k| trial_division(k)).collect();
                if primes_up_to(n) != expected {
                    return Err("sieve output differs from trial division".into());
                }
                Ok(n + 1)
            },
        );
        lib.decide(
            GapLemma::new(
                "prime_count_matches_enumeration".into(),
                atom("∀ L ≤ 2000, prime_count L = length (primes_up_to L)"),
            ),
            "compare_counts",
            || {
                for limit in 0..=2000u64 {
                    if prime_count(limit) != primes_up_to(limit).len() {
                        return Err(format!("mismatch at L = {limit}"));
                    }
                }
                Ok(2001)
            },
        );
        lib.decide(
            GapLemma::new(
                "gaps_even_after_two".into(),
                atom(&format!("∀ consecutive primes 2 < p < q ≤ {n}, 2 ∣ q − p")),
            ),
            "scan_consecutive_primes",
            || {
                let primes = primes_up_to(n);
                for w in primes.windows(2).filter(|w| w[0] > 2) {
                    if (w[1] - w[0]) % 2 != 0 {
                        return Err(format!("odd gap {} → {}", w[0], w[1]));
                    }
                }
                Ok(primes.len() as u64)
            },
        );
        lib.decide(
            GapLemma::new(
                "maximal_gap_below_limit".into(),
                atom(&format!("the largest gap between consecutive primes ≤ {n} is 36, first at 9551 → 9587")),
            )
            .with_gap_size(36),
            "scan_for_maximal_gap",
            || {
                let primes = primes_up_to(n);
                let (gap, at) = primes
                    .windows(2)
                    .map(|w| (w[1] - w[0], w[0]))
                    .fold((0, 0), |best, (g, p)| if g > best.0 { (g, p) } else { best });
                if (gap, at) != (36, 9551) {
                    return Err(format!("largest gap is {gap}, first at {at}"));
                }
                Ok(primes.len() as u64)
            },
        );
        lib.decide(
            GapLemma::new(
                "candidate_set_matches_enumeration".into(),
                atom(&format!("(GapCandidateSet.from_limit {n}).gaps = consecutive differences of primes_up_to {n}")),
            ),
            "compare_gap_lists",
            || {
                let expected: Vec<u64> = primes_up_to(n).windows(2).map(|w| w[1] - w[0]).collect();
                let got = GapCandidateSet::from_limit(n).gaps();
                if got != expected {
                    return Err(format!("{} gaps vs {} expected", got.len(), expected.len()));
                }
                Ok(expected.len() as u64)
            },
        );
        lib.decide(
            GapLemma::new(
                "gap_verification_accepts_true_gaps".into(),
                atom(&format!("verify_gaps_around_primes accepts every consecutive prime pair ≤ {n}")),
            ),
            "verify_real_pairs",
            || {
                let candidates: Vec<(u64, u64, u64)> = primes_up_to(n)
                    .windows(2)
                    .map(|w| (w[0], w[1], w[1] - w[0]))
                    .collect();
                let result = verify_gaps_around_primes(&candidates);
                if !result.all_passed() {
                    return Err(format!("{} consecutive pairs rejected", result.failed));
                }
                Ok(candidates.len() as u64)
            },
        );
        lib.decide(
            GapLemma::new(
                "first_occurrence_matches_scan".into(),
                atom(&format!("PrimeGapPair.is_first_occurrence agrees with a left-to-right scan for all pairs ≤ {n}")),
            ),
            "compare_with_scan",
            || {
                let pairs = prime_gap_pairs(n);
                let mut seen = std::collections::BTreeSet::new();
                for pair in &pairs {
                    let first = seen.insert(pair.gap);
                    if pair.is_first_occurrence(&pairs) != first {
                        return Err(format!("disagreement at prime {}", pair.prime));
                    }
                }
                Ok(pairs.len() as u64)
            },
        );
        lib.decide(
            GapLemma::new(
                "bertrand_below_5000".into(),
                atom("∀ 1 ≤ n < 5000, ∃ p, Nat.Prime p ∧ n < p ≤ 2n"),
            ),
            "search_prime_in_interval",
            || {
                let primes = primes_up_to(10_000);
                for k in 1..5000u64 {
                    let i = primes.partition_point(|&p| p <= k);
                    if primes.get(i).map_or(true, |&p| p > 2 * k) {
                        return Err(format!("no prime in ({k}, {}]", 2 * k));
                    }
                }
                Ok(4999)
            },
        );
        lib
    }

    /// Register `lemma` and run its decision procedure: closed with a
    /// certificate on success, marked failed with the counterexample
    /// otherwise.
    pub fn decide(
        &mut self,
        mut lemma: GapLemma,
        procedure: &str,
        check: impl FnOnce() -> Result<u64, String>,
    ) {
        match DecisionCertificate::run(lemma.statement.clone(), procedure, check) {
            Ok(cert) => {
                lemma.proof = Some(ProofTerm::Decided(cert));
                lemma.status = LemmaStatus::Closed;
                self.context.add_theorem(lemma.name.clone(), lemma.statement.clone());
            }
            Err(counterexample) => {
                lemma.status = LemmaStatus::Failed;
                lemma.note = Some(counterexample);
            }
        }
        self.add_lemma(lemma);
    }

    /// Close lemma `name` with `proof`, checked in this library's context.
    pub fn prove_lemma(&mut self, name: &str, proof: ProofTerm) -> Result<(), TypeError> {
        let lemma = self
            .lemmas
            .get(name)
            .ok_or_else(|| TypeError::UnknownName(name.to_string()))?;
        self.context.check(&proof, &lemma.statement)?;
        let statement = lemma.statement.clone();
        let lemma = self.lemmas.get_mut(name).expect("checked above");
        lemma.proof = Some(proof);
        lemma.status = LemmaStatus::Closed;
        self.context.add_theorem(name.to_string(), statement);
        Ok(())
    }

    /// Add a lemma to the library
    pub fn add_lemma(&mut self, lemma: GapLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&GapLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut GapLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.count_status(LemmaStatus::Closed)
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.count_status(LemmaStatus::Open)
    }

    /// Count refuted lemmas
    pub fn count_failed(&self) -> usize {
        self.count_status(LemmaStatus::Failed)
    }

    fn count_status(&self, status: LemmaStatus) -> usize {
        self.lemmas.values().filter(|l| l.status == status).count()
    }

    /// Get all lemmas for a specific gap size
    pub fn lemmas_for_gap(&self, size: usize) -> Vec<&GapLemma> {
        self.lemmas
            .values()
            .filter(|l| l.gap_size == Some(size))
            .collect()
    }
}

impl Default for GapLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standard_library_decides_every_bounded_lemma() {
        let lib = GapLemmasLibrary::standard();
        let failed: Vec<_> = lib
            .lemmas
            .values()
            .filter(|l| l.status == LemmaStatus::Failed)
            .map(|l| (l.name.clone(), l.note.clone()))
            .collect();
        assert!(failed.is_empty(), "refuted: {failed:?}");
        assert_eq!(lib.count_proven(), 9);
        assert_eq!(lib.count_open(), 2);
        assert!(lib
            .lemmas
            .values()
            .filter(|l| l.is_proven())
            .all(|l| l.evidence() == Some(Evidence::Computed)));
        assert_eq!(lib.lemmas_for_gap(36).len(), 1);
    }

    #[test]
    fn false_bounded_claims_are_refuted() {
        let mut lib = GapLemmasLibrary::new();
        lib.decide(
            GapLemma::new("all_odd_numbers_prime".into(), LeanType::atom("∀ odd n < 20, Nat.Prime n")),
            "scan",
            || match (3..20u64).step_by(2).find(|&k| !trial_division(k)) {
                Some(k) => Err(format!("{k} is not prime")),
                None => Ok(9),
            },
        );
        let lemma = lib.get_lemma("all_odd_numbers_prime").unwrap();
        assert_eq!(lemma.status, LemmaStatus::Failed);
        assert_eq!(lemma.note.as_deref(), Some("scan: 9 is not prime"));
    }

    #[test]
    fn open_lemmas_need_real_proofs() {
        let mut lib = GapLemmasLibrary::standard();
        assert!(lib.prove_lemma("primality_correct", ProofTerm::Trivial).is_err());
        assert!(lib.prove_lemma("missing", ProofTerm::Trivial).is_err());
        let mut lemma = GapLemma::new("t".into(), LeanType::truth());
        assert!(lemma.prove(ProofTerm::Trivial).is_ok());
        assert_eq!(lemma.evidence(), Some(Evidence::Constructive));
    }

    #[test]
    fn proven_lemmas_are_citable() {
        let mut lib = GapLemmasLibrary::standard();
        let stmt = lib.get_lemma("gaps_even_after_two").unwrap().statement.clone();
        let goal = LeanType::atom("no odd gaps above two");
        lib.context.add_axiom("rephrase".into(), LeanType::arrow(stmt, goal.clone()));
        lib.add_lemma(GapLemma::new("rephrased".into(), goal));
        let proof = ProofTerm::app(ProofTerm::axiom("rephrase"), ProofTerm::reference("gaps_even_after_two"));
        lib.prove_lemma("rephrased", proof).unwrap();
        assert_eq!(lib.get_lemma("rephrased").unwrap().evidence(), Some(Evidence::Assumed));
    }
}
