//! multiplicity_arena_layout
//!
//! Partition of a multiplicity arena into four contiguous regions laid out
//! in order — TEXT, DATA, STACK, HEAP — plus region-level reads and writes
//! that are bounds-checked against the layout.
//!
//! A sealed arena (one that has passed certification) is treated as
//! immutable: every write path here refuses it.

#![warn(missing_docs)]

pub use gap_tensor_core::GapTensorNode;
use gap_tensor_shape::TensorShape;
pub use multiplicity_arena_core::MultiplicityArena;
use std::fmt;

/// One of the four arena regions.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Region {
    /// Program constants; read-only after bootstrap.
    Text,
    /// Tensor data.
    Data,
    /// Recursion / scratch frames.
    Stack,
    /// Dynamic allocations.
    Heap,
}

impl Region {
    /// All regions in layout order.
    pub const ALL: [Region; 4] = [Region::Text, Region::Data, Region::Stack, Region::Heap];

    fn slot(self) -> usize {
        self as usize
    }
}

/// A half-open span `[start, start + len)` of arena node indices.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct RegionSpan {
    /// First node index.
    pub start: usize,
    /// Number of nodes.
    pub len: usize,
}

impl RegionSpan {
    /// One past the last node index.
    pub fn end(&self) -> usize {
        self.start + self.len
    }

    /// Does the span contain `index`?
    pub fn contains(&self, index: usize) -> bool {
        index >= self.start && index < self.end()
    }

    /// Is the span zero-length?
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
}

/// Errors from layout construction and region access.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LayoutError {
    /// All regions are zero-length.
    Empty,
    /// The total node count (or its byte size) overflows.
    Overflow,
    /// The arena was not allocated for this layout.
    ArenaSizeMismatch {
        /// Nodes in the arena.
        arena_len: usize,
        /// Nodes required by the layout.
        layout_total: usize,
    },
    /// More nodes were supplied than the region holds.
    RegionOverflow {
        /// Target region.
        region: Region,
        /// Region capacity.
        capacity: usize,
        /// Nodes supplied.
        got: usize,
    },
    /// The arena is sealed and cannot be modified.
    Sealed,
}

impl fmt::Display for LayoutError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for LayoutError {}

/// Region partition of an arena.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ArenaLayout {
    spans: [RegionSpan; 4],
    total: usize,
}

impl ArenaLayout {
    /// Lay out the four regions contiguously. Individual regions may be
    /// empty, but not all of them.
    pub fn new(text: usize, data: usize, stack: usize, heap: usize) -> Result<Self, LayoutError> {
        let mut spans = [RegionSpan { start: 0, len: 0 }; 4];
        let mut cursor = 0usize;
        for (slot, &len) in [text, data, stack, heap].iter().enumerate() {
            spans[slot] = RegionSpan { start: cursor, len };
            cursor = cursor.checked_add(len).ok_or(LayoutError::Overflow)?;
        }
        if cursor == 0 {
            return Err(LayoutError::Empty);
        }
        std::alloc::Layout::array::<GapTensorNode>(cursor).map_err(|_| LayoutError::Overflow)?;
        Ok(Self {
            spans,
            total: cursor,
        })
    }

    /// A layout whose DATA region holds exactly one tensor of `shape`.
    pub fn for_tensor(
        shape: &TensorShape,
        text: usize,
        stack: usize,
        heap: usize,
    ) -> Result<Self, LayoutError> {
        Self::new(text, shape.len(), stack, heap)
    }

    /// The span of `region`.
    pub fn span(&self, region: Region) -> RegionSpan {
        self.spans[region.slot()]
    }

    /// Total nodes across all regions.
    pub fn total(&self) -> usize {
        self.total
    }

    /// The region containing node `index`, if any.
    pub fn region_of(&self, index: usize) -> Option<Region> {
        Region::ALL
            .into_iter()
            .find(|&r| self.span(r).contains(index))
    }

    /// Allocate a Nil-filled arena sized for this layout.
    ///
    /// Panics only if the system allocator itself fails.
    pub fn allocate(&self) -> MultiplicityArena {
        // SAFETY: `new` guarantees total > 0 and that the array layout for
        // `total` nodes is representable, which is build_spine's contract.
        unsafe { MultiplicityArena::build_spine(self.total) }
    }

    /// Check that `arena` was allocated for this layout.
    pub fn check_arena(&self, arena: &MultiplicityArena) -> Result<(), LayoutError> {
        if arena.len() != self.total {
            return Err(LayoutError::ArenaSizeMismatch {
                arena_len: arena.len(),
                layout_total: self.total,
            });
        }
        Ok(())
    }

    /// Check that `arena` matches this layout and is not sealed.
    pub fn check_writable(&self, arena: &MultiplicityArena) -> Result<(), LayoutError> {
        self.check_arena(arena)?;
        if arena.is_sealed() {
            return Err(LayoutError::Sealed);
        }
        Ok(())
    }

