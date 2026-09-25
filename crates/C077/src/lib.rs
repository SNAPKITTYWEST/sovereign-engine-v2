//! tor_resolution_lemmas_library
//!
//! Lemmas about Tor over Z (Tier 5). [`TorLemmasLibrary::standard`] decides
//! the finite lemmas by computing Tor for every pair of cyclic groups in a
//! range and comparing against the known answer
//! `Tor_0(Z/m, Z/n) = Tor_1(Z/m, Z/n) = Z/gcd(m, n)` (evidence grade
//! `Computed`). Independence of Tor from the chosen resolutions is stated
//! and left `Open`.

#![warn(missing_docs)]

use derived_homology::tor_of;
use functoriality_of_tor::{compose_tor_maps, induced_tor_map, reduce_mod_target};
use std::collections::BTreeMap;
use tor_functor_definition::{ProjectiveResolution, TorComputation, TorGroup};
use tor_zero_structure::verify_tor_zero_universal_property;

pub use type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError};

/// Largest cyclic order covered by the decided lemmas.
pub const DECIDED_ORDER: i64 = 24;

/// Status of a Tor lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TorLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Refuted (a decision procedure found a counterexample)
    Failed,
}

/// A Tor functor or resolution lemma
#[derive(Clone, Debug)]
pub struct TorLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: TorLemmaStatus,
    /// Proof, once closed
    pub proof: Option<ProofTerm>,
    /// Tor degree the lemma is about, if one
    pub tor_degree: Option<usize>,
    /// Counterexample, or what remains to be done
    pub note: Option<String>,
}

impl TorLemma {
    /// Create a new open lemma
    pub fn new(name: String, statement: LeanType) -> Self {
        Self {
            name,
            statement,
            status: TorLemmaStatus::Open,
            proof: None,
            tor_degree: None,
            note: None,
        }
    }

    /// Set the Tor degree
    pub fn with_tor_degree(mut self, degree: usize) -> Self {
        self.tor_degree = Some(degree);
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
        self.status = TorLemmaStatus::Closed;
        Ok(())
    }

    /// Check if lemma is proven
    pub fn is_proven(&self) -> bool {
        self.status == TorLemmaStatus::Closed
    }

    /// Evidence grade, if proven
    pub fn evidence(&self) -> Option<Evidence> {
        self.proof.as_ref().filter(|_| self.is_proven()).map(ProofTerm::evidence)
    }
}

/// Library of Tor lemmas
#[derive(Clone, Debug)]
pub struct TorLemmasLibrary {
    /// All lemmas indexed by name
    pub lemmas: BTreeMap<String, TorLemma>,
    /// Theorems and axioms available to proofs
    pub context: TypeContext,
}

fn gcd(a: i64, b: i64) -> u64 {
    let (mut a, mut b) = (a.unsigned_abs(), b.unsigned_abs());
    while b != 0 {
        (a, b) = (b, a % b);
    }
    a
}

fn z_mod(n: i64) -> ProjectiveResolution {
    ProjectiveResolution::cyclic_resolution(n)
}

/// `(free rank, torsion orders)` of `Tor_i`, trivial if not computed.
fn invariants(tor: &TorComputation, i: usize) -> (usize, Vec<u64>) {
    tor.tor(i).map_or((0, vec![]), |g: &TorGroup| (g.rank, g.torsion_orders()))
}

/// Invariants of `Z/g` (`Z` for `g = 0`, trivial for `g = 1`).
fn cyclic(g: u64) -> (usize, Vec<u64>) {
    match g {
        0 => (1, vec![]),
        1 => (0, vec![]),
        g => (0, vec![g]),
    }
}

