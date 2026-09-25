//! multiplicity_arena_pointers
//!
//! Region-relative pointers into a multiplicity arena. An [`ArenaPtr`] is a
//! `(region, offset)` pair that can only be created in bounds; arithmetic is
//! checked and never leaves its region. Every read and write re-validates the
//! pointer against the layout and arena it is used with, so a pointer made
//! for one layout cannot silently index past another arena.

#![warn(missing_docs)]

use gap_tensor_ordering::sort_canonical;
pub use multiplicity_arena_core::{GapTensorNode, MultiplicityArena};
pub use multiplicity_arena_layout::{ArenaLayout, LayoutError, Region, RegionSpan};
use std::fmt;
use std::ops::Range;

/// Errors from pointer arithmetic and pointer-based access.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PtrError {
    /// The offset is outside the region.
    OutOfRegion {
        /// Region.
        region: Region,
        /// Offending offset.
        offset: usize,
        /// Region length.
        len: usize,
    },
    /// An absolute index is outside every region.
    OutOfArena {
        /// Offending index.
        index: usize,
        /// Arena size.
        total: usize,
    },
    /// Offset arithmetic overflowed or underflowed.
    Overflow,
    /// The two pointers or ranges are in different regions.
    RegionMismatch {
        /// Left region.
        left: Region,
        /// Right region.
        right: Region,
    },
    /// Ranges must contain at least one node.
    EmptyRange,
    /// A node buffer does not match the range length.
    LengthMismatch {
        /// Range length.
        expected: usize,
        /// Buffer length.
        got: usize,
    },
    /// Arena/layout mismatch or sealed arena.
    Layout(LayoutError),
}

impl fmt::Display for PtrError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for PtrError {}

impl From<LayoutError> for PtrError {
    fn from(e: LayoutError) -> Self {
        PtrError::Layout(e)
    }
}

/// An in-bounds pointer to one node of a region. Ordered by region, then
/// offset.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct ArenaPtr {
    region: Region,
    offset: usize,
}

fn region_len(layout: &ArenaLayout, region: Region) -> usize {
    layout.span(region).len
}

impl ArenaPtr {
    /// Pointer to `offset` within `region`.
    pub fn new(layout: &ArenaLayout, region: Region, offset: usize) -> Result<Self, PtrError> {
        let len = region_len(layout, region);
        if offset >= len {
            return Err(PtrError::OutOfRegion { region, offset, len });
        }
        Ok(Self { region, offset })
    }

    /// Pointer to the node at absolute arena index `index`.
    pub fn from_absolute(layout: &ArenaLayout, index: usize) -> Result<Self, PtrError> {
        let region = layout.region_of(index).ok_or(PtrError::OutOfArena {
            index,
            total: layout.total(),
        })?;
        Ok(Self {
            region,
            offset: index - layout.span(region).start,
        })
    }

    /// The region pointed into.
    pub fn region(&self) -> Region {
        self.region
    }

    /// Offset within the region.
    pub fn offset(&self) -> usize {
        self.offset
    }

    /// Advance by `n` nodes, staying within the region.
    pub fn add(&self, layout: &ArenaLayout, n: usize) -> Result<Self, PtrError> {
        let offset = self.offset.checked_add(n).ok_or(PtrError::Overflow)?;
        Self::new(layout, self.region, offset)
    }

    /// Step back by `n` nodes, staying within the region.
    pub fn sub(&self, layout: &ArenaLayout, n: usize) -> Result<Self, PtrError> {
        let offset = self.offset.checked_sub(n).ok_or(PtrError::Overflow)?;
        Self::new(layout, self.region, offset)
    }

    /// Signed distance from `origin` to `self`; both must share a region.
    pub fn offset_from(&self, origin: ArenaPtr) -> Result<isize, PtrError> {
        if self.region != origin.region {
            return Err(PtrError::RegionMismatch {
                left: self.region,
                right: origin.region,
            });
        }
        let (a, b) = (self.offset as isize, origin.offset as isize);
        a.checked_sub(b).ok_or(PtrError::Overflow)
    }

    /// Absolute arena index, re-validated against `layout`.
    pub fn absolute(&self, layout: &ArenaLayout) -> Result<usize, PtrError> {
        let span = layout.span(self.region);
        if self.offset >= span.len {
            return Err(PtrError::OutOfRegion {
                region: self.region,
                offset: self.offset,
                len: span.len,
            });
        }
        Ok(span.start + self.offset)
    }
}

/// A non-empty run of consecutive nodes within one region.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeRange {
    start: ArenaPtr,
    len: usize,
}