    /// Copy out every node of `region`.
    pub fn read_region(
        &self,
        arena: &MultiplicityArena,
        region: Region,
    ) -> Result<Vec<GapTensorNode>, LayoutError> {
        self.check_arena(arena)?;
        let span = self.span(region);
        // SAFETY: span.end() <= total == arena.len().
        Ok((span.start..span.end())
            .map(|i| unsafe { arena.get_node(i) })
            .collect())
    }

    /// Write `nodes` to the start of `region`; the rest of the region is
    /// left unchanged.
    pub fn write_region(
        &self,
        arena: &mut MultiplicityArena,
        region: Region,
        nodes: &[GapTensorNode],
    ) -> Result<(), LayoutError> {
        self.check_writable(arena)?;
        let span = self.span(region);
        if nodes.len() > span.len {
            return Err(LayoutError::RegionOverflow {
                region,
                capacity: span.len,
                got: nodes.len(),
            });
        }
        for (offset, node) in nodes.iter().enumerate() {
            // SAFETY: span.start + offset < span.end() <= arena.len().
            unsafe { arena.set_node(span.start + offset, *node) };
        }
        Ok(())
    }

    /// Set every node of `region` to `node`.
    pub fn fill_region(
        &self,
        arena: &mut MultiplicityArena,
        region: Region,
        node: GapTensorNode,
    ) -> Result<(), LayoutError> {
        self.check_writable(arena)?;
        let span = self.span(region);
        for i in span.start..span.end() {
            // SAFETY: i < span.end() <= arena.len().
            unsafe { arena.set_node(i, node) };
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn regions_are_contiguous() {
        let l = ArenaLayout::new(2, 3, 4, 5).unwrap();
        assert_eq!(l.span(Region::Text), RegionSpan { start: 0, len: 2 });
        assert_eq!(l.span(Region::Data), RegionSpan { start: 2, len: 3 });
        assert_eq!(l.span(Region::Stack), RegionSpan { start: 5, len: 4 });
        assert_eq!(l.span(Region::Heap), RegionSpan { start: 9, len: 5 });
        assert_eq!(l.total(), 14);
        assert_eq!(l.region_of(0), Some(Region::Text));
        assert_eq!(l.region_of(4), Some(Region::Data));
        assert_eq!(l.region_of(13), Some(Region::Heap));
        assert_eq!(l.region_of(14), None);
    }

    #[test]
    fn empty_regions_and_errors() {
        let l = ArenaLayout::new(0, 4, 0, 1).unwrap();
        assert_eq!(l.region_of(0), Some(Region::Data));
        assert_eq!(l.region_of(4), Some(Region::Heap));
        assert_eq!(ArenaLayout::new(0, 0, 0, 0), Err(LayoutError::Empty));
        assert_eq!(ArenaLayout::new(usize::MAX, 1, 0, 0), Err(LayoutError::Overflow));
        assert_eq!(ArenaLayout::new(usize::MAX / 4, 0, 0, 0), Err(LayoutError::Overflow));
    }

    #[test]
    fn data_region_sized_for_tensor() {
        let shape = TensorShape::matrix(2, 3).unwrap();
        let l = ArenaLayout::for_tensor(&shape, 1, 2, 3).unwrap();
        assert_eq!(l.span(Region::Data).len, 6);
        assert_eq!(l.total(), 12);
    }

    #[test]
    fn region_read_write() {
        let l = ArenaLayout::new(1, 3, 0, 2).unwrap();
        let mut arena = l.allocate();
        let nodes = [GapTensorNode::new(2, 1, 1.0), GapTensorNode::new(3, 1, 1.0)];
        l.write_region(&mut arena, Region::Data, &nodes).unwrap();
        assert_eq!(
            l.read_region(&arena, Region::Data).unwrap(),
            vec![nodes[0], nodes[1], GapTensorNode::NIL]
        );
        assert!(l.read_region(&arena, Region::Text).unwrap()[0].is_nil());
        assert_eq!(
            l.write_region(&mut arena, Region::Heap, &[GapTensorNode::NIL; 3]),
            Err(LayoutError::RegionOverflow { region: Region::Heap, capacity: 2, got: 3 })
        );
        l.fill_region(&mut arena, Region::Data, GapTensorNode::NIL).unwrap();
        assert!(l.read_region(&arena, Region::Data).unwrap().iter().all(|n| n.is_nil()));
    }

    #[test]
    fn mismatched_and_sealed_arenas_are_rejected() {
        let l = ArenaLayout::new(1, 1, 1, 1).unwrap();
        let other = ArenaLayout::new(1, 1, 1, 2).unwrap().allocate();
        assert_eq!(
            l.read_region(&other, Region::Data),
            Err(LayoutError::ArenaSizeMismatch { arena_len: 5, layout_total: 4 })
        );
        let mut arena = l.allocate();
        arena.mark_sealed();
        assert!(l.read_region(&arena, Region::Data).is_ok());
        assert_eq!(
            l.write_region(&mut arena, Region::Data, &[GapTensorNode::NIL]),
            Err(LayoutError::Sealed)
        );
    }
}
