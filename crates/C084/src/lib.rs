//! multiplicity_state_binding
//!
//! Binds a live multiplicity arena (Tier 1) to the runtime snapshot store:
//! the DATA region is recorded after every write and when the arena is
//! sealed. Claims (arena matches its layout, snapshots are faithful, a
//! sealed arena never changes, history intact) are re-checkable.

#![warn(missing_docs)]

use multiplicity_arena_core::{GapTensorNode, MultiplicityArena};
pub use multiplicity_arena_layout::{ArenaLayout, LayoutError, Region};
use runtime_state_snapshot::{tensors_bitwise_equal, vector_state, ClaimSource, GapTensor, RuntimeClaim, SnapshotStore};

/// An arena whose DATA region is recorded.
pub struct ArenaBinding {
    name: String,
    layout: ArenaLayout,
    arena: MultiplicityArena,
    store: SnapshotStore,
    sealed_at: Option<usize>,
}

impl std::fmt::Debug for ArenaBinding {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ArenaBinding")
            .field("name", &self.name)
            .field("layout", &self.layout)
            .field("snapshots", &self.store.len())
            .field("sealed_at", &self.sealed_at)
            .finish()
    }
}

impl ArenaBinding {
    /// Allocate an arena for `layout` and record its (Nil) DATA region.
    /// The DATA region must be non-empty.
    pub fn new(name: impl Into<String>, layout: ArenaLayout) -> Result<Self, LayoutError> {
        if layout.span(Region::Data).is_empty() {
            return Err(LayoutError::Empty);
        }
        let arena = layout.allocate();
        let mut binding = Self {
            name: name.into(),
            layout,
            arena,
            store: SnapshotStore::new(),
            sealed_at: None,
        };
        binding.record("allocated")?;
        Ok(binding)
    }

    /// The DATA region as a tensor.
    pub fn data_state(&self) -> Result<GapTensor, LayoutError> {
        Ok(vector_state(self.layout.read_region(&self.arena, Region::Data)?))
    }

    fn record(&mut self, label: &str) -> Result<(), LayoutError> {
        let state = self.data_state()?;
        self.store.capture(label.to_string(), &state);
        Ok(())
    }

    /// Write the start of the DATA region and record it.
    pub fn write_data(&mut self, nodes: &[GapTensorNode]) -> Result<(), LayoutError> {
        self.layout.write_region(&mut self.arena, Region::Data, nodes)?;
        self.record("write")
    }

    /// Seal the arena and record the sealed state.
    pub fn seal(&mut self) -> Result<(), LayoutError> {
        self.arena.mark_sealed();
        self.sealed_at = Some(self.store.len());
        self.record("sealed")
    }

    /// The layout.
    pub fn layout(&self) -> &ArenaLayout {
        &self.layout
    }

    /// The arena.
    pub fn arena(&self) -> &MultiplicityArena {
        &self.arena
    }

    /// Recorded history.
    pub fn store(&self) -> &SnapshotStore {
        &self.store
    }

    /// Is the arena sealed?
    pub fn is_sealed(&self) -> bool {
        self.arena.is_sealed()
    }

    /// Mutable arena access for fault-injection tests (bypasses recording).
    #[doc(hidden)]
    pub fn arena_mut_for_testing(&mut self) -> &mut MultiplicityArena {
        &mut self.arena
    }
}

impl ClaimSource for ArenaBinding {
    fn source_name(&self) -> &str {
        &self.name
    }

    fn digest(&self) -> u64 {
        self.store.head_digest()
    }

    fn claims(&self) -> Vec<RuntimeClaim> {
        vec![
            RuntimeClaim::new("arena_matches_layout", "the arena holds exactly layout.total() nodes"),
            RuntimeClaim::new("latest_snapshot_faithful", "the latest recorded state equals the current DATA region"),
            RuntimeClaim::new("sealed_state_frozen", "after sealing, every recorded state and the current DATA region equal the sealed state"),
            RuntimeClaim::new("history_intact", "the recorded history verifies against its trace"),
        ]
    }

    fn recheck(&self, id: &str) -> Result<u64, String> {
        let current = self.data_state().map_err(|e| e.to_string())?;
        match id {
            "arena_matches_layout" => {
                if self.arena.len() != self.layout.total() {
                    return Err(format!("{} nodes, layout needs {}", self.arena.len(), self.layout.total()));
                }
                Ok(1)
            }
            "latest_snapshot_faithful" => match self.store.latest() {
                Some(s) if tensors_bitwise_equal(&s.tensor, &current) => Ok(1),
                _ => Err("current DATA region differs from the latest snapshot".into()),
            },
            "sealed_state_frozen" => {
                let Some(at) = self.sealed_at else {
                    return Ok(0);
                };
                let sealed = &self.store.snapshots()[at].tensor;
                for s in &self.store.snapshots()[at..] {
                    if !tensors_bitwise_equal(&s.tensor, sealed) {
                        return Err(format!("step {} changed after sealing", s.step));
                    }
                }
                if !tensors_bitwise_equal(&current, sealed) {
                    return Err("DATA region changed after sealing".into());
                }
                Ok((self.store.len() - at) as u64 + 1)
            }
            "history_intact" => self.store.verify().map(|_| self.store.len() as u64).map_err(|e| e.to_string()),
            other => Err(format!("unknown claim `{other}`")),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn binding() -> ArenaBinding {
        ArenaBinding::new("arena", ArenaLayout::new(1, 3, 1, 1).unwrap()).unwrap()
    }

    #[test]
    fn writes_and_seal_are_recorded() {
        let mut b = binding();
        b.write_data(&[GapTensorNode::new(2, 1, 1.0)]).unwrap();
        b.seal().unwrap();
        assert!(b.write_data(&[GapTensorNode::NIL]).is_err());
        assert_eq!(b.store().len(), 3);
        for claim in b.claims() {
            assert!(b.recheck(&claim.id).is_ok(), "{}: {:?}", claim.id, b.recheck(&claim.id));
        }
    }

    #[test]
    fn unrecorded_changes_are_caught() {
        let mut b = binding();
        b.seal().unwrap();
        let data_start = b.layout().span(Region::Data).start;
        unsafe { b.arena_mut_for_testing().set_node(data_start, GapTensorNode::new(5, 1, 1.0)) };
        assert!(b.recheck("sealed_state_frozen").is_err());
        assert!(b.recheck("latest_snapshot_faithful").is_err());
        assert!(b.recheck("history_intact").is_ok());
    }

    #[test]
    fn empty_data_region_is_refused() {
        assert!(ArenaBinding::new("x", ArenaLayout::new(1, 0, 1, 0).unwrap()).is_err());
    }
}
