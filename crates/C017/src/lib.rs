//! multiplicity_arena_deallocation
//!
//! Region drain and reset with rollback. Draining Nil-fills a region and
//! returns a [`Checkpoint`] of its previous contents; [`rollback`] restores
//! it. A region cannot be drained while any lease on it is outstanding, and
//! [`reset_all`] is all-or-nothing.

#![warn(missing_docs)]

use multiplicity_arena_core::{GapTensorNode, MultiplicityArena};
use multiplicity_arena_layout::{ArenaLayout, LayoutError, Region};
use multiplicity_arena_ownership::OwnershipTracker;
use std::fmt;

/// Saved contents of one region.
#[derive(Debug, Clone, PartialEq)]
pub struct Checkpoint {
    region: Region,
    nodes: Vec<GapTensorNode>,
}

impl Checkpoint {
    /// The region saved.
    pub fn region(&self) -> Region {
        self.region
    }

    /// The saved nodes.
    pub fn nodes(&self) -> &[GapTensorNode] {
        &self.nodes
    }
}

/// Errors from drain, reset and rollback.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DeallocError {
    /// Layout mismatch or sealed arena.
    Layout(LayoutError),
    /// Leases are still active in the region.
    OutstandingLeases {
        /// Region.
        region: Region,
        /// Active leases in it.
        count: usize,
    },
    /// The checkpoint does not fit the region in this layout.
    CheckpointMismatch {
        /// Region.
        region: Region,
        /// Region length.
        expected: usize,
        /// Checkpoint length.
        got: usize,
    },
}

impl fmt::Display for DeallocError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for DeallocError {}

impl From<LayoutError> for DeallocError {
    fn from(e: LayoutError) -> Self {
        DeallocError::Layout(e)
    }
}

/// Save the contents of `region`.
pub fn checkpoint(
    arena: &MultiplicityArena,
    layout: &ArenaLayout,
    region: Region,
) -> Result<Checkpoint, DeallocError> {
    Ok(Checkpoint {
        region,
        nodes: layout.read_region(arena, region)?,
    })
}

fn ensure_no_leases(tracker: &OwnershipTracker, region: Region) -> Result<(), DeallocError> {
    let count = tracker.outstanding_in(region);
    if count > 0 {
        return Err(DeallocError::OutstandingLeases { region, count });
    }
    Ok(())
}

/// Nil-fill `region`, returning a checkpoint of what was there.
pub fn drain_region(
    arena: &mut MultiplicityArena,
    layout: &ArenaLayout,
    region: Region,
    tracker: &OwnershipTracker,
) -> Result<Checkpoint, DeallocError> {
    ensure_no_leases(tracker, region)?;
    layout.check_writable(arena)?;
    let saved = checkpoint(arena, layout, region)?;
    layout.fill_region(arena, region, GapTensorNode::NIL)?;
    Ok(saved)
}

/// Restore a region from a checkpoint.
pub fn rollback(
    arena: &mut MultiplicityArena,
    layout: &ArenaLayout,
    checkpoint: &Checkpoint,
) -> Result<(), DeallocError> {
    let expected = layout.span(checkpoint.region).len;
    if checkpoint.nodes.len() != expected {
        return Err(DeallocError::CheckpointMismatch {
            region: checkpoint.region,
            expected,
            got: checkpoint.nodes.len(),
        });
    }
    layout.write_region(arena, checkpoint.region, &checkpoint.nodes)?;
    Ok(())
}

/// Drain every region. If any region has outstanding leases (or the arena
/// is not writable) nothing is changed.
pub fn reset_all(
    arena: &mut MultiplicityArena,
    layout: &ArenaLayout,
    tracker: &OwnershipTracker,
) -> Result<Vec<Checkpoint>, DeallocError> {
    for region in Region::ALL {
        ensure_no_leases(tracker, region)?;
    }
    layout.check_writable(arena)?;
    Region::ALL
        .into_iter()
        .map(|region| drain_region(arena, layout, region, tracker))
        .collect()
}

