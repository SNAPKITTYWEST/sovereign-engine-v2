//! krull_lemmas_library
//!
//! Lemmas about Krull dimension of Spec(Z) and its subspaces (Tier 6).
//! [`KrullLemmasLibrary::standard`] decides the finite lemmas by computing
//! dimensions, chains and certificates for every spectrum in a family
//! (evidence grade `Computed`). `dim Z = 1` for the whole (infinite)
//! spectrum is stated and left `Open`.

#![warn(missing_docs)]

use dimension_upper_bounds::DimensionUpperBound;
use krull_certification::CertificationChecker;
use krull_dimension_definition::KrullDim;
use spectrum_definition::Spectrum;
use std::collections::BTreeMap;

pub use type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError};

/// Largest prime bound covered by the decided lemmas.
pub const DECIDED_BOUND: u64 = 200;

/// Status of a Krull dimension lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KrullLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Refuted (a decision procedure found a counterexample)
    Failed,
}

/// A Krull dimension lemma
#[derive(Clone, Debug)]
pub struct KrullLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: KrullLemmaStatus,
    /// Proof, once closed
    pub proof: Option<ProofTerm>,
    /// Dimension the lemma asserts, if one
    pub dimension_bound: Option<usize>,
    /// Counterexample, or what remains to be done
    pub note: Option<String>,
}

impl KrullLemma {
    /// Create a new open lemma
    pub fn new(name: String, statement: LeanType) -> Self {
        Self {
            name,
            statement,
            status: KrullLemmaStatus::Open,
            proof: None,
            dimension_bound: None,
            note: None,
        }
    }

    /// Set the dimension asserted
    pub fn with_dimension_bound(mut self, bound: usize) -> Self {
        self.dimension_bound = Some(bound);
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
        self.status = KrullLemmaStatus::Closed;
        Ok(())
    }

    /// Check if lemma is proven
    pub fn is_proven(&self) -> bool {
        self.status == KrullLemmaStatus::Closed
    }

    /// Evidence grade, if proven
    pub fn evidence(&self) -> Option<Evidence> {
        self.proof.as_ref().filter(|_| self.is_proven()).map(ProofTerm::evidence)
    }
}

/// Library of Krull dimension lemmas
#[derive(Clone, Debug)]
pub struct KrullLemmasLibrary {
    /// All lemmas indexed by name
    pub lemmas: BTreeMap<String, KrullLemma>,
    /// Theorems and axioms available to proofs
    pub context: TypeContext,
}

/// `{(0)} ∪ {(p) : p ≤ bound}` — Spectrum::new keeps only prime ideals.
fn spec_z_prefix(bound: u64) -> Spectrum {
    Spectrum::new((0..=bound).collect())
}

/// `{(p) : p ≤ bound}`, the closed points only.
fn closed_points(bound: u64) -> Spectrum {
    Spectrum::new((1..=bound).collect())
}

