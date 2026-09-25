//! type_checking_interface
//!
//! A small proof checker for proof obligations, modelled on the implicational
//! fragment of Lean's kernel. Statements are [`LeanType`]s; the checker
//! decides whether a [`ProofTerm`] proves a statement in a [`TypeContext`]:
//!
//! * `Trivial` proves `True` and nothing else;
//! * `Reference(n)` proves the type recorded for `n` in the context — a
//!   hypothesis, a theorem, or an axiom;
//! * `Axiom(n)` proves the type of a declared axiom;
//! * `App(f, x)` is modus ponens: from `f : A → B` and `x : A`, conclude `B`;
//! * `Decided(cert)` proves the statement recorded in a
//!   [`DecisionCertificate`], which can only be obtained by running its
//!   decision procedure to success over a stated finite domain.
//!
//! This crate does not run Lean. Every proof carries an [`Evidence`] grade so
//! reports can separate constructive proofs, exhaustive computation,
//! references to theorems proven elsewhere, and bare assumptions.

#![warn(missing_docs)]

use std::collections::BTreeMap;
use std::fmt;

/// A Lean type or proposition
#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum LeanType {
    /// The sort of propositions
    Prop,
    /// Type at level u
    Type(usize),
    /// Function type / implication A → B
    Arrow(Box<LeanType>, Box<LeanType>),
    /// Named proposition or type
    Custom(String),
}

impl LeanType {
    /// The sort `Prop`
    pub fn prop() -> Self {
        Self::Prop
    }

    /// Create a type at universe level u
    pub fn type_u(u: usize) -> Self {
        Self::Type(u)
    }

    /// Implication / function type `from → to`
    pub fn arrow(from: LeanType, to: LeanType) -> Self {
        Self::Arrow(Box::new(from), Box::new(to))
    }

    /// A named proposition.
    pub fn atom(name: impl Into<String>) -> Self {
        Self::Custom(name.into())
    }

    /// The proposition `True`, proven by `Trivial`.
    pub fn truth() -> Self {
        Self::Custom("True".into())
    }

    /// Get string representation
    pub fn to_string(&self) -> String {
        match self {
            Self::Prop => "Prop".to_string(),
            Self::Type(u) => format!("Type {}", u),
            Self::Arrow(from, to) => format!("{} → {}", from.to_string(), to.to_string()),
            Self::Custom(name) => name.clone(),
        }
    }
}

/// Record of a decision procedure that ran to success.
///
/// Fields are private: the only way to obtain one is [`Self::run`], which
/// executes the check.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DecisionCertificate {
    statement: LeanType,
    procedure: String,
    cases_checked: u64,
}

impl DecisionCertificate {
    /// Run `check`, which must examine every case of the finite domain named
    /// in `statement` and return how many cases it checked, or describe a
    /// counterexample. A certificate is returned only on success.
    pub fn run(
        statement: LeanType,
        procedure: impl Into<String>,
        check: impl FnOnce() -> Result<u64, String>,
    ) -> Result<Self, String> {
        let procedure = procedure.into();
        let cases_checked = check().map_err(|e| format!("{procedure}: {e}"))?;
        Ok(Self {
            statement,
            procedure,
            cases_checked,
        })
    }

    /// The statement decided.
    pub fn statement(&self) -> &LeanType {
        &self.statement
    }

    /// Name of the decision procedure.
    pub fn procedure(&self) -> &str {
        &self.procedure
    }

    /// Number of cases examined.
    pub fn cases_checked(&self) -> u64 {
        self.cases_checked
    }
}

/// Strength of the evidence behind a proof, weakest first.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Evidence {
    /// Rests on an axiom (assumed, not proven).
    Assumed,
    /// Rests on a named theorem whose own proof is outside this term.
    Referenced,
    /// Established by an exhaustive decision procedure over a finite domain.
    Computed,
    /// Closed constructively within the checker.
    Constructive,
}

/// A proof term.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ProofTerm {
    /// Use of a declared axiom
    Axiom(String),
    /// Proof of `True`
    Trivial,
    /// Reference to a hypothesis, theorem or axiom in the context
    Reference(String),
    /// Modus ponens: apply a proof of `A → B` to a proof of `A`
    App(Box<ProofTerm>, Box<ProofTerm>),
    /// Result of an executed decision procedure
    Decided(DecisionCertificate),
}

impl ProofTerm {
    /// Use of the axiom `name`.
    pub fn axiom(name: &str) -> Self {
        Self::Axiom(name.to_string())
    }

    /// Reference to `name`.
    pub fn reference(name: &str) -> Self {
        Self::Reference(name.to_string())
    }

    /// Modus ponens.
    pub fn app(f: ProofTerm, x: ProofTerm) -> Self {
        Self::App(Box::new(f), Box::new(x))
    }

