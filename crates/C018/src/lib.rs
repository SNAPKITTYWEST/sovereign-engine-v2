//! multiplicity_arena_failure_handling
//!
//! Fail-closed arena management. Allocation is checked against a node
//! budget before any memory is requested, and a [`FailClosedArena`] that hits
//! a fault (out-of-bounds access or a capacity request it cannot satisfy)
//! poisons itself: it records a snapshot of its contents in a tamper-evident
//! trace, scrubs and frees its memory, and refuses every later operation.
//!
//! Allocator failure inside the system allocator is not recoverable here:
//! `MultiplicityArena::build_spine` panics on a null allocation. The budget
//! check keeps requests well-formed and bounded so that path is reserved for
//! genuine system out-of-memory.

#![warn(missing_docs)]

use gap_tensor_trace::{GapTensor, TensorShape, TensorTrace};
use multiplicity_arena_core::{GapTensorNode, MultiplicityArena};
use multiplicity_arena_layout::{ArenaLayout, LayoutError};
use std::fmt;

/// Upper bound on arena size, in nodes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ArenaBudget {
    /// Maximum nodes an arena may hold.
    pub max_nodes: usize,
}

/// Failures of a fail-closed arena.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ArenaFailure {
    /// The layout needs more nodes than the budget allows.
    OverBudget {
        /// Nodes requested.
        requested: usize,
        /// Budget.
        limit: usize,
    },
    /// Access outside the arena. Poisons the arena.
    OutOfBounds {
        /// Offending index.
        index: usize,
        /// Arena size.
        len: usize,
    },
    /// A capacity request the arena cannot satisfy. Poisons the arena.
    OutOfMemory {
        /// Nodes needed.
        needed: usize,
        /// Nodes available.
        capacity: usize,
    },
    /// The arena was poisoned by an earlier fault.
    Poisoned {
        /// Reason recorded at the first fault.
        reason: String,
    },
    /// Layout error (e.g. the arena is sealed).
    Layout(LayoutError),
}

impl fmt::Display for ArenaFailure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for ArenaFailure {}

/// Allocate an arena for `layout` if it fits `budget`. Never allocates when
/// the check fails.
pub fn try_allocate(
    layout: &ArenaLayout,
    budget: &ArenaBudget,
) -> Result<MultiplicityArena, ArenaFailure> {
    if layout.total() > budget.max_nodes {
        return Err(ArenaFailure::OverBudget {
            requested: layout.total(),
            limit: budget.max_nodes,
        });
    }
    Ok(layout.allocate())
}

/// An arena that shuts down permanently on its first fault.
pub struct FailClosedArena {
    arena: Option<MultiplicityArena>,
    layout: ArenaLayout,
    poison: Option<String>,
    log: TensorTrace,
}

impl fmt::Debug for FailClosedArena {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("FailClosedArena")
            .field("layout", &self.layout)
            .field("live", &self.arena.is_some())
            .field("poison", &self.poison)
            .field("log_len", &self.log.len())
            .finish()
    }
}

impl FailClosedArena {
    /// Allocate within `budget`.
    pub fn open(layout: ArenaLayout, budget: &ArenaBudget) -> Result<Self, ArenaFailure> {
        let arena = try_allocate(&layout, budget)?;
        Ok(Self {
            arena: Some(arena),
            layout,
            poison: None,
            log: TensorTrace::new(),
        })
    }

    /// The layout.
    pub fn layout(&self) -> &ArenaLayout {
        &self.layout
    }

    /// Has a fault occurred?
    pub fn is_poisoned(&self) -> bool {
        self.poison.is_some()
    }

    /// Reason for the first fault, if any.
    pub fn poison_reason(&self) -> Option<&str> {
        self.poison.as_deref()
    }

    /// Snapshots recorded at faults.
    pub fn failure_log(&self) -> &TensorTrace {
        &self.log
    }

    fn live(&self) -> Result<&MultiplicityArena, ArenaFailure> {
        match (&self.arena, &self.poison) {
            (Some(arena), None) => Ok(arena),
            (_, Some(reason)) => Err(ArenaFailure::Poisoned {
                reason: reason.clone(),
            }),
            (None, None) => Err(ArenaFailure::Poisoned {
                reason: "arena released".into(),
            }),
        }
    }

    /// Read node `index`. Out-of-bounds reads poison the arena.
    pub fn read(&mut self, index: usize) -> Result<GapTensorNode, ArenaFailure> {
        let len = self.live()?.len();
        if index >= len {
            self.poison(format!("read out of bounds: {index} >= {len}"));
            return Err(ArenaFailure::OutOfBounds { index, len });
        }
        // SAFETY: index < len == arena.len().
        Ok(unsafe { self.live()?.get_node(index) })
    }

