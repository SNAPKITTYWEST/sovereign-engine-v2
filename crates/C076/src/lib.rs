//! homological_lemmas_library
//!
//! Lemmas about chain complexes, homology and resolution certification
//! (Tier 4). [`HomologyLemmasLibrary::standard`] decides the finite lemmas
//! by running the Tier 4 code over every complex in an explicit family
//! (evidence grade `Computed`). Correctness of the Smith-normal-form homology
//! algorithm for *all* complexes is stated and left `Open`.

#![warn(missing_docs)]

use differential_operator::{ChainComplexShape, DifferentialOperator};
use differential_squared_zero::SquaredZeroVerifier;
use exactness_predicate::ExactnessPredicateChecker;
use homology_computation::HomologyComputer;
use resolution_certification::{
    ProjectiveModule, ProjectiveModuleHomomorphism, ProjectiveResolution, ResolutionCertifier,
};
use std::collections::BTreeMap;

pub use type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError};

/// Status of a homology lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HomologyLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Refuted (a decision procedure found a counterexample)
    Failed,
}

/// A homology or chain complex lemma
#[derive(Clone, Debug)]
pub struct HomologyLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: HomologyLemmaStatus,
    /// Proof, once closed
    pub proof: Option<ProofTerm>,
    /// Kind: differential, homology, exactness or resolution
    pub lemma_type: String,
    /// Counterexample, or what remains to be done
    pub note: Option<String>,
}

impl HomologyLemma {
    /// Create a new open lemma
    pub fn new(name: String, statement: LeanType, lemma_type: String) -> Self {
        Self {
            name,
            statement,
            status: HomologyLemmaStatus::Open,
            proof: None,
            lemma_type,
            note: None,
        }
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
        self.status = HomologyLemmaStatus::Closed;
        Ok(())
    }

    /// Check if lemma is proven
    pub fn is_proven(&self) -> bool {
        self.status == HomologyLemmaStatus::Closed
    }

    /// Evidence grade, if proven
    pub fn evidence(&self) -> Option<Evidence> {
        self.proof.as_ref().filter(|_| self.is_proven()).map(ProofTerm::evidence)
    }
}

/// Library of homology lemmas
#[derive(Clone, Debug)]
pub struct HomologyLemmasLibrary {
    /// All lemmas indexed by name
    pub lemmas: BTreeMap<String, HomologyLemma>,
    /// Theorems and axioms available to proofs
    pub context: TypeContext,
}

/// `0 → Z^a --m--> Z^b → 0` with `C_1 = Z^a`, `C_0 = Z^b` (`m` is `b × a`).
fn two_term(m: &[Vec<i64>], a: usize, b: usize) -> DifferentialOperator {
    let mut diff = DifferentialOperator::new(ChainComplexShape::from_ranks(vec![(0, b), (1, a)]));
    for j in 0..a {
        diff.set_generator_image(1, j, 0, (0..b).map(|i| (i, m[i][j])).collect());
    }
    diff
}

/// Every `b × a` matrix with entries in `lo..=hi`.
fn all_matrices(a: usize, b: usize, lo: i64, hi: i64) -> Vec<Vec<Vec<i64>>> {
    let cells = a * b;
    let base = (hi - lo + 1) as usize;
    let count = base.pow(cells as u32);
    (0..count)
        .map(|mut code| {
            let mut m = vec![vec![0i64; a]; b];
            for cell in 0..cells {
                m[cell / a][cell % a] = lo + (code % base) as i64;
                code /= base;
            }
            m
        })
        .collect()
}

fn two_term_family() -> Vec<(Vec<Vec<i64>>, usize, usize)> {
    let mut family = Vec::new();
    for a in 1..=2 {
        for b in 1..=2 {
            for m in all_matrices(a, b, -2, 2) {
                family.push((m, a, b));
            }
        }
    }
    family
}

fn two_step(a: i64, b: i64) -> ProjectiveResolution {
    let (p0, p1, p2) = (ProjectiveModule::new(1, 0), ProjectiveModule::new(1, 1), ProjectiveModule::new(1, 2));
    let mut r = ProjectiveResolution::new();
    r.add_module(p0.clone());
    r.add_module(p1.clone());
    r.add_module(p2.clone());
    r.add_differential(ProjectiveModuleHomomorphism::new(p1.clone(), p0, vec![vec![a]]));
    r.add_differential(ProjectiveModuleHomomorphism::new(p2, p1, vec![vec![b]]));
    r
}

