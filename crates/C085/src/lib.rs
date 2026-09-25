//! recursion_runtime_binding
//!
//! Binds a recursive solver run (Tier 3) to the runtime snapshot store: each
//! push and pop of the solver path goes through a depth manager and the path
//! is recorded as a tensor. Claims (depth within limit, depth equals path
//! length, history intact) are re-checkable.

#![warn(missing_docs)]

use recursion_depth_management::DepthManager;
use recursive_solver_state::RecursiveSolverState;
use runtime_state_snapshot::{vector_state, ClaimSource, GapTensorNode, RuntimeClaim, SnapshotStore};

/// Why a solver step was refused.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RecursionBindingError {
    /// The depth limit was reached.
    DepthLimit(u32),
    /// Pop on an empty path.
    EmptyPath,
}

/// One recorded solver step.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DepthEvent {
    /// Depth reported by the depth manager.
    pub manager_depth: u32,
    /// Depth reported by the solver state.
    pub state_depth: u32,
    /// Length of the solver path.
    pub path_len: usize,
}

/// A recorded solver run.
#[derive(Debug, Clone)]
pub struct RecursionBinding {
    name: String,
    state: RecursiveSolverState,
    depth: DepthManager,
    store: SnapshotStore,
    events: Vec<DepthEvent>,
}

impl RecursionBinding {
    /// A run limited to `max_depth`.
    pub fn new(name: impl Into<String>, max_depth: u32) -> Self {
        let mut binding = Self {
            name: name.into(),
            state: RecursiveSolverState::new(),
            depth: DepthManager::with_max_depth(max_depth),
            store: SnapshotStore::new(),
            events: Vec::new(),
        };
        binding.record("start");
        binding
    }

    fn path_nodes(&self) -> Vec<GapTensorNode> {
        let mut state = self.state.clone();
        let mut nodes = Vec::new();
        while let Some((_, _, node)) = state.pop_state() {
            nodes.push(node);
        }
        nodes.reverse();
        nodes
    }

    fn record(&mut self, label: &str) {
        self.events.push(DepthEvent {
            manager_depth: self.depth.current_depth(),
            state_depth: self.state.depth(),
            path_len: self.state.path_depth(),
        });
        let path = vector_state(self.path_nodes());
        self.store.capture(label.to_string(), &path);
    }

    /// Descend one level with `node`.
    pub fn push(&mut self, node: GapTensorNode) -> Result<u32, RecursionBindingError> {
        let depth = self
            .depth
            .increase_depth()
            .ok_or(RecursionBindingError::DepthLimit(self.depth.max_allowed_depth()))?;
        self.state.increase_depth();
        self.state.push_state(node);
        self.record("push");
        Ok(depth)
    }

    /// Return one level, yielding its node.
    pub fn pop(&mut self) -> Result<GapTensorNode, RecursionBindingError> {
        let (_, _, node) = self.state.pop_state().ok_or(RecursionBindingError::EmptyPath)?;
        self.state.decrease_depth();
        self.depth.decrease_depth();
        self.record("pop");
        Ok(node)
    }

    /// Recorded steps.
    pub fn events(&self) -> &[DepthEvent] {
        &self.events
    }

    /// Recorded history.
    pub fn store(&self) -> &SnapshotStore {
        &self.store
    }

    /// Current depth.
    pub fn depth(&self) -> u32 {
        self.depth.current_depth()
    }

    /// Solver state for fault-injection tests.
    #[doc(hidden)]
    pub fn state_mut_for_testing(&mut self) -> &mut RecursiveSolverState {
        &mut self.state
    }
}

impl ClaimSource for RecursionBinding {
    fn source_name(&self) -> &str {
        &self.name
    }

    fn digest(&self) -> u64 {
        self.store.head_digest()
    }

    fn claims(&self) -> Vec<RuntimeClaim> {
        vec![
            RuntimeClaim::new("depth_within_limit", format!("every recorded depth is at most {}", self.depth.max_allowed_depth())),
            RuntimeClaim::new("depth_equals_path_length", "at every recorded step the manager depth, solver depth and path length agree"),
            RuntimeClaim::new("history_intact", "the recorded history verifies against its trace"),
        ]
    }

    fn recheck(&self, id: &str) -> Result<u64, String> {
        match id {
            "depth_within_limit" => {
                let max = self.depth.max_allowed_depth();
                match self.events.iter().position(|e| e.manager_depth > max || e.state_depth > max) {
                    Some(i) => Err(format!("step {i} exceeds depth {max}")),
                    None => Ok(self.events.len() as u64),
                }
            }
            "depth_equals_path_length" => {
                for (i, e) in self.events.iter().enumerate() {
                    if e.manager_depth != e.state_depth || e.path_len != e.state_depth as usize {
                        return Err(format!("step {i}: {e:?}"));
                    }
                }
                let now = self.state.path_depth();
                if now != self.state.depth() as usize {
                    return Err(format!("current path length {now} ≠ depth {}", self.state.depth()));
                }
                Ok(self.events.len() as u64)
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
    fn push_pop_within_limit() {
        let mut b = RecursionBinding::new("solver", 3);
        for p in [2, 3, 5] {
            b.push(GapTensorNode::new(p, 1, 1.0)).unwrap();
        }
        assert_eq!(b.push(GapTensorNode::new(7, 1, 1.0)), Err(RecursionBindingError::DepthLimit(3)));
        assert_eq!(b.pop().unwrap().prime_val, 5);
        assert_eq!(b.depth(), 2);
        assert_eq!(b.store().latest().unwrap().tensor.nodes().len(), 2);
        for claim in b.claims() {
            assert!(b.recheck(&claim.id).is_ok(), "{}: {:?}", claim.id, b.recheck(&claim.id));
        }
    }

    #[test]
    fn empty_pop_and_desync_are_caught() {
        let mut b = RecursionBinding::new("solver", 5);
        assert_eq!(b.pop(), Err(RecursionBindingError::EmptyPath));
        b.push(GapTensorNode::new(2, 1, 1.0)).unwrap();
        b.state_mut_for_testing().increase_depth();
        assert!(b.recheck("depth_equals_path_length").is_err());
    }
}
