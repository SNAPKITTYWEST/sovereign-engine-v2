//! type_checking_interface
//!
//! Interface to Lean 4 type checker for proof obligations.

#![warn(missing_docs)]

use std::collections::BTreeMap;

/// A Lean type or proposition
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LeanType {
    /// Universe level
    Prop,
    /// Type at level u
    Type(usize),
    /// Function type A → B
    Arrow(Box<LeanType>, Box<LeanType>),
    /// Custom type/predicate by name
    Custom(String),
}

impl LeanType {
    /// Create a proposition
    pub fn prop() -> Self {
        Self::Prop
    }

    /// Create a type at universe level u
    pub fn type_u(u: usize) -> Self {
        Self::Type(u)
    }

    /// Create a function type
    pub fn arrow(from: LeanType, to: LeanType) -> Self {
        Self::Arrow(Box::new(from), Box::new(to))
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

/// A proof term or tactic
#[derive(Clone, Debug)]
pub enum ProofTerm {
    /// Axiom (assumed true)
    Axiom(String),
    /// Trivial proof
    Trivial,
    /// Proof reference
    Reference(String),
    /// Application of function to argument
    App(Box<ProofTerm>, Box<ProofTerm>),
}

impl ProofTerm {
    /// Create an axiom
    pub fn axiom(name: &str) -> Self {
        Self::Axiom(name.to_string())
    }

    /// Is this a complete proof?
    pub fn is_complete(&self) -> bool {
        match self {
            Self::Trivial | Self::Axiom(_) => true,
            Self::Reference(_) => true,
            _ => false,
        }
    }
}

/// A Lean type checking context
#[derive(Clone, Debug)]
pub struct TypeContext {
    /// Variables and their types
    pub variables: BTreeMap<String, LeanType>,
    /// Theorems and their types
    pub theorems: BTreeMap<String, LeanType>,
}

impl TypeContext {
    /// Create an empty context
    pub fn new() -> Self {
        Self {
            variables: BTreeMap::new(),
            theorems: BTreeMap::new(),
        }
    }

    /// Add a variable to the context
    pub fn add_variable(&mut self, name: String, ty: LeanType) {
        self.variables.insert(name, ty);
    }

    /// Add a theorem to the context
    pub fn add_theorem(&mut self, name: String, ty: LeanType) {
        self.theorems.insert(name, ty);
    }

    /// Look up a variable
    pub fn lookup_variable(&self, name: &str) -> Option<&LeanType> {
        self.variables.get(name)
    }

    /// Look up a theorem
    pub fn lookup_theorem(&self, name: &str) -> Option<&LeanType> {
        self.theorems.get(name)
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
        let ty = LeanType::prop();
        assert_eq!(ty.to_string(), "Prop");
    }

    #[test]
    fn test_lean_type_arrow() {
        let ty = LeanType::arrow(LeanType::prop(), LeanType::prop());
        assert_eq!(ty.to_string(), "Prop → Prop");
    }

    #[test]
    fn test_proof_term_trivial() {
        let proof = ProofTerm::Trivial;
        assert!(proof.is_complete());
    }

    #[test]
    fn test_proof_term_axiom() {
        let proof = ProofTerm::axiom("example");
        assert!(proof.is_complete());
    }

    #[test]
    fn test_type_context() {
        let mut ctx = TypeContext::new();
        ctx.add_variable("x".to_string(), LeanType::prop());
        assert!(ctx.lookup_variable("x").is_some());
        assert!(ctx.lookup_variable("y").is_none());
    }

    #[test]
    fn test_type_context_theorem() {
        let mut ctx = TypeContext::new();
        ctx.add_theorem("thm".to_string(), LeanType::prop());
        assert!(ctx.lookup_theorem("thm").is_some());
    }
}