    /// Structurally complete (no holes). Whether it proves a particular
    /// statement is decided by [`TypeContext::check`].
    pub fn is_complete(&self) -> bool {
        match self {
            Self::Trivial | Self::Axiom(_) | Self::Reference(_) | Self::Decided(_) => true,
            Self::App(f, x) => f.is_complete() && x.is_complete(),
        }
    }

    /// Weakest evidence the proof relies on.
    pub fn evidence(&self) -> Evidence {
        match self {
            Self::Trivial => Evidence::Constructive,
            Self::Decided(_) => Evidence::Computed,
            Self::Reference(_) => Evidence::Referenced,
            Self::Axiom(_) => Evidence::Assumed,
            Self::App(f, x) => f.evidence().min(x.evidence()),
        }
    }
}

/// Why a proof term fails to check.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TypeError {
    /// A referenced name is not in the context.
    UnknownName(String),
    /// An axiom was used that has not been declared.
    UnknownAxiom(String),
    /// Applied a proof whose statement is not an implication.
    NotAnImplication(LeanType),
    /// The argument proves the wrong premise.
    ArgumentMismatch {
        /// Premise required.
        expected: LeanType,
        /// Statement proven by the argument.
        found: LeanType,
    },
    /// The proof proves a different statement.
    Mismatch {
        /// Statement required.
        expected: LeanType,
        /// Statement proven.
        found: LeanType,
    },
}

impl fmt::Display for TypeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnknownName(n) => write!(f, "unknown name `{n}`"),
            Self::UnknownAxiom(n) => write!(f, "undeclared axiom `{n}`"),
            Self::NotAnImplication(t) => write!(f, "`{}` is not an implication", t.to_string()),
            Self::ArgumentMismatch { expected, found } => write!(
                f,
                "argument proves `{}`, premise is `{}`",
                found.to_string(),
                expected.to_string()
            ),
            Self::Mismatch { expected, found } => write!(
                f,
                "proof proves `{}`, statement is `{}`",
                found.to_string(),
                expected.to_string()
            ),
        }
    }
}

impl std::error::Error for TypeError {}

/// A type checking context: hypotheses, theorems and axioms.
#[derive(Clone, Debug)]
pub struct TypeContext {
    /// Hypotheses (local variables) and their types
    pub variables: BTreeMap<String, LeanType>,
    /// Theorems and their statements
    pub theorems: BTreeMap<String, LeanType>,
    /// Axioms (assumptions) and their statements
    pub axioms: BTreeMap<String, LeanType>,
}

impl TypeContext {
    /// Create an empty context
    pub fn new() -> Self {
        Self {
            variables: BTreeMap::new(),
            theorems: BTreeMap::new(),
            axioms: BTreeMap::new(),
        }
    }

    /// Add a hypothesis
    pub fn add_variable(&mut self, name: String, ty: LeanType) {
        self.variables.insert(name, ty);
    }

    /// Add a theorem
    pub fn add_theorem(&mut self, name: String, ty: LeanType) {
        self.theorems.insert(name, ty);
    }

    /// Declare an axiom
    pub fn add_axiom(&mut self, name: String, ty: LeanType) {
        self.axioms.insert(name, ty);
    }

    /// Look up a hypothesis
    pub fn lookup_variable(&self, name: &str) -> Option<&LeanType> {
        self.variables.get(name)
    }

    /// Look up a theorem
    pub fn lookup_theorem(&self, name: &str) -> Option<&LeanType> {
        self.theorems.get(name)
    }

    /// Look up an axiom
    pub fn lookup_axiom(&self, name: &str) -> Option<&LeanType> {
        self.axioms.get(name)
    }

    /// The statement a proof term proves in this context.
    pub fn infer(&self, proof: &ProofTerm) -> Result<LeanType, TypeError> {
        match proof {
            ProofTerm::Trivial => Ok(LeanType::truth()),
            ProofTerm::Decided(cert) => Ok(cert.statement().clone()),
            ProofTerm::Axiom(name) => self
                .lookup_axiom(name)
                .cloned()
                .ok_or_else(|| TypeError::UnknownAxiom(name.clone())),
            ProofTerm::Reference(name) => self
                .lookup_variable(name)
                .or_else(|| self.lookup_theorem(name))
                .or_else(|| self.lookup_axiom(name))
                .cloned()
                .ok_or_else(|| TypeError::UnknownName(name.clone())),
            ProofTerm::App(f, x) => match self.infer(f)? {
                LeanType::Arrow(premise, conclusion) => {
                    let found = self.infer(x)?;
                    if found != *premise {
                        return Err(TypeError::ArgumentMismatch {
                            expected: *premise,
                            found,
                        });
                    }
                    Ok(*conclusion)
                }
                other => Err(TypeError::NotAnImplication(other)),
            },
        }
    }

