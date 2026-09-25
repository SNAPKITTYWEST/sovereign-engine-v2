//! multiplicity_arena_allocation
//!
//! O(1) bump allocation of node ranges within one arena region. Allocation
//! only moves a cursor; `mark`/`release_to` give stack-discipline rollback
//! and `reset` frees the whole region in O(1).

#![warn(missing_docs)]

pub use multiplicity_arena_core::{GapTensorNode, MultiplicityArena};
pub use multiplicity_arena_layout::{ArenaLayout, Region};
use multiplicity_arena_pointers::write_range;
pub use multiplicity_arena_pointers::{ArenaPtr, NodeRange, PtrError};
use std::fmt;

/// Errors from allocation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AllocError {
    /// Zero-length allocations are not allowed.
    ZeroSized,
    /// Not enough space left in the region.
    OutOfSpace {
        /// Nodes requested.
        requested: usize,
        /// Nodes remaining.
        remaining: usize,
    },
    /// The layout's region size differs from the one this allocator was
    /// created for.
    LayoutMismatch {
        /// Capacity the allocator was created with.
        expected_capacity: usize,
        /// Region length in the supplied layout.
        layout_capacity: usize,
    },
    /// A mark lies beyond the current cursor.
    InvalidMark {
        /// Mark position.
        mark: usize,
        /// Current cursor.
        cursor: usize,
    },
    /// Pointer / arena error.
    Ptr(PtrError),
}

impl fmt::Display for AllocError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for AllocError {}

/// A saved cursor position for [`BumpAllocator::release_to`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct AllocMark(usize);

/// Bump allocator over one region.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BumpAllocator {
    region: Region,
    capacity: usize,
    cursor: usize,
    allocations: u64,
}

impl BumpAllocator {
    /// An empty allocator over `region` of `layout`.
    pub fn new(layout: &ArenaLayout, region: Region) -> Self {
        Self {
            region,
            capacity: layout.span(region).len,
            cursor: 0,
            allocations: 0,
        }
    }

    /// Region served.
    pub fn region(&self) -> Region {
        self.region
    }

    /// Region capacity in nodes.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Nodes handed out since the last reset.
    pub fn used(&self) -> usize {
        self.cursor
    }

    /// Nodes still available.
    pub fn remaining(&self) -> usize {
        self.capacity - self.cursor
    }

    /// Successful allocations over the allocator's lifetime.
    pub fn allocation_count(&self) -> u64 {
        self.allocations
    }

    /// Allocate `len` nodes. O(1); does not touch arena memory.
    pub fn alloc(&mut self, layout: &ArenaLayout, len: usize) -> Result<NodeRange, AllocError> {
        if len == 0 {
            return Err(AllocError::ZeroSized);
        }
        let layout_capacity = layout.span(self.region).len;
        if layout_capacity != self.capacity {
            return Err(AllocError::LayoutMismatch {
                expected_capacity: self.capacity,
                layout_capacity,
            });
        }
        let remaining = self.remaining();
        if len > remaining {
            return Err(AllocError::OutOfSpace {
                requested: len,
                remaining,
            });
        }
        let range = NodeRange::new(layout, self.region, self.cursor, len).map_err(AllocError::Ptr)?;
        self.cursor += len;
        self.allocations += 1;
        Ok(range)
    }

    /// Allocate `len` nodes and Nil-fill them. On failure nothing is
    /// consumed.
    pub fn alloc_zeroed(
        &mut self,
        arena: &mut MultiplicityArena,
        layout: &ArenaLayout,
        len: usize,
    ) -> Result<NodeRange, AllocError> {
        layout
            .check_writable(arena)
            .map_err(|e| AllocError::Ptr(PtrError::Layout(e)))?;
        let saved = (self.cursor, self.allocations);
        let range = self.alloc(layout, len)?;
        if let Err(e) = write_range(arena, layout, range, &vec![GapTensorNode::NIL; len]) {
            (self.cursor, self.allocations) = saved;
            return Err(AllocError::Ptr(e));
        }
        Ok(range)
    }

    /// Current cursor position.
    pub fn mark(&self) -> AllocMark {
        AllocMark(self.cursor)
    }

    /// Free everything allocated after `mark`.
    pub fn release_to(&mut self, mark: AllocMark) -> Result<(), AllocError> {
        if mark.0 > self.cursor {
            return Err(AllocError::InvalidMark {
                mark: mark.0,
                cursor: self.cursor,
            });
        }
        self.cursor = mark.0;
        Ok(())
    }

    /// Free everything. O(1).
    pub fn reset(&mut self) {
        self.cursor = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use multiplicity_arena_pointers::read_range;

    #[test]
    fn bump_allocation_until_full() {
        let l = ArenaLayout::new(0, 0, 0, 5).unwrap();
        let mut a = BumpAllocator::new(&l, Region::Heap);
        let r1 = a.alloc(&l, 2).unwrap();
        let r2 = a.alloc(&l, 3).unwrap();
        assert_eq!((r1.start().offset(), r2.start().offset()), (0, 2));
        assert!(!r1.overlaps(&r2));
        assert_eq!(a.remaining(), 0);
        assert_eq!(a.alloc(&l, 1), Err(AllocError::OutOfSpace { requested: 1, remaining: 0 }));
        assert_eq!(a.alloc(&l, 0), Err(AllocError::ZeroSized));
        assert_eq!(a.allocation_count(), 2);
    }

    #[test]
    fn marks_and_reset() {
        let l = ArenaLayout::new(0, 0, 4, 0).unwrap();
        let mut a = BumpAllocator::new(&l, Region::Stack);
        a.alloc(&l, 1).unwrap();
        let m = a.mark();
        a.alloc(&l, 2).unwrap();
        assert_eq!(a.used(), 3);
        a.release_to(m).unwrap();
        assert_eq!(a.used(), 1);
        assert_eq!(a.release_to(AllocMark(3)), Err(AllocError::InvalidMark { mark: 3, cursor: 1 }));
        a.reset();
        assert_eq!(a.remaining(), 4);
    }

    #[test]
    fn layout_mismatch_is_rejected() {
        let l = ArenaLayout::new(0, 0, 0, 5).unwrap();
        let other = ArenaLayout::new(0, 0, 0, 6).unwrap();
        let mut a = BumpAllocator::new(&l, Region::Heap);
        assert_eq!(
            a.alloc(&other, 1),
            Err(AllocError::LayoutMismatch { expected_capacity: 5, layout_capacity: 6 })
        );
    }

    #[test]
    fn zeroed_allocation_clears_reused_memory() {
        let l = ArenaLayout::new(0, 0, 0, 3).unwrap();
        let mut arena = l.allocate();
        let mut a = BumpAllocator::new(&l, Region::Heap);
        let r = a.alloc(&l, 3).unwrap();
        write_range(&mut arena, &l, r, &[GapTensorNode::new(2, 1, 1.0); 3]).unwrap();
        a.reset();
        let r = a.alloc_zeroed(&mut arena, &l, 2).unwrap();
        assert!(read_range(&arena, &l, r).unwrap().iter().all(|n| n.is_nil()));

        arena.mark_sealed();
        let before = a.used();
        assert!(a.alloc_zeroed(&mut arena, &l, 1).is_err());
        assert_eq!(a.used(), before);
    }
}