impl NodeRange {
    /// `len` nodes starting at `offset` in `region`.
    pub fn new(
        layout: &ArenaLayout,
        region: Region,
        offset: usize,
        len: usize,
    ) -> Result<Self, PtrError> {
        if len == 0 {
            return Err(PtrError::EmptyRange);
        }
        let end = offset.checked_add(len).ok_or(PtrError::Overflow)?;
        let region_len = region_len(layout, region);
        if end > region_len {
            return Err(PtrError::OutOfRegion {
                region,
                offset: end - 1,
                len: region_len,
            });
        }
        Ok(Self {
            start: ArenaPtr { region, offset },
            len,
        })
    }

    /// The whole of `region`.
    pub fn whole_region(layout: &ArenaLayout, region: Region) -> Result<Self, PtrError> {
        Self::new(layout, region, 0, region_len(layout, region))
    }

    /// First node.
    pub fn start(&self) -> ArenaPtr {
        self.start
    }

    /// Region of the range.
    pub fn region(&self) -> Region {
        self.start.region
    }

    /// Number of nodes.
    pub fn len(&self) -> usize {
        self.len
    }

    /// Always false: ranges are non-empty by construction.
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    /// Offset one past the last node.
    pub fn end_offset(&self) -> usize {
        self.start.offset + self.len
    }

    /// Does the range contain `ptr`?
    pub fn contains(&self, ptr: ArenaPtr) -> bool {
        ptr.region == self.region() && ptr.offset >= self.start.offset && ptr.offset < self.end_offset()
    }

    /// Do the two ranges share at least one node?
    pub fn overlaps(&self, other: &NodeRange) -> bool {
        self.region() == other.region()
            && self.start.offset < other.end_offset()
            && other.start.offset < self.end_offset()
    }

    /// Pointer to the `i`-th node of the range.
    pub fn ptr_at(&self, layout: &ArenaLayout, i: usize) -> Result<ArenaPtr, PtrError> {
        if i >= self.len {
            return Err(PtrError::OutOfRegion {
                region: self.region(),
                offset: self.start.offset.saturating_add(i),
                len: self.end_offset(),
            });
        }
        self.start.add(layout, i)
    }

    /// Absolute arena indices, re-validated against `layout`.
    pub fn absolute_range(&self, layout: &ArenaLayout) -> Result<Range<usize>, PtrError> {
        let span = layout.span(self.region());
        if self.end_offset() > span.len {
            return Err(PtrError::OutOfRegion {
                region: self.region(),
                offset: self.end_offset() - 1,
                len: span.len,
            });
        }
        Ok(span.start + self.start.offset..span.start + self.end_offset())
    }
}

/// Bounds-checked read of one node.
pub fn read(
    arena: &MultiplicityArena,
    layout: &ArenaLayout,
    ptr: ArenaPtr,
) -> Result<GapTensorNode, PtrError> {
    layout.check_arena(arena)?;
    let index = ptr.absolute(layout)?;
    // SAFETY: index < span.end() <= layout.total() == arena.len().
    Ok(unsafe { arena.get_node(index) })
}

/// Bounds-checked write of one node. Refuses sealed arenas.
pub fn write(
    arena: &mut MultiplicityArena,
    layout: &ArenaLayout,
    ptr: ArenaPtr,
    node: GapTensorNode,
) -> Result<(), PtrError> {
    layout.check_writable(arena)?;
    let index = ptr.absolute(layout)?;
    // SAFETY: as in `read`.
    unsafe { arena.set_node(index, node) };
    Ok(())
}

/// Bounds-checked read of a range.
pub fn read_range(
    arena: &MultiplicityArena,
    layout: &ArenaLayout,
    range: NodeRange,
) -> Result<Vec<GapTensorNode>, PtrError> {
    layout.check_arena(arena)?;
    let indices = range.absolute_range(layout)?;
    // SAFETY: indices.end <= span.end() <= arena.len().
    Ok(indices.map(|i| unsafe { arena.get_node(i) }).collect())
}

/// Bounds-checked write of a range; `nodes.len()` must equal the range
/// length. Refuses sealed arenas.
pub fn write_range(
    arena: &mut MultiplicityArena,
    layout: &ArenaLayout,
    range: NodeRange,
    nodes: &[GapTensorNode],
) -> Result<(), PtrError> {
    layout.check_writable(arena)?;
    if nodes.len() != range.len() {
        return Err(PtrError::LengthMismatch {
            expected: range.len(),
            got: nodes.len(),
        });
    }
    let indices = range.absolute_range(layout)?;
    for (i, node) in indices.zip(nodes) {
        // SAFETY: i < span.end() <= arena.len().
        unsafe { arena.set_node(i, *node) };
    }
    Ok(())
}