    /// Check that `proof` proves `statement`.
    pub fn check(&self, proof: &ProofTerm, statement: &LeanType) -> Result<(), TypeError> {
        let found = self.infer(proof)?;
        if &found != statement {
            return Err(TypeError::Mismatch {
                expected: statement.clone(),
                found,
            });
        }
        Ok(())
    }
}

impl Default for TypeContext {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lean_type_prop() {
        assert_eq!(LeanType::prop().to_string(), "Prop");
    }

    #[test]
    fn test_lean_type_arrow() {
        let ty = LeanType::arrow(LeanType::prop(), LeanType::prop());
        assert_eq!(ty.to_string(), "Prop → Prop");
    }

    #[test]
    fn trivial_proves_only_true() {
        let ctx = TypeContext::new();
        assert!(ctx.check(&ProofTerm::Trivial, &LeanType::truth()).is_ok());
        assert!(matches!(
            ctx.check(&ProofTerm::Trivial, &LeanType::atom("P")),
            Err(TypeError::Mismatch { .. })
        ));
        assert!(ctx.check(&ProofTerm::Trivial, &LeanType::prop()).is_err());
    }

    #[test]
    fn modus_ponens() {
        let (p, q) = (LeanType::atom("P"), LeanType::atom("Q"));
        let mut ctx = TypeContext::new();
        ctx.add_theorem("p_holds".into(), p.clone());
        ctx.add_theorem("p_implies_q".into(), LeanType::arrow(p.clone(), q.clone()));
        let proof = ProofTerm::app(ProofTerm::reference("p_implies_q"), ProofTerm::reference("p_holds"));
        assert!(proof.is_complete());
        assert!(ctx.check(&proof, &q).is_ok());
        assert_eq!(proof.evidence(), Evidence::Referenced);

        let backwards = ProofTerm::app(ProofTerm::reference("p_holds"), ProofTerm::reference("p_holds"));
        assert!(matches!(ctx.infer(&backwards), Err(TypeError::NotAnImplication(_))));
        ctx.add_theorem("q_holds".into(), q.clone());
        let wrong_arg = ProofTerm::app(ProofTerm::reference("p_implies_q"), ProofTerm::reference("q_holds"));
        assert!(matches!(ctx.infer(&wrong_arg), Err(TypeError::ArgumentMismatch { .. })));
    }

    #[test]
    fn axioms_must_be_declared_and_are_graded_assumed() {
        let p = LeanType::atom("P");
        let mut ctx = TypeContext::new();
        assert_eq!(ctx.check(&ProofTerm::axiom("ax"), &p), Err(TypeError::UnknownAxiom("ax".into())));
        ctx.add_axiom("ax".into(), p.clone());
        assert!(ctx.check(&ProofTerm::axiom("ax"), &p).is_ok());
        assert_eq!(ProofTerm::axiom("ax").evidence(), Evidence::Assumed);
        assert!(ctx.check(&ProofTerm::reference("missing"), &p).is_err());
    }

    #[test]
    fn decided_statements() {
        let stmt = LeanType::atom("∀ n < 10, n * n < 100");
        let cert = DecisionCertificate::run(stmt.clone(), "square_bound", || {
            let bad = (0u64..10).find(|n| n * n >= 100);
            match bad {
                Some(n) => Err(format!("counterexample {n}")),
                None => Ok(10),
            }
        })
        .unwrap();
        assert_eq!(cert.cases_checked(), 10);
        let proof = ProofTerm::Decided(cert);
        assert!(TypeContext::new().check(&proof, &stmt).is_ok());
        assert_eq!(proof.evidence(), Evidence::Computed);

        let failed = DecisionCertificate::run(LeanType::atom("false claim"), "always_fails", || {
            Err("counterexample 3".into())
        });
        assert!(failed.unwrap_err().contains("counterexample 3"));
    }

    #[test]
    fn app_completeness_and_evidence() {
        let partial = ProofTerm::app(ProofTerm::Trivial, ProofTerm::axiom("a"));
        assert!(partial.is_complete());
        assert_eq!(partial.evidence(), Evidence::Assumed);
        assert_eq!(ProofTerm::Trivial.evidence(), Evidence::Constructive);
    }

    #[test]
    fn test_type_context() {
        let mut ctx = TypeContext::new();
        ctx.add_variable("x".to_string(), LeanType::prop());
        assert!(ctx.lookup_variable("x").is_some());
        assert!(ctx.lookup_variable("y").is_none());
        ctx.add_theorem("thm".to_string(), LeanType::prop());
        assert!(ctx.lookup_theorem("thm").is_some());
    }
}