/// Run `f` on the arena. If it returns `Err`, every region it changed is
/// restored to its prior contents. The outer `Result` reports failures of
/// the checkpoint / rollback machinery itself.
pub fn with_rollback<T, E, F>(
    arena: &mut MultiplicityArena,
    layout: &ArenaLayout,
    f: F,
) -> Result<Result<T, E>, DeallocError>
where
    F: FnOnce(&mut MultiplicityArena) -> Result<T, E>,
{
    let saved = Region::ALL
        .into_iter()
        .map(|region| checkpoint(arena, layout, region))
        .collect::<Result<Vec<_>, _>>()?;
    let result = f(arena);
    if result.is_err() {
        for cp in &saved {
            if layout.read_region(arena, cp.region)? != cp.nodes {
                rollback(arena, layout, cp)?;
            }
        }
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use multiplicity_arena_ownership::{Access, NodeRange, OwnerId};

    fn setup() -> (ArenaLayout, MultiplicityArena) {
        let l = ArenaLayout::new(1, 3, 2, 1).unwrap();
        let mut arena = l.allocate();
        l.fill_region(&mut arena, Region::Data, GapTensorNode::new(3, 1, 1.0)).unwrap();
        l.fill_region(&mut arena, Region::Stack, GapTensorNode::new(5, 1, 1.0)).unwrap();
        (l, arena)
    }

    #[test]
    fn drain_then_rollback() {
        let (l, mut arena) = setup();
        let t = OwnershipTracker::new();
        let cp = drain_region(&mut arena, &l, Region::Data, &t).unwrap();
        assert!(l.read_region(&arena, Region::Data).unwrap().iter().all(|n| n.is_nil()));
        assert_eq!(l.read_region(&arena, Region::Stack).unwrap()[0].prime_val, 5);
        rollback(&mut arena, &l, &cp).unwrap();
        assert!(l.read_region(&arena, Region::Data).unwrap().iter().all(|n| n.prime_val == 3));
    }

    #[test]
    fn leases_block_drain() {
        let (l, mut arena) = setup();
        let mut t = OwnershipTracker::new();
        let r = NodeRange::new(&l, Region::Data, 0, 1).unwrap();
        let lease = t.acquire(OwnerId(9), r, Access::Shared).unwrap();
        assert_eq!(
            drain_region(&mut arena, &l, Region::Data, &t),
            Err(DeallocError::OutstandingLeases { region: Region::Data, count: 1 })
        );
        assert_eq!(
            reset_all(&mut arena, &l, &t),
            Err(DeallocError::OutstandingLeases { region: Region::Data, count: 1 })
        );
        assert_eq!(l.read_region(&arena, Region::Stack).unwrap()[0].prime_val, 5);
        t.release(lease).unwrap();
        let cps = reset_all(&mut arena, &l, &t).unwrap();
        assert_eq!(cps.len(), 4);
        assert!(arena.iter().all(|n| n.is_nil()));
    }

    #[test]
    fn transactional_update() {
        let (l, mut arena) = setup();
        let failed: Result<Result<(), &str>, _> = with_rollback(&mut arena, &l, |a| {
            l.fill_region(a, Region::Data, GapTensorNode::NIL).unwrap();
            l.fill_region(a, Region::Heap, GapTensorNode::new(13, 1, 1.0)).unwrap();
            Err("abort")
        });
        assert_eq!(failed, Ok(Err("abort")));
        assert!(l.read_region(&arena, Region::Data).unwrap().iter().all(|n| n.prime_val == 3));
        assert!(l.read_region(&arena, Region::Heap).unwrap()[0].is_nil());

        let ok: Result<Result<u8, ()>, _> = with_rollback(&mut arena, &l, |a| {
            l.fill_region(a, Region::Heap, GapTensorNode::new(13, 1, 1.0)).unwrap();
            Ok(7)
        });
        assert_eq!(ok, Ok(Ok(7)));
        assert_eq!(l.read_region(&arena, Region::Heap).unwrap()[0].prime_val, 13);
    }

    #[test]
    fn sealed_arenas_and_bad_checkpoints() {
        let (l, mut arena) = setup();
        let t = OwnershipTracker::new();
        let cp = checkpoint(&arena, &l, Region::Data).unwrap();
        let other = ArenaLayout::new(1, 2, 2, 1).unwrap();
        let mut small = other.allocate();
        assert_eq!(
            rollback(&mut small, &other, &cp),
            Err(DeallocError::CheckpointMismatch { region: Region::Data, expected: 2, got: 3 })
        );
        arena.mark_sealed();
        assert_eq!(
            drain_region(&mut arena, &l, Region::Data, &t),
            Err(DeallocError::Layout(LayoutError::Sealed))
        );
        let r: Result<Result<(), ()>, _> = with_rollback(&mut arena, &l, |_| Err(()));
        assert_eq!(r, Ok(Err(())));
    }
}