    /// Write node `index`. Out-of-bounds writes poison the arena; writes to
    /// a sealed arena are refused without poisoning.
    pub fn write(&mut self, index: usize, node: GapTensorNode) -> Result<(), ArenaFailure> {
        let arena = self.live()?;
        let len = arena.len();
        if arena.is_sealed() {
            return Err(ArenaFailure::Layout(LayoutError::Sealed));
        }
        if index >= len {
            self.poison(format!("write out of bounds: {index} >= {len}"));
            return Err(ArenaFailure::OutOfBounds { index, len });
        }
        let arena = self.arena.as_mut().expect("live arena checked above");
        // SAFETY: index < len == arena.len().
        unsafe { arena.set_node(index, node) };
        Ok(())
    }

    /// Declare that the next piece of work needs `needed` nodes. If the arena
    /// cannot hold them, it fails closed instead of proceeding partially.
    pub fn require_capacity(&mut self, needed: usize) -> Result<(), ArenaFailure> {
        let capacity = self.live()?.len();
        if needed > capacity {
            self.poison(format!("out of memory: need {needed} nodes, capacity {capacity}"));
            return Err(ArenaFailure::OutOfMemory { needed, capacity });
        }
        Ok(())
    }

    /// Poison the arena: snapshot it into the failure log, scrub it to Nil
    /// and free it. Only the first reason is kept.
    pub fn poison(&mut self, reason: impl Into<String>) {
        if self.poison.is_some() {
            return;
        }
        let reason = reason.into();
        if let Some(mut arena) = self.arena.take() {
            let nodes: Vec<GapTensorNode> = arena.iter().collect();
            if let Ok(shape) = TensorShape::vector(nodes.len()) {
                if let Ok(snapshot) = GapTensor::from_nodes(shape, nodes) {
                    self.log.record(format!("poison: {reason}"), &snapshot);
                }
            }
            for i in 0..arena.len() {
                // SAFETY: i < arena.len().
                unsafe { arena.set_node(i, GapTensorNode::NIL) };
            }
            arena.destroy();
        }
        self.poison = Some(reason);
    }

    /// Take the arena back out, if no fault occurred.
    pub fn into_arena(mut self) -> Result<MultiplicityArena, ArenaFailure> {
        self.live()?;
        Ok(self.arena.take().expect("live arena checked above"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn layout() -> ArenaLayout {
        ArenaLayout::new(1, 2, 1, 0).unwrap()
    }

    #[test]
    fn budget_is_checked_before_allocation() {
        assert_eq!(
            try_allocate(&layout(), &ArenaBudget { max_nodes: 3 }).err(),
            Some(ArenaFailure::OverBudget { requested: 4, limit: 3 })
        );
        assert_eq!(try_allocate(&layout(), &ArenaBudget { max_nodes: 4 }).unwrap().len(), 4);
    }

    #[test]
    fn normal_operation() {
        let mut a = FailClosedArena::open(layout(), &ArenaBudget { max_nodes: 16 }).unwrap();
        a.write(2, GapTensorNode::new(7, 1, 1.0)).unwrap();
        assert_eq!(a.read(2).unwrap().prime_val, 7);
        assert!(a.require_capacity(4).is_ok());
        assert!(!a.is_poisoned());
        assert_eq!(a.into_arena().unwrap().len(), 4);
    }

    #[test]
    fn out_of_bounds_fails_closed() {
        let mut a = FailClosedArena::open(layout(), &ArenaBudget { max_nodes: 16 }).unwrap();
        a.write(1, GapTensorNode::new(3, 2, 1.0)).unwrap();
        assert_eq!(a.write(9, GapTensorNode::NIL), Err(ArenaFailure::OutOfBounds { index: 9, len: 4 }));
        assert!(a.is_poisoned());
        assert!(matches!(a.read(1), Err(ArenaFailure::Poisoned { .. })));
        assert!(matches!(a.write(1, GapTensorNode::NIL), Err(ArenaFailure::Poisoned { .. })));

        let log = a.failure_log();
        assert_eq!(log.len(), 1);
        assert!(log.verify().is_ok());
        assert_eq!(log.replay(0).unwrap().nodes()[1].prime_val, 3);
        assert!(a.into_arena().is_err());
    }

    #[test]
    fn capacity_shortfall_fails_closed() {
        let mut a = FailClosedArena::open(layout(), &ArenaBudget { max_nodes: 16 }).unwrap();
        assert_eq!(
            a.require_capacity(5),
            Err(ArenaFailure::OutOfMemory { needed: 5, capacity: 4 })
        );
        assert_eq!(a.poison_reason(), Some("out of memory: need 5 nodes, capacity 4"));
        a.poison("second fault");
        assert_eq!(a.poison_reason(), Some("out of memory: need 5 nodes, capacity 4"));
        assert_eq!(a.failure_log().len(), 1);
    }

    #[test]
    fn sealed_writes_are_refused_without_poisoning() {
        let arena = try_allocate(&layout(), &ArenaBudget { max_nodes: 16 }).unwrap();
        let mut a = FailClosedArena {
            arena: Some(arena),
            layout: layout(),
            poison: None,
            log: TensorTrace::new(),
        };
        a.arena.as_mut().unwrap().mark_sealed();
        assert_eq!(a.write(0, GapTensorNode::NIL), Err(ArenaFailure::Layout(LayoutError::Sealed)));
        assert!(!a.is_poisoned());
    }
}
