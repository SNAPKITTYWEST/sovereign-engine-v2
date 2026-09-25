//! recursion_lemmas_library
//!
//! Lemmas about the recursive solver's depth control and backtracking
//! (Tier 3). [`RecursionLemmasLibrary::standard`] decides the bounded
//! lemmas by running the Tier 3 code over every case (evidence grade
//! `Computed`). Termination of the solver on arbitrary inputs is stated and
//! left `Open`: it needs a termination measure proven in Lean.

#![warn(missing_docs)]

use recursion_backtracking::BacktrackManager;
use recursion_depth_management::{DepthManager, RecursionContext, RecursionDepthGuard};
use recursive_solver_state::{RecursiveSolverState, MAX_RECURSION_DEPTH};
use std::collections::BTreeMap;

pub use type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError};

/// Largest depth bound covered by the decided lemmas.
pub const DECIDED_DEPTH: usize = 20;

/// Status of a recursion lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RecursionLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Refuted (a decision procedure found a counterexample)
    Failed,
}

/// A recursion termination or depth lemma
#[derive(Clone, Debug)]
pub struct RecursionLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: RecursionLemmaStatus,
    /// Proof, once closed
    pub proof: Option<ProofTerm>,
    /// Largest depth the lemma covers (`None` = unbounded)
    pub max_depth: Option<usize>,
    /// Counterexample, or what remains to be done
    pub note: Option<String>,
}

impl RecursionLemma {
    /// Create a new open lemma
    pub fn new(name: String, statement: LeanType) -> Self {
        Self {
            name,
            statement,
            status: RecursionLemmaStatus::Open,
            proof: None,
            max_depth: None,
            note: None,
        }
    }

    /// Set the largest depth covered
    pub fn with_max_depth(mut self, depth: usize) -> Self {
        self.max_depth = Some(depth);
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
        self.status = RecursionLemmaStatus::Closed;
        Ok(())
    }

    /// Check if lemma is proven
    pub fn is_proven(&self) -> bool {
        self.status == RecursionLemmaStatus::Closed
    }

    /// Evidence grade, if proven
    pub fn evidence(&self) -> Option<Evidence> {
        self.proof.as_ref().filter(|_| self.is_proven()).map(ProofTerm::evidence)
    }
}

/// Library of recursion lemmas
#[derive(Clone, Debug)]
pub struct RecursionLemmasLibrary {
    /// All lemmas indexed by name
    pub lemmas: BTreeMap<String, RecursionLemma>,
    /// Theorems and axioms available to proofs
    pub context: TypeContext,
}

fn nest(guard: &mut RecursionDepthGuard<'_>, remaining: u32) -> Result<(), String> {
    if remaining == 0 {
        return Ok(());
    }
    let expected = guard.depth() + 1;
    let mut inner = guard.enter().ok_or("enter refused below the maximum")?;
    if inner.depth() != expected || inner.manager().current_depth() != expected {
        return Err(format!("depth {} ≠ {expected}", inner.depth()));
    }
    nest(&mut inner, remaining - 1)?;
    drop(inner);
    if guard.manager().current_depth() != expected - 1 {
        return Err(format!("depth not restored to {}", expected - 1));
    }
    Ok(())
}