/// Sort the nodes of `range` into canonical order in place.
pub fn sort_range_canonical(
    arena: &mut MultiplicityArena,
    layout: &ArenaLayout,
    range: NodeRange,
) -> Result<(), PtrError> {
    layout.check_writable(arena)?;
    let mut nodes = read_range(arena, layout, range)?;
    sort_canonical(&mut nodes);
    write_range(arena, layout, range, &nodes)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn layout() -> ArenaLayout {
        ArenaLayout::new(2, 4, 3, 1).unwrap()
    }

    #[test]
    fn construction_is_bounds_checked() {
        let l = layout();
        assert!(ArenaPtr::new(&l, Region::Data, 3).is_ok());
        assert_eq!(
            ArenaPtr::new(&l, Region::Data, 4),
            Err(PtrError::OutOfRegion { region: Region::Data, offset: 4, len: 4 })
        );
        let p = ArenaPtr::from_absolute(&l, 7).unwrap();
        assert_eq!((p.region(), p.offset()), (Region::Stack, 1));
        assert_eq!(
            ArenaPtr::from_absolute(&l, 10),
            Err(PtrError::OutOfArena { index: 10, total: 10 })
        );
    }

    #[test]
    fn arithmetic_stays_in_region() {
        let l = layout();
        let p = ArenaPtr::new(&l, Region::Data, 1).unwrap();
        assert_eq!(p.add(&l, 2).unwrap().offset(), 3);
        assert!(p.add(&l, 3).is_err());
        assert_eq!(p.sub(&l, 1).unwrap().offset(), 0);
        assert_eq!(p.sub(&l, 2), Err(PtrError::Overflow));
        assert_eq!(p.add(&l, usize::MAX), Err(PtrError::Overflow));
        let q = ArenaPtr::new(&l, Region::Data, 3).unwrap();
        assert_eq!(q.offset_from(p), Ok(2));
        assert_eq!(p.offset_from(q), Ok(-2));
        let s = ArenaPtr::new(&l, Region::Stack, 0).unwrap();
        assert!(matches!(s.offset_from(p), Err(PtrError::RegionMismatch { .. })));
        assert_eq!(p.absolute(&l), Ok(3));
    }

    #[test]
    fn ranges() {
        let l = layout();
        let a = NodeRange::new(&l, Region::Data, 0, 2).unwrap();
        let b = NodeRange::new(&l, Region::Data, 1, 3).unwrap();
        let c = NodeRange::new(&l, Region::Data, 2, 2).unwrap();
        assert!(a.overlaps(&b));
        assert!(!a.overlaps(&c));
        assert!(b.contains(ArenaPtr::new(&l, Region::Data, 3).unwrap()));
        assert!(!a.contains(ArenaPtr::new(&l, Region::Data, 2).unwrap()));
        assert_eq!(NodeRange::new(&l, Region::Data, 0, 0), Err(PtrError::EmptyRange));
        assert!(NodeRange::new(&l, Region::Data, 2, 3).is_err());
        assert_eq!(b.absolute_range(&l), Ok(3..6));
        assert_eq!(NodeRange::whole_region(&l, Region::Stack).unwrap().len(), 3);
        assert!(NodeRange::whole_region(&ArenaLayout::new(1, 1, 0, 1).unwrap(), Region::Stack).is_err());
    }

    #[test]
    fn checked_reads_and_writes() {
        let l = layout();
        let mut arena = l.allocate();
        let p = ArenaPtr::new(&l, Region::Heap, 0).unwrap();
        write(&mut arena, &l, p, GapTensorNode::new(13, 1, 1.0)).unwrap();
        assert_eq!(read(&arena, &l, p).unwrap().prime_val, 13);

        let r = NodeRange::whole_region(&l, Region::Data).unwrap();
        let nodes = [
            GapTensorNode::new(7, 1, 1.0),
            GapTensorNode::new(2, 1, 1.0),
            GapTensorNode::new(5, 1, 1.0),
            GapTensorNode::new(3, 1, 1.0),
        ];
        write_range(&mut arena, &l, r, &nodes).unwrap();
        sort_range_canonical(&mut arena, &l, r).unwrap();
        let primes: Vec<u32> = read_range(&arena, &l, r).unwrap().iter().map(|n| n.prime_val).collect();
        assert_eq!(primes, vec![2, 3, 5, 7]);
        assert_eq!(
            write_range(&mut arena, &l, r, &nodes[..2]),
            Err(PtrError::LengthMismatch { expected: 4, got: 2 })
        );
    }

    #[test]
    fn foreign_layouts_and_sealed_arenas_are_rejected() {
        let small = ArenaLayout::new(1, 1, 1, 1).unwrap();
        let big = layout();
        let p = ArenaPtr::new(&big, Region::Data, 3).unwrap();
        let arena = small.allocate();
        assert!(matches!(read(&arena, &small, p), Err(PtrError::OutOfRegion { .. })));
        assert!(matches!(read(&arena, &big, p), Err(PtrError::Layout(LayoutError::ArenaSizeMismatch { .. }))));

        let mut sealed = big.allocate();
        sealed.mark_sealed();
        assert_eq!(
            write(&mut sealed, &big, p, GapTensorNode::NIL),
            Err(PtrError::Layout(LayoutError::Sealed))
        );
    }
}