impl TorLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// The Tier 5 lemma set, with every finite lemma decided.
    pub fn standard() -> Self {
        fn lemma(name: &str, statement: String) -> TorLemma {
            TorLemma::new(name.into(), LeanType::atom(statement))
        }
        let mut lib = Self::new();
        let n = DECIDED_ORDER;

        lib.add_lemma(
            lemma("tor_balanced", "Tor_i(M, N) is independent of the chosen free resolutions of M and N".into())
                .with_note("needs a Lean proof (comparison theorem); instances agree below"),
        );

        lib.decide(
            lemma("tor0_cyclic_is_gcd", format!("∀ 0 ≤ m, n ≤ {n}: Tor₀(ℤ/m, ℤ/n) ≅ ℤ/gcd(m, n)")).with_tor_degree(0),
            "compute_tor0",
            || {
                for a in 0..=n {
                    for b in 0..=n {
                        let tor = tor_of(&z_mod(a), &z_mod(b))?;
                        if invariants(&tor, 0) != cyclic(gcd(a, b)) {
                            return Err(format!("Tor₀(ℤ/{a}, ℤ/{b}) = {:?}", invariants(&tor, 0)));
                        }
                    }
                }
                Ok(((n + 1) * (n + 1)) as u64)
            },
        );
        lib.decide(
            lemma("tor1_cyclic_is_gcd", format!("∀ 0 ≤ m, n ≤ {n}: Tor₁(ℤ/m, ℤ/n) ≅ ℤ/gcd(m, n) if m, n ≠ 0, and 0 otherwise")).with_tor_degree(1),
            "compute_tor1",
            || {
                for a in 0..=n {
                    for b in 0..=n {
                        let tor = tor_of(&z_mod(a), &z_mod(b))?;
                        let expected = if a == 0 || b == 0 { (0, vec![]) } else { cyclic(gcd(a, b)) };
                        if invariants(&tor, 1) != expected {
                            return Err(format!("Tor₁(ℤ/{a}, ℤ/{b}) = {:?}", invariants(&tor, 1)));
                        }
                    }
                }
                Ok(((n + 1) * (n + 1)) as u64)
            },
        );
        lib.decide(
            lemma("higher_tor_vanishes", format!("∀ 0 ≤ m, n ≤ {n}, i ≥ 2: Tor_i(ℤ/m, ℤ/n) = 0")).with_tor_degree(2),
            "compute_higher_tor",
            || {
                for a in 0..=n {
                    for b in 0..=n {
                        let tor = tor_of(&z_mod(a), &z_mod(b))?;
                        if tor.groups.iter().any(|(&i, g)| i >= 2 && !g.is_trivial()) {
                            return Err(format!("non-zero higher Tor for ℤ/{a}, ℤ/{b}"));
                        }
                    }
                }
                Ok(((n + 1) * (n + 1)) as u64)
            },
        );
        lib.decide(
            lemma("tor_symmetric", "∀ 0 ≤ m, n ≤ 16, i ∈ {0, 1}: Tor_i(ℤ/m, ℤ/n) ≅ Tor_i(ℤ/n, ℤ/m)".into()),
            "compare_both_orders",
            || {
                for a in 0..=16i64 {
                    for b in a..=16i64 {
                        let (x, y) = (tor_of(&z_mod(a), &z_mod(b))?, tor_of(&z_mod(b), &z_mod(a))?);
                        for i in 0..2 {
                            if invariants(&x, i) != invariants(&y, i) {
                                return Err(format!("Tor_{i}(ℤ/{a}, ℤ/{b}) ≠ Tor_{i}(ℤ/{b}, ℤ/{a})"));
                            }
                        }
                    }
                }
                Ok(17 * 18 / 2)
            },
        );
        lib.decide(
            lemma("tor0_is_tensor_product", "∀ 0 ≤ m, n ≤ 16: Tor₀ from Tot(P ⊗ Q) equals ℤ/m ⊗ ℤ/n from presentations".into()).with_tor_degree(0),
            "cross_check_tensor_product",
            || {
                for a in 0..=16i64 {
                    for b in 0..=16i64 {
                        if !verify_tor_zero_universal_property(&z_mod(a), &z_mod(b))? {
                            return Err(format!("disagreement for ℤ/{a}, ℤ/{b}"));
                        }
                    }
                }
                Ok(17 * 17)
            },
        );
        lib.decide(
            lemma("functor_preserves_identity", "∀ 1 ≤ m, n ≤ 10, i ∈ {0, 1}: (id_{ℤ/m})_* = id on Tor_i(ℤ/m, ℤ/n)".into()),
            "induce_identity_maps",
            || {
                let mut cases = 0;
                for a in 1..=10i64 {
                    for b in 1..=10i64 {
                        for i in 0..2 {
                            let m = induced_tor_map(&z_mod(a), &z_mod(a), &z_mod(b), &[vec![1]], i)?;
                            let identity = (0..m.map.source_rank)
                                .all(|r| (0..m.map.target_rank).all(|c| m.map.get(r, c) == i32::from(r == c)));
                            if !identity {
                                return Err(format!("id_* ≠ id on Tor_{i}(ℤ/{a}, ℤ/{b})"));
                            }
                            cases += 1;
                        }
                    }
                }
                Ok(cases)
            },
        );
        lib.decide(
            lemma("functor_preserves_composition", "∀ m ∈ {4, 6, 8, 9, 12}, n ∈ {2, 3, 4, 6}, f, g ∈ {2, 3, 5}, i ∈ {0, 1}: (g ∘ f)_* = g_* ∘ f_* on Tor_i(ℤ/m, ℤ/n)".into()),
            "compose_induced_maps",
            || {
                let mut cases = 0;
                for a in [4i64, 6, 8, 9, 12] {
                    for b in [2i64, 3, 4, 6] {
                        for f in [2i64, 3, 5] {
                            for g in [2i64, 3, 5] {
                                for i in 0..2 {
                                    let (m, q) = (z_mod(a), z_mod(b));
                                    let fs = induced_tor_map(&m, &m, &q, &[vec![f]], i)?;
                                    let gs = induced_tor_map(&m, &m, &q, &[vec![g]], i)?;
                                    let gfs = induced_tor_map(&m, &m, &q, &[vec![g * f]], i)?;
                                    let composed = compose_tor_maps(&fs.map, &gs.map).ok_or("composition overflow")?;
                                    if reduce_mod_target(&composed, &gfs.target) != gfs.map {
                                        return Err(format!("m {a}, n {b}, f {f}, g {g}, degree {i}"));
                                    }
                                    cases += 1;
                                }
                            }
                        }
                    }
                }
                Ok(cases)
            },
        );
        lib
    }

    /// Register `lemma` and run its decision procedure.
    pub fn decide(
        &mut self,
        mut lemma: TorLemma,
        procedure: &str,
        check: impl FnOnce() -> Result<u64, String>,
    ) {
        match DecisionCertificate::run(lemma.statement.clone(), procedure, check) {
            Ok(cert) => {
                lemma.proof = Some(ProofTerm::Decided(cert));
                lemma.status = TorLemmaStatus::Closed;
                self.context.add_theorem(lemma.name.clone(), lemma.statement.clone());
            }
            Err(counterexample) => {
                lemma.status = TorLemmaStatus::Failed;
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
        lemma.status = TorLemmaStatus::Closed;
        self.context.add_theorem(name.to_string(), statement);
        Ok(())
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: TorLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&TorLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut TorLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.count_status(TorLemmaStatus::Closed)
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.count_status(TorLemmaStatus::Open)
    }

    /// Count refuted lemmas
    pub fn count_failed(&self) -> usize {
        self.count_status(TorLemmaStatus::Failed)
    }

    fn count_status(&self, status: TorLemmaStatus) -> usize {
        self.lemmas.values().filter(|l| l.status == status).count()
    }

    /// Lemmas about Tor in a given degree
    pub fn lemmas_for_degree(&self, degree: usize) -> Vec<&TorLemma> {
        self.lemmas.values().filter(|l| l.tor_degree == Some(degree)).collect()
    }

    /// Highest degree with a lemma
    pub fn max_degree(&self) -> Option<usize> {
        self.lemmas.values().filter_map(|l| l.tor_degree).max()
    }
}

impl Default for TorLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standard_library_decides_every_finite_lemma() {
        let lib = TorLemmasLibrary::standard();
        let failed: Vec<_> = lib
            .lemmas
            .values()
            .filter(|l| l.status == TorLemmaStatus::Failed)
            .map(|l| (l.name.clone(), l.note.clone()))
            .collect();
        assert!(failed.is_empty(), "refuted: {failed:?}");
        assert_eq!(lib.count_proven(), 7);
        assert_eq!(lib.count_open(), 1);
        assert_eq!(lib.lemmas_for_degree(0).len(), 2);
        assert_eq!(lib.max_degree(), Some(2));
    }

    #[test]
    fn helpers() {
        assert_eq!(gcd(12, 18), 6);
        assert_eq!(gcd(0, 5), 5);
        assert_eq!(cyclic(0), (1, vec![]));
        assert_eq!(cyclic(1), (0, vec![]));
        assert_eq!(cyclic(4), (0, vec![4]));
    }
}
