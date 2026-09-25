//! prime_state_binding
//!
//! Binds a run of the prime/gap engine (Tier 2) to the runtime snapshot
//! store: the primes up to a limit are enumerated, encoded as tensor nodes
//! and recorded. Claims about the run (all values prime, gaps consistent,
//! orderings are permutations, encoding faithful) are re-checkable.

#![warn(missing_docs)]

use gap_candidate_set::{primes_up_to, GapCandidateSet};
use gap_ordering::{order_gaps, GapOrdering};
use prime_predicate::{is_prime, try_prime_to_tensor_node};
use runtime_state_snapshot::{vector_state, ClaimSource, RuntimeClaim, SnapshotStore};

/// Why a run could not be bound.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PrimeRunError {
    /// The limit yields no primes.
    TooSmall(u64),
    /// A prime does not fit a tensor node.
    TooLarge(u64),
}

/// A recorded run of the prime engine.
#[derive(Debug, Clone)]
pub struct PrimeStateBinding {
    name: String,
    limit: u64,
    primes: Vec<u64>,
    candidates: Vec<(u64, u64, u64)>,
    store: SnapshotStore,
}

const ORDERINGS: [GapOrdering; 4] = [
    GapOrdering::SizeAscending,
    GapOrdering::SizeDescending,
    GapOrdering::PrimeAscending,
    GapOrdering::PrimeDescending,
];

impl PrimeStateBinding {
    /// Enumerate primes up to `limit` and record them.
    pub fn run(name: impl Into<String>, limit: u64) -> Result<Self, PrimeRunError> {
        let primes = primes_up_to(limit);
        if primes.is_empty() {
            return Err(PrimeRunError::TooSmall(limit));
        }
        let nodes = primes
            .iter()
            .map(|&p| try_prime_to_tensor_node(p).ok_or(PrimeRunError::TooLarge(p)))
            .collect::<Result<Vec<_>, _>>()?;
        let candidates = GapCandidateSet::new(primes.clone()).candidates_with_gap(1);
        let mut store = SnapshotStore::new();
        store.capture(format!("primes ≤ {limit}"), &vector_state(nodes));
        Ok(Self {
            name: name.into(),
            limit,
            primes,
            candidates,
            store,
        })
    }

    /// Primes enumerated.
    pub fn primes(&self) -> &[u64] {
        &self.primes
    }

    /// Consecutive-prime gaps `(p, q, q − p)`.
    pub fn candidates(&self) -> &[(u64, u64, u64)] {
        &self.candidates
    }

    /// The limit.
    pub fn limit(&self) -> u64 {
        self.limit
    }

    /// Recorded history.
    pub fn store(&self) -> &SnapshotStore {
        &self.store
    }
}

fn ordered_correctly(sorted: &[(u64, u64, u64)], ordering: GapOrdering) -> bool {
    sorted.windows(2).all(|w| match ordering {
        GapOrdering::SizeAscending => w[0].2 <= w[1].2,
        GapOrdering::SizeDescending => w[0].2 >= w[1].2,
        GapOrdering::PrimeAscending => w[0].0 <= w[1].0,
        GapOrdering::PrimeDescending => w[0].0 >= w[1].0,
    })
}

impl ClaimSource for PrimeStateBinding {
    fn source_name(&self) -> &str {
        &self.name
    }

    fn digest(&self) -> u64 {
        self.store.head_digest()
    }

    fn claims(&self) -> Vec<RuntimeClaim> {
        vec![
            RuntimeClaim::new("all_prime", format!("every enumerated value ≤ {} is prime", self.limit)),
            RuntimeClaim::new("gaps_consistent", "each candidate (p, q, g) has g = q − p and q is the next enumerated prime"),
            RuntimeClaim::new("orderings_are_permutations", "every gap ordering returns a correctly sorted permutation of the candidates"),
            RuntimeClaim::new("encoding_faithful", "the recorded tensor encodes exactly the enumerated primes"),
            RuntimeClaim::new("history_intact", "the recorded history verifies against its trace"),
        ]
    }

    fn recheck(&self, id: &str) -> Result<u64, String> {
        match id {
            "all_prime" => match self.primes.iter().find(|&&p| !is_prime(p)) {
                Some(p) => Err(format!("{p} is not prime")),
                None => Ok(self.primes.len() as u64),
            },
            "gaps_consistent" => {
                if self.candidates.len() + 1 != self.primes.len() {
                    return Err("candidate count does not match prime count".into());
                }
                for (i, &(p, q, g)) in self.candidates.iter().enumerate() {
                    if p != self.primes[i] || q != self.primes[i + 1] || g != q - p {
                        return Err(format!("candidate {i}: ({p}, {q}, {g})"));
                    }
                }
                Ok(self.candidates.len() as u64)
            }
            "orderings_are_permutations" => {
                let mut reference = self.candidates.clone();
                reference.sort();
                for ordering in ORDERINGS {
                    let sorted = order_gaps(self.candidates.clone(), ordering);
                    let mut check = sorted.clone();
                    check.sort();
                    if check != reference || !ordered_correctly(&sorted, ordering) {
                        return Err(format!("{ordering:?} is not a sorted permutation"));
                    }
                }
                Ok(ORDERINGS.len() as u64)
            }
            "encoding_faithful" => {
                let s = self.store.latest().ok_or("nothing recorded")?;
                let encoded: Vec<u64> = s.tensor.nodes().iter().map(|n| n.prime_val as u64).collect();
                if encoded != self.primes {
                    return Err("recorded tensor differs from the enumerated primes".into());
                }
                Ok(encoded.len() as u64)
            }
            "history_intact" => self.store.verify().map(|_| self.store.len() as u64).map_err(|e| e.to_string()),
            other => Err(format!("unknown claim `{other}`")),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn run_and_recheck() {
        let b = PrimeStateBinding::run("primes", 1000).unwrap();
        assert_eq!(b.primes().len(), 168);
        assert_eq!(b.candidates().len(), 167);
        for claim in b.claims() {
            assert!(b.recheck(&claim.id).is_ok(), "{}: {:?}", claim.id, b.recheck(&claim.id));
        }
    }

    #[test]
    fn corrupted_runs_are_caught() {
        let mut b = PrimeStateBinding::run("primes", 100).unwrap();
        b.primes[3] = 9;
        assert!(b.recheck("all_prime").unwrap_err().contains('9'));
        assert!(b.recheck("encoding_faithful").is_err());
        let mut b = PrimeStateBinding::run("primes", 100).unwrap();
        b.candidates[2].2 += 1;
        assert!(b.recheck("gaps_consistent").is_err());
    }

    #[test]
    fn limits() {
        assert_eq!(PrimeStateBinding::run("p", 1).unwrap_err(), PrimeRunError::TooSmall(1));
        assert_eq!(PrimeStateBinding::run("p", 2).unwrap().primes(), &[2]);
    }
}
