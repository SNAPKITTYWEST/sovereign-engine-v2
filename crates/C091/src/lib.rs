//! cross_layer_types
//!
//! Shared vocabulary for the Tier 9 cross-layer checks: tier identifiers,
//! conversions between the representations used by different tiers, finite
//! test families, and [`CorrespondenceReport`], the result every
//! correspondence check returns.

#![warn(missing_docs)]

pub use chain_complex_shape::ChainComplexShape;
pub use gap_tensor_core::{GapTensorNode, CANDIDATE_PRIMES, SIGMA_GAP_MAX};
pub use ideal_interface::Ideal;
pub use multiplicity_arena_core::MultiplicityArena;
pub use recursive_solver_state::RecursiveSolverState;
pub use runtime_state_snapshot::{
    check_tensor, tensors_bitwise_equal, vector_state, ClaimSource, GapTensor, InvariantReport, RuntimeClaim,
    SnapshotStore, TensorShape, Violation,
};
pub use tor_functor_definition::TorIndex;

use prime_predicate::try_prime_to_tensor_node;

/// The ten tiers of the pipeline.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Tier {
    /// Gap tensor primitives (C001–C010)
    GapTensor,
    /// Multiplicity arena (C011–C020)
    Arena,
    /// Prime/gap engine (C021–C030)
    PrimeEngine,
    /// Recursive solver (C031–C040)
    Solver,
    /// Homological algebra (C041–C050)
    Homology,
    /// Tor functor (C051–C060)
    Tor,
    /// Krull dimension (C061–C070)
    Krull,
    /// Proof obligations (C071–C080)
    Proofs,
    /// Runtime bridge (C081–C090)
    Runtime,
    /// Cross-layer certification (C091–C100)
    Certification,
}

impl Tier {
    /// All tiers in order.
    pub const ALL: [Tier; 10] = [
        Tier::GapTensor,
        Tier::Arena,
        Tier::PrimeEngine,
        Tier::Solver,
        Tier::Homology,
        Tier::Tor,
        Tier::Krull,
        Tier::Proofs,
        Tier::Runtime,
        Tier::Certification,
    ];

    /// Tier number 0–9.
    pub fn number(self) -> usize {
        self as usize
    }

    /// Tier with number `n`.
    pub fn from_number(n: usize) -> Option<Tier> {
        Self::ALL.get(n).copied()
    }

    /// Human-readable name.
    pub fn name(self) -> &'static str {
        match self {
            Tier::GapTensor => "gap tensor",
            Tier::Arena => "multiplicity arena",
            Tier::PrimeEngine => "prime/gap engine",
            Tier::Solver => "recursive solver",
            Tier::Homology => "homological algebra",
            Tier::Tor => "Tor functor",
            Tier::Krull => "Krull dimension",
            Tier::Proofs => "proof obligations",
            Tier::Runtime => "runtime bridge",
            Tier::Certification => "cross-layer certification",
        }
    }

    /// Crate id range, e.g. `C011–C020`.
    pub fn crate_range(self) -> String {
        let first = self.number() * 10 + 1;
        format!("C{first:03}–C{:03}", first + 9)
    }
}

/// Tensor node for a prime (Tier 2 → Tier 0), `None` if it does not fit.
pub fn prime_node(p: u64) -> Option<GapTensorNode> {
    try_prime_to_tensor_node(p)
}

/// Principal ideal of a node's prime (Tier 0 → Tier 6); Nil ↦ (0).
pub fn ideal_of_node(node: &GapTensorNode) -> Ideal {
    Ideal::principal(node.prime_val as u64)
}

/// Nodes on a solver's path, bottom first (Tier 3 → Tier 0).
pub fn solver_path(state: &RecursiveSolverState) -> Vec<GapTensorNode> {
    let mut state = state.clone();
    let mut nodes = Vec::new();
    while let Some((_, _, node)) = state.pop_state() {
        nodes.push(node);
    }
    nodes.reverse();
    nodes
}