impl HomologyLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// The Tier 4 lemma set, with every finite lemma decided.
    pub fn standard() -> Self {
        fn lemma(name: &str, statement: &str, kind: &str) -> HomologyLemma {
            HomologyLemma::new(name.into(), LeanType::atom(statement), kind.into())
        }
        let mut lib = Self::new();

        lib.add_lemma(
            lemma("smith_form_computes_homology", "∀ finite free complexes C over ℤ, compute_at_degree C n ≅ ker d_n / im d_{n+1}", "homology")
                .with_note("needs a Lean proof of the Smith-normal-form algorithm; decided on finite families below"),
        );
        lib.add_lemma(
            lemma("resolutions_exist", "every finitely generated abelian group has a free resolution of length ≤ 1", "resolution")
                .with_note("unbounded: needs a Lean proof (structure theorem over a PID)"),
        );

        lib.decide(
            lemma("euler_characteristic_two_term", "∀ 0 → ℤ^a → ℤ^b → 0 with a, b ≤ 2 and entries in [−2, 2]: b − a = rank H₀ − rank H₁", "homology"),
            "enumerate_two_term_complexes",
            || {
                let family = two_term_family();
                for (m, a, b) in &family {
                    let h = HomologyComputer::compute_all(&two_term(m, *a, *b))?;
                    let h0 = h.group_at(0).map_or(0, |g| g.rank) as i64;
                    let h1 = h.group_at(1).map_or(0, |g| g.rank) as i64;
                    if *b as i64 - *a as i64 != h0 - h1 {
                        return Err(format!("χ mismatch for {m:?}"));
                    }
                }
                Ok(family.len() as u64)
            },
        );
        lib.decide(
            lemma("exactness_iff_zero_homology", "∀ 0 → ℤ^a → ℤ^b → 0 with a, b ≤ 2 and entries in [−2, 2]: exact ↔ every homology group is 0", "exactness"),
            "compare_exactness_with_homology",
            || {
                let family = two_term_family();
                for (m, a, b) in &family {
                    let diff = two_term(m, *a, *b);
                    let exact = ExactnessPredicateChecker::check_global_exactness(&diff).is_exact;
                    let acyclic = HomologyComputer::compute_all(&diff)?.support_degrees().is_empty();
                    if exact != acyclic {
                        return Err(format!("exactness {exact} vs acyclic {acyclic} for {m:?}"));
                    }
                }
                Ok(family.len() as u64)
            },
        );
        lib.decide(
            lemma("torsion_of_multiplication", "∀ n ∈ [−30, 30]: H₀(ℤ --n--> ℤ) = ℤ/|n| (ℤ for n = 0) and H₁ = 0 unless n = 0", "homology"),
            "enumerate_multiplication_maps",
            || {
                for n in -30i64..=30 {
                    let h = HomologyComputer::compute_all(&two_term(&[vec![n]], 1, 1))?;
                    let (h0, h1) = (h.group_at(0).cloned(), h.group_at(1).cloned());
                    let (h0, h1) = (h0.ok_or("missing H₀")?, h1.ok_or("missing H₁")?);
                    let ok = match n.unsigned_abs() {
                        0 => h0.rank == 1 && h0.torsion.is_empty() && h1.rank == 1,
                        1 => h0.is_trivial() && h1.is_trivial(),
                        k => h0.rank == 0 && h0.torsion == vec![k] && h1.is_trivial(),
                    };
                    if !ok {
                        return Err(format!("n = {n}: H₀ = {}, H₁ = {}", h0.to_string(), h1.to_string()));
                    }
                }
                Ok(61)
            },
        );
        lib.decide(
            lemma("squared_zero_verifier_sound", "∀ d₂ : ℤ → ℤ², d₁ : ℤ² → ℤ with entries in [−1, 1]: the verifier accepts ↔ d₁ ∘ d₂ = 0", "differential"),
            "compare_with_matrix_product",
            || {
                let mut cases = 0;
                for d2 in all_matrices(1, 2, -1, 1) {
                    for d1 in all_matrices(2, 1, -1, 1) {
                        let mut diff = DifferentialOperator::new(ChainComplexShape::from_ranks(vec![(0, 1), (1, 2), (2, 1)]));
                        diff.set_generator_image(2, 0, 1, vec![(0, d2[0][0]), (1, d2[1][0])]);
                        diff.set_generator_image(1, 0, 0, vec![(0, d1[0][0])]);
                        diff.set_generator_image(1, 1, 0, vec![(0, d1[0][1])]);
                        let product = d1[0][0] * d2[0][0] + d1[0][1] * d2[1][0];
                        if SquaredZeroVerifier::verify_global(&diff).is_valid != (product == 0) {
                            return Err(format!("d₁ = {d1:?}, d₂ = {d2:?}"));
                        }
                        cases += 1;
                    }
                }
                Ok(cases)
            },
        );
        lib.decide(
            lemma("cyclic_resolutions_certify", "∀ n ∈ [−40, 40]: the presentation 0 → ℤ --n--> ℤ → ℤ/n → 0 is fully certified", "resolution"),
            "certify_cyclic_resolutions",
            || {
                for n in -40i64..=40 {
                    let cert = ResolutionCertifier::certify_fully(&ProjectiveResolution::cyclic_resolution(n));
                    if !cert.level.is_fully_certified() {
                        return Err(format!("n = {n}: {}", cert.message));
                    }
                }
                Ok(81)
            },
        );
        lib.decide(
            lemma("two_step_certification_exact", "∀ a, b ∈ [−6, 6]: ℤ --b--> ℤ --a--> ℤ is certified as a resolution ↔ a = 0 ∧ |b| = 1", "exactness"),
            "certify_two_step_complexes",
            || {
                for a in -6i64..=6 {
                    for b in -6i64..=6 {
                        let certified = ResolutionCertifier::certify_fully(&two_step(a, b)).level.is_fully_certified();
                        if certified != (a == 0 && b.abs() == 1) {
                            return Err(format!("a = {a}, b = {b}: certified = {certified}"));
                        }
                    }
                }
                Ok(169)
            },
        );
        lib
    }

    /// Register `lemma` and run its decision procedure.
    pub fn decide(
        &mut self,
        mut lemma: HomologyLemma,
        procedure: &str,
        check: impl FnOnce() -> Result<u64, String>,
    ) {
        match DecisionCertificate::run(lemma.statement.clone(), procedure, check) {
            Ok(cert) => {
                lemma.proof = Some(ProofTerm::Decided(cert));
                lemma.status = HomologyLemmaStatus::Closed;
                self.context.add_theorem(lemma.name.clone(), lemma.statement.clone());
            }
            Err(counterexample) => {
                lemma.status = HomologyLemmaStatus::Failed;
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
        lemma.status = HomologyLemmaStatus::Closed;
        self.context.add_theorem(name.to_string(), statement);
        Ok(())
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: HomologyLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&HomologyLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut HomologyLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.count_status(HomologyLemmaStatus::Closed)
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.count_status(HomologyLemmaStatus::Open)
    }

    /// Count refuted lemmas
    pub fn count_failed(&self) -> usize {
        self.count_status(HomologyLemmaStatus::Failed)
    }

    fn count_status(&self, status: HomologyLemmaStatus) -> usize {
        self.lemmas.values().filter(|l| l.status == status).count()
    }

    /// Lemmas of a kind
    pub fn lemmas_by_type(&self, lemma_type: &str) -> Vec<&HomologyLemma> {
        self.lemmas.values().filter(|l| l.lemma_type == lemma_type).collect()
    }

    /// Exactness lemmas
    pub fn exactness_lemmas(&self) -> Vec<&HomologyLemma> {
        self.lemmas_by_type("exactness")
    }

    /// Differential lemmas
    pub fn differential_lemmas(&self) -> Vec<&HomologyLemma> {
        self.lemmas_by_type("differential")
    }
}

impl Default for HomologyLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standard_library_decides_every_finite_lemma() {
        let lib = HomologyLemmasLibrary::standard();
        let failed: Vec<_> = lib
            .lemmas
            .values()
            .filter(|l| l.status == HomologyLemmaStatus::Failed)
            .map(|l| (l.name.clone(), l.note.clone()))
            .collect();
        assert!(failed.is_empty(), "refuted: {failed:?}");
        assert_eq!(lib.count_proven(), 6);
        assert_eq!(lib.count_open(), 2);
        assert_eq!(lib.exactness_lemmas().len(), 2);
        assert_eq!(lib.differential_lemmas().len(), 1);
    }

    #[test]
    fn family_sizes() {
        assert_eq!(two_term_family().len(), 5 + 25 + 25 + 625);
        assert_eq!(all_matrices(2, 1, -1, 1).len(), 9);
    }
}