impl RecursionLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// The Tier 3 lemma set, with every bounded lemma decided.
    pub fn standard() -> Self {
        fn lemma(name: &str, statement: String) -> RecursionLemma {
            RecursionLemma::new(name.into(), LeanType::atom(statement))
        }
        let mut lib = Self::new();
        let m = DECIDED_DEPTH as u32;

        lib.add_lemma(
            lemma("solver_terminates", "every run of the recursive solver on a finite gap candidate set terminates".into())
                .with_note("needs a termination measure proven in Lean; depth bounds decided below"),
        );

        lib.decide(
            lemma("depth_manager_respects_maximum", format!("∀ m ≤ {m}, a DepthManager with maximum m accepts exactly m increases (returning 1..m) and then refuses"))
                .with_max_depth(DECIDED_DEPTH),
            "increase_until_refused",
            || {
                for max in 0..=m {
                    let mut d = DepthManager::with_max_depth(max);
                    for expected in 1..=max {
                        if d.increase_depth() != Some(expected) {
                            return Err(format!("max {max}: increase {expected} failed"));
                        }
                    }
                    if d.increase_depth().is_some() || d.current_depth() != max {
                        return Err(format!("max {max}: exceeded"));
                    }
                }
                Ok(u64::from(m) + 1)
            },
        );
        lib.decide(
            lemma("decrease_inverts_increase", format!("∀ k ≤ m ≤ {m}, k increases followed by k decreases return a DepthManager to top level"))
                .with_max_depth(DECIDED_DEPTH),
            "increase_then_decrease",
            || {
                let mut cases = 0;
                for max in 0..=m {
                    for k in 0..=max {
                        let mut d = DepthManager::with_max_depth(max);
                        for _ in 0..k {
                            d.increase_depth().ok_or("increase refused")?;
                        }
                        for _ in 0..k {
                            d.decrease_depth().ok_or("decrease refused")?;
                        }
                        if !d.is_top_level() || d.decrease_depth().is_some() {
                            return Err(format!("max {max}, k {k}: not back at top level"));
                        }
                        cases += 1;
                    }
                }
                Ok(cases)
            },
        );
        lib.decide(
            lemma("guards_restore_depth", format!("∀ n ≤ {m}, n nested RecursionDepthGuards report depths 1..n and each drop restores the previous depth"))
                .with_max_depth(DECIDED_DEPTH),
            "nest_guards",
            || {
                for n in 1..=m {
                    let mut ctx = RecursionContext::new();
                    {
                        let mut outer = ctx.enter().ok_or("first enter refused")?;
                        nest(&mut outer, n - 1)?;
                    }
                    if ctx.manager().current_depth() != 0 {
                        return Err(format!("n {n}: depth {} after all guards dropped", ctx.manager().current_depth()));
                    }
                }
                Ok(u64::from(m))
            },
        );
        lib.decide(
            lemma("solver_depth_flag", format!("∀ d ≤ {}, after d increases RecursiveSolverState.exceeds_max_depth ↔ depth ≥ MAX_RECURSION_DEPTH ({MAX_RECURSION_DEPTH})", MAX_RECURSION_DEPTH + 10))
                .with_max_depth((MAX_RECURSION_DEPTH + 10) as usize),
            "increase_and_compare",
            || {
                let mut s = RecursiveSolverState::new();
                for d in 0..=MAX_RECURSION_DEPTH + 10 {
                    if s.depth() != d || s.exceeds_max_depth() != (d >= MAX_RECURSION_DEPTH) {
                        return Err(format!("depth {d}"));
                    }
                    s.increase_depth();
                }
                Ok(u64::from(MAX_RECURSION_DEPTH) + 11)
            },
        );
        lib.decide(
            lemma("backtracking_is_lifo", format!("∀ n ≤ {m}, n saved checkpoints are popped in reverse order with increasing unique ids"))
                .with_max_depth(DECIDED_DEPTH),
            "save_and_pop",
            || {
                for n in 0..=m {
                    let mut b = BacktrackManager::new();
                    let ids: Vec<u64> = (0..n).map(|d| b.save_checkpoint(RecursiveSolverState::new(), d)).collect();
                    if ids.windows(2).any(|w| w[1] <= w[0]) {
                        return Err(format!("n {n}: ids not increasing"));
                    }
                    for d in (0..n).rev() {
                        let cp = b.pop_checkpoint().ok_or("missing checkpoint")?;
                        if cp.depth != d || cp.id != ids[d as usize] {
                            return Err(format!("n {n}: popped depth {} expected {d}", cp.depth));
                        }
                    }
                    if b.can_backtrack() {
                        return Err(format!("n {n}: checkpoints left over"));
                    }
                }
                Ok(u64::from(m) + 1)
            },
        );
        lib
    }

    /// Register `lemma` and run its decision procedure.
    pub fn decide(
        &mut self,
        mut lemma: RecursionLemma,
        procedure: &str,
        check: impl FnOnce() -> Result<u64, String>,
    ) {
        match DecisionCertificate::run(lemma.statement.clone(), procedure, check) {
            Ok(cert) => {
                lemma.proof = Some(ProofTerm::Decided(cert));
                lemma.status = RecursionLemmaStatus::Closed;
                self.context.add_theorem(lemma.name.clone(), lemma.statement.clone());
            }
            Err(counterexample) => {
                lemma.status = RecursionLemmaStatus::Failed;
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
        lemma.status = RecursionLemmaStatus::Closed;
        self.context.add_theorem(name.to_string(), statement);
        Ok(())
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: RecursionLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&RecursionLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut RecursionLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.count_status(RecursionLemmaStatus::Closed)
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.count_status(RecursionLemmaStatus::Open)
    }

    /// Count refuted lemmas
    pub fn count_failed(&self) -> usize {
        self.count_status(RecursionLemmaStatus::Failed)
    }

    fn count_status(&self, status: RecursionLemmaStatus) -> usize {
        self.lemmas.values().filter(|l| l.status == status).count()
    }

    /// Lemmas that cover `depth` (unbounded lemmas cover every depth)
    pub fn lemmas_for_depth(&self, depth: usize) -> Vec<&RecursionLemma> {
        self.lemmas
            .values()
            .filter(|l| l.max_depth.map_or(true, |md| md >= depth))
            .collect()
    }

    /// Largest bounded depth covered by any lemma
    pub fn max_covered_depth(&self) -> Option<usize> {
        self.lemmas.values().filter_map(|l| l.max_depth).max()
    }
}

impl Default for RecursionLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standard_library_decides_every_bounded_lemma() {
        let lib = RecursionLemmasLibrary::standard();
        let failed: Vec<_> = lib
            .lemmas
            .values()
            .filter(|l| l.status == RecursionLemmaStatus::Failed)
            .map(|l| (l.name.clone(), l.note.clone()))
            .collect();
        assert!(failed.is_empty(), "refuted: {failed:?}");
        assert_eq!(lib.count_proven(), 5);
        assert_eq!(lib.count_open(), 1);
        assert_eq!(lib.max_covered_depth(), Some((MAX_RECURSION_DEPTH + 10) as usize));
        assert!(!lib.get_lemma("solver_terminates").unwrap().is_proven());
    }

    #[test]
    fn open_lemmas_need_real_proofs() {
        let mut lib = RecursionLemmasLibrary::standard();
        assert!(lib.prove_lemma("solver_terminates", ProofTerm::Trivial).is_err());
        assert_eq!(lib.lemmas_for_depth(5).len(), 6);
        assert_eq!(lib.lemmas_for_depth(50).len(), 2);
    }
}