/// Every vector tensor of length `1..=max_len` over `alphabet`.
pub fn tensor_family(alphabet: &[GapTensorNode], max_len: usize) -> Vec<GapTensor> {
    let mut family = Vec::new();
    let mut current: Vec<Vec<GapTensorNode>> = vec![Vec::new()];
    for _ in 0..max_len {
        let next: Vec<Vec<GapTensorNode>> = current
            .iter()
            .flat_map(|prefix| {
                alphabet.iter().map(move |&n| {
                    let mut v = prefix.clone();
                    v.push(n);
                    v
                })
            })
            .collect();
        family.extend(next.iter().cloned().map(vector_state));
        current = next;
    }
    family
}

/// The standard alphabet: Nil, valid candidate nodes, a far candidate that
/// causes dissonance, a non-candidate prime and a negative weight.
pub fn standard_alphabet() -> Vec<GapTensorNode> {
    vec![
        GapTensorNode::NIL,
        GapTensorNode::new(2, 1, 1.0),
        GapTensorNode::new(3, 2, 0.5),
        GapTensorNode::new(13, 1, 1.0),
        GapTensorNode::new(4, 1, 1.0),
        GapTensorNode::new(5, 1, -1.0),
    ]
}

/// The standard test family: every tensor of length 1–3 over the standard
/// alphabet (6 + 36 + 216 = 258 tensors).
pub fn standard_family() -> Vec<GapTensor> {
    tensor_family(&standard_alphabet(), 3)
}

/// Outcome of checking a correspondence over a family of cases.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CorrespondenceReport {
    /// Name of the correspondence.
    pub name: String,
    /// Cases examined.
    pub cases_checked: u64,
    /// Descriptions of failing cases.
    pub failures: Vec<String>,
}

impl CorrespondenceReport {
    /// An empty report.
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            cases_checked: 0,
            failures: Vec::new(),
        }
    }

    /// Record one case; `describe` is only called on failure.
    pub fn check(&mut self, ok: bool, describe: impl FnOnce() -> String) {
        self.cases_checked += 1;
        if !ok {
            self.failures.push(describe());
        }
    }

    /// Record a case that could not be evaluated.
    pub fn error(&mut self, message: impl Into<String>) {
        self.cases_checked += 1;
        self.failures.push(message.into());
    }

    /// Did every case hold?
    pub fn holds(&self) -> bool {
        self.failures.is_empty() && self.cases_checked > 0
    }

    /// `Ok(cases)` if every case held, else the first failures (for a
    /// decision procedure).
    pub fn into_result(self) -> Result<u64, String> {
        if self.holds() {
            Ok(self.cases_checked)
        } else if self.cases_checked == 0 {
            Err(format!("{}: no cases checked", self.name))
        } else {
            let shown: Vec<&str> = self.failures.iter().take(3).map(String::as_str).collect();
            Err(format!(
                "{}: {} of {} cases failed, e.g. {}",
                self.name,
                self.failures.len(),
                self.cases_checked,
                shown.join("; ")
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tiers() {
        assert_eq!(Tier::from_number(4), Some(Tier::Homology));
        assert_eq!(Tier::Tor.number(), 5);
        assert_eq!(Tier::Arena.crate_range(), "C011–C020");
        assert_eq!(Tier::from_number(10), None);
    }

    #[test]
    fn conversions() {
        assert_eq!(prime_node(7).unwrap().prime_val, 7);
        assert!(prime_node(u64::MAX).is_none());
        assert!(ideal_of_node(&GapTensorNode::NIL).is_zero);
        assert!(ideal_of_node(&GapTensorNode::new(5, 1, 1.0)).contains(10));
        let mut s = RecursiveSolverState::new();
        s.push_state(GapTensorNode::new(2, 1, 1.0));
        s.push_state(GapTensorNode::new(3, 1, 1.0));
        let path: Vec<u32> = solver_path(&s).iter().map(|n| n.prime_val).collect();
        assert_eq!(path, vec![2, 3]);
    }

    #[test]
    fn families() {
        assert_eq!(standard_family().len(), 6 + 36 + 216);
        assert_eq!(tensor_family(&[GapTensorNode::NIL], 2).len(), 2);
    }

    #[test]
    fn reports() {
        let mut r = CorrespondenceReport::new("x");
        r.check(true, || unreachable!());
        assert_eq!(r.clone().into_result(), Ok(1));
        r.check(false, || "case 2".into());
        assert!(r.clone().into_result().unwrap_err().contains("case 2"));
        assert!(CorrespondenceReport::new("empty").into_result().is_err());
    }
}
