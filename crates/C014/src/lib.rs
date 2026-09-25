//! multiplicity_arena_initialization
//!
//! Arena bootstrap: allocate an arena for a layout, load the initial TEXT and
//! DATA images, and hand out an [`InitializedArena`] with safe, bounds-checked
//! access. TEXT is read-only after bootstrap, and a sealed arena accepts no
//! writes at all.

#![warn(missing_docs)]

use multiplicity_arena_core::{GapTensorNode, MultiplicityArena};
use multiplicity_arena_layout::{ArenaLayout, LayoutError, Region};
use std::fmt;

/// Errors from bootstrap and access.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InitError {
    /// Layout / region error (including an image too large for its region).
    Layout(LayoutError),
    /// Index outside the arena.
    OutOfBounds {
        /// Offending index.
        index: usize,
        /// Arena size.
        len: usize,
    },
    /// Writes to TEXT are not allowed after bootstrap.
    ReadOnlyRegion(Region),
    /// The arena is sealed.
    Sealed,
}

impl fmt::Display for InitError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for InitError {}

impl From<LayoutError> for InitError {
    fn from(e: LayoutError) -> Self {
        match e {
            LayoutError::Sealed => InitError::Sealed,
            other => InitError::Layout(other),
        }
    }
}

/// An arena bootstrapped for a specific layout.
pub struct InitializedArena {
    arena: MultiplicityArena,
    layout: ArenaLayout,
}

impl fmt::Debug for InitializedArena {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("InitializedArena")
            .field("layout", &self.layout)
            .field("len", &self.arena.len())
            .field("sealed", &self.arena.is_sealed())
            .finish()
    }
}

impl InitializedArena {
    /// Allocate and load TEXT and DATA images. Each image fills the start of
    /// its region; the rest of the arena is Nil. Sizes are validated before
    /// any memory is allocated.
    pub fn bootstrap(
        layout: ArenaLayout,
        text: &[GapTensorNode],
        data: &[GapTensorNode],
    ) -> Result<Self, InitError> {
        for (region, image) in [(Region::Text, text), (Region::Data, data)] {
            let capacity = layout.span(region).len;
            if image.len() > capacity {
                return Err(InitError::Layout(LayoutError::RegionOverflow {
                    region,
                    capacity,
                    got: image.len(),
                }));
            }
        }
        let mut arena = layout.allocate();
        layout.write_region(&mut arena, Region::Text, text)?;
        layout.write_region(&mut arena, Region::Data, data)?;
        Ok(Self { arena, layout })
    }

    /// A Nil-filled arena for `layout`.
    pub fn empty(layout: ArenaLayout) -> Self {
        let arena = layout.allocate();
        Self { arena, layout }
    }

    /// The layout.
    pub fn layout(&self) -> &ArenaLayout {
        &self.layout
    }

    /// The underlying arena.
    pub fn arena(&self) -> &MultiplicityArena {
        &self.arena
    }

    /// Mutable access to the underlying arena, for the checked APIs of other
    /// arena crates (which re-validate layout and seal).
    pub fn arena_mut(&mut self) -> &mut MultiplicityArena {
        &mut self.arena
    }

    /// Read node `index`.
    pub fn get(&self, index: usize) -> Result<GapTensorNode, InitError> {
        if index >= self.arena.len() {
            return Err(InitError::OutOfBounds {
                index,
                len: self.arena.len(),
            });
        }
        // SAFETY: index < arena.len().
        Ok(unsafe { self.arena.get_node(index) })
    }

    /// Write node `index`. Refused for TEXT and for sealed arenas.
    pub fn set(&mut self, index: usize, node: GapTensorNode) -> Result<(), InitError> {
        if self.arena.is_sealed() {
            return Err(InitError::Sealed);
        }
        if index >= self.arena.len() {
            return Err(InitError::OutOfBounds {
                index,
                len: self.arena.len(),
            });
        }
        if self.layout.region_of(index) == Some(Region::Text) {
            return Err(InitError::ReadOnlyRegion(Region::Text));
        }
        // SAFETY: index < arena.len().
        unsafe { self.arena.set_node(index, node) };
        Ok(())
    }

    /// Copy out the nodes of `region`.
    pub fn region(&self, region: Region) -> Result<Vec<GapTensorNode>, InitError> {
        Ok(self.layout.read_region(&self.arena, region)?)
    }

    /// Seal the arena (no further writes through any checked API).
    pub fn seal(&mut self) {
        self.arena.mark_sealed();
    }

    /// Is the arena sealed?
    pub fn is_sealed(&self) -> bool {
        self.arena.is_sealed()
    }

    /// Split into the raw arena and its layout.
    pub fn into_parts(self) -> (MultiplicityArena, ArenaLayout) {
        (self.arena, self.layout)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn layout() -> ArenaLayout {
        ArenaLayout::new(2, 3, 1, 1).unwrap()
    }

    #[test]
    fn bootstrap_loads_images() {
        let text = [GapTensorNode::new(2, 1, 1.0)];
        let data = [GapTensorNode::new(3, 2, 0.5), GapTensorNode::new(5, 1, 1.0)];
        let a = InitializedArena::bootstrap(layout(), &text, &data).unwrap();
        assert_eq!(a.region(Region::Text).unwrap(), vec![text[0], GapTensorNode::NIL]);
        assert_eq!(a.region(Region::Data).unwrap(), vec![data[0], data[1], GapTensorNode::NIL]);
        assert!(a.region(Region::Heap).unwrap()[0].is_nil());
    }

    #[test]
    fn oversized_image_is_rejected_before_allocation() {
        let data = [GapTensorNode::NIL; 4];
        assert_eq!(
            InitializedArena::bootstrap(layout(), &[], &data).unwrap_err(),
            InitError::Layout(LayoutError::RegionOverflow { region: Region::Data, capacity: 3, got: 4 })
        );
    }

    #[test]
    fn text_is_read_only_and_bounds_are_checked() {
        let mut a = InitializedArena::empty(layout());
        assert_eq!(a.set(0, GapTensorNode::NIL), Err(InitError::ReadOnlyRegion(Region::Text)));
        a.set(2, GapTensorNode::new(7, 1, 1.0)).unwrap();
        assert_eq!(a.get(2).unwrap().prime_val, 7);
        assert_eq!(a.get(7), Err(InitError::OutOfBounds { index: 7, len: 7 }));
        assert_eq!(a.set(7, GapTensorNode::NIL), Err(InitError::OutOfBounds { index: 7, len: 7 }));
    }

    #[test]
    fn sealed_arena_rejects_writes() {
        let mut a = InitializedArena::empty(layout());
        a.seal();
        assert!(a.is_sealed());
        assert_eq!(a.set(3, GapTensorNode::NIL), Err(InitError::Sealed));
        assert!(a.get(3).is_ok());
        let (arena, l) = a.into_parts();
        assert_eq!(arena.len(), l.total());
    }
}