impl KrullLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// The Tier 6 lemma set, with every finite lemma decided.
    pub fn standard() -> Self {
        fn lemma(name: &str, statement: String) -> KrullLemma {
            KrullLemma::new(name.into(), LeanType::atom(statement))
        }
        let mut lib = Self::new();
        let n = DECIDED_BOUND;

        lib.add_lemma(
            lemma("dim_z_is_one", "ringKrullDim ℤ = 1".into())
                .with_dimension_bound(1)
                .with_note("unbounded spectrum: needs a Lean proof; finite prefixes decided below"),
        );

        lib.decide(
            lemma("spec_z_prefix_dimension_one", format!("∀ 2 ≤ N ≤ {n}: {{(0)}} ∪ {{(p) : p ≤ N}} has Krull dimension 1")).with_dimension_bound(1),
            "compute_prefix_dimensions",
            || {
                for bound in 2..=n {
                    let dim = KrullDim::from_spectrum(&spec_z_prefix(bound));
                    if dim != KrullDim(1) {
                        return Err(format!("N = {bound}: {dim}"));
                    }
                }
                Ok(n - 1)
            },
        );
        lib.decide(
            lemma("closed_points_dimension_zero", format!("∀ 2 ≤ N ≤ {n}: {{(p) : p ≤ N}} has Krull dimension 0")).with_dimension_bound(0),
            "compute_closed_point_dimensions",
            || {
                for bound in 2..=n {
                    let dim = KrullDim::from_spectrum(&closed_points(bound));
                    if dim != KrullDim(0) {
                        return Err(format!("N = {bound}: {dim}"));
                    }
                }
                Ok(n - 1)
            },
        );
        lib.decide(
            lemma("longest_chains_start_at_generic_point", "∀ 2 ≤ N ≤ 100: every longest prime chain of the Spec(ℤ) prefix is (0) ⊂ (p), one per prime p ≤ N".into()),
            "enumerate_longest_chains",
            || {
                for bound in 2..=100u64 {
                    let spec = spec_z_prefix(bound);
                    let chains = KrullDim::maximal_chains(&spec);
                    let primes = spec.len() - 1;
                    if chains.len() != primes || !chains.iter().all(|c| c.len() == 2 && c[0] == 0 && c[1] != 0) {
                        return Err(format!("N = {bound}: {chains:?}"));
                    }
                }
                Ok(99)
            },
        );
        lib.decide(
            lemma("certification_accepts_prefixes", "∀ 2 ≤ N ≤ 100: dimension certification passes every check for both the Spec(ℤ) prefix and its closed points".into()),
            "certify_prefixes",
            || {
                for bound in 2..=100u64 {
                    for spec in [spec_z_prefix(bound), closed_points(bound)] {
                        let result = CertificationChecker::new(spec).check_all();
                        if !result.all_passed() {
                            return Err(format!("N = {bound}: failed {:?}", result.failed_checks()));
                        }
                    }
                }
                Ok(2 * 99)
            },
        );
        lib.decide(
            lemma("bounds_are_sharp_for_prefixes", "∀ 2 ≤ N ≤ 100: the Krull PIT bound 1 holds and the bound 0 fails for the Spec(ℤ) prefix".into()).with_dimension_bound(1),
            "check_bounds",
            || {
                for bound in 2..=100u64 {
                    let dim = KrullDim::from_spectrum(&spec_z_prefix(bound));
                    if !DimensionUpperBound::krull_pit_bound(1).satisfies(dim)
                        || DimensionUpperBound::krull_pit_bound(0).satisfies(dim)
                    {
                        return Err(format!("N = {bound}: bounds not sharp for {dim}"));
                    }
                }
                Ok(99)
            },
        );
        lib
    }

    /// Register `lemma` and run its decision procedure.
    pub fn decide(
        &mut self,
        mut lemma: KrullLemma,
        procedure: &str,
        check: impl FnOnce() -> Result<u64, String>,
    ) {
        match DecisionCertificate::run(lemma.statement.clone(), procedure, check) {
            Ok(cert) => {
                lemma.proof = Some(ProofTerm::Decided(cert));
                lemma.status = KrullLemmaStatus::Closed;
                self.context.add_theorem(lemma.name.clone(), lemma.statement.clone());
            }
            Err(counterexample) => {
                lemma.status = KrullLemmaStatus::Failed;
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
        lemma.status = KrullLemmaStatus::Closed;
        self.context.add_theorem(name.to_string(), statement);
        Ok(())
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: KrullLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&KrullLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut KrullLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.count_status(KrullLemmaStatus::Closed)
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.count_status(KrullLemmaStatus::Open)
    }

    /// Count refuted lemmas
    pub fn count_failed(&self) -> usize {
        self.count_status(KrullLemmaStatus::Failed)
    }

    fn count_status(&self, status: KrullLemmaStatus) -> usize {
        self.lemmas.values().filter(|l| l.status == status).count()
    }

    /// Lemmas asserting a given dimension
    pub fn lemmas_for_dimension(&self, dim: usize) -> Vec<&KrullLemma> {
        self.lemmas.values().filter(|l| l.dimension_bound == Some(dim)).collect()
    }

    /// Smallest dimension asserted
    pub fn min_dimension(&self) -> Option<usize> {
        self.lemmas.values().filter_map(|l| l.dimension_bound).min()
    }

    /// Largest dimension asserted
    pub fn max_dimension(&self) -> Option<usize> {
        self.lemmas.values().filter_map(|l| l.dimension_bound).max()
    }
}

impl Default for KrullLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standard_library_decides_every_finite_lemma() {
        let lib = KrullLemmasLibrary::standard();
        let failed: Vec<_> = lib
            .lemmas
            .values()
            .filter(|l| l.status == KrullLemmaStatus::Failed)
            .map(|l| (l.name.clone(), l.note.clone()))
            .collect();
        assert!(failed.is_empty(), "refuted: {failed:?}");
        assert_eq!(lib.count_proven(), 5);
        assert_eq!(lib.count_open(), 1);
        assert_eq!(lib.min_dimension(), Some(0));
        assert_eq!(lib.max_dimension(), Some(1));
        assert_eq!(lib.lemmas_for_dimension(1).len(), 3);
    }

    #[test]
    fn prefixes_contain_the_generic_point() {
        assert!(spec_z_prefix(10).contains_prime(0));
        assert!(!closed_points(10).contains_prime(0));
        assert_eq!(closed_points(10).len(), 4);
    }
}
