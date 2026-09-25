//! multiplicity_arena_core
//!
//! The MultiplicityArena data structure and bump allocator state management.
//! This is the primary memory management primitive for the entire system.

#![warn(missing_docs)]

pub use gap_tensor_core::GapTensorNode;
use std::alloc::{alloc, dealloc, Layout};
use std::ptr;

/// The multiplicity arena: a single contiguous block of allocated GapTensorNodes.
///
/// The arena is initialized via `build_spine` and destroyed via `destroy`.
/// It provides O(1) element access and supports recursive algorithms through
/// backtracking and state rollback mechanisms.
pub struct MultiplicityArena {
    /// Pointer to the allocated nodes array.
    pub nodes: *mut GapTensorNode,
    /// Number of nodes in the arena.
    pub num_nodes: usize,
    /// Sealed flag: true if this arena has passed G4 certification.
    sealed: bool,
}

impl MultiplicityArena {
    /// Build a new arena spine. Allocates contiguous memory for `num_nodes` elements.
    ///
    /// # Safety
    /// The caller must ensure `num_nodes > 0` and `< usize::MAX / size_of::<GapTensorNode>()`.
    /// This function will panic if allocation fails.
    pub unsafe fn build_spine(num_nodes: usize) -> Self {
        assert!(num_nodes > 0, "SIGMA-E-EMPTY: zero-length spine");
        let layout = Layout::array::<GapTensorNode>(num_nodes)
            .expect("SIGMA-E-LAYOUT: array layout overflow");
        let ptr = alloc(layout) as *mut GapTensorNode;
        if ptr.is_null() {
            panic!("SIGMA-E-ALLOC: prime materia allocation failed");
        }
        for i in 0..num_nodes {
            ptr.add(i).write(GapTensorNode::NIL);
        }
        Self {
            nodes: ptr,
            num_nodes,
            sealed: false,
        }
    }

    /// Access a node at the given index (0-based).
    ///
    /// # Safety
    /// The caller must ensure `index < self.num_nodes`.
    pub unsafe fn get_node(&self, index: usize) -> GapTensorNode {
        debug_assert!(index < self.num_nodes);
        *self.nodes.add(index)
    }

    /// Set a node at the given index.
    ///
    /// # Safety
    /// The caller must ensure `index < self.num_nodes`.
    pub unsafe fn set_node(&mut self, index: usize, node: GapTensorNode) {
        debug_assert!(index < self.num_nodes);
        *self.nodes.add(index) = node;
    }

    /// Immutably iterate over all nodes in the arena.
    pub fn iter(&self) -> ArenaIter<'_> {
        ArenaIter {
            arena: self,
            index: 0,
        }
    }

    /// Is this arena sealed?
    pub fn is_sealed(&self) -> bool {
        self.sealed
    }

    /// Mark this arena as sealed (passed G4 certification).
    pub fn mark_sealed(&mut self) {
        self.sealed = true;
    }

    /// Get the number of nodes.
    pub fn len(&self) -> usize {
        self.num_nodes
    }

    /// Is the arena empty?
    pub fn is_empty(&self) -> bool {
        self.num_nodes == 0
    }

    /// Destroy the arena and free all memory.
    pub fn destroy(self) {
        if !self.nodes.is_null() && self.num_nodes > 0 {
            unsafe {
                let layout = Layout::array::<GapTensorNode>(self.num_nodes)
                    .expect("SIGMA-E-LAYOUT: destroy overflow");
                dealloc(self.nodes as *mut u8, layout);
            }
        }
        std::mem::forget(self);
    }
}

impl Drop for MultiplicityArena {
    fn drop(&mut self) {
        if !self.nodes.is_null() && self.num_nodes > 0 {
            unsafe {
                let layout = Layout::array::<GapTensorNode>(self.num_nodes)
                    .expect("SIGMA-E-LAYOUT: drop overflow");
                dealloc(self.nodes as *mut u8, layout);
            }
            self.nodes = ptr::null_mut();
        }
    }
}

/// Iterator over arena nodes.
pub struct ArenaIter<'a> {
    arena: &'a MultiplicityArena,
    index: usize,
}

impl<'a> Iterator for ArenaIter<'a> {
    type Item = GapTensorNode;

    fn next(&mut self) -> Option<Self::Item> {
        if self.index < self.arena.num_nodes {
            let node = unsafe { self.arena.get_node(self.index) };
            self.index += 1;
            Some(node)
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_arena_build_and_destroy() {
        unsafe {
            let arena = MultiplicityArena::build_spine(10);
            assert_eq!(arena.len(), 10);
            assert!(!arena.is_empty());
            assert!(!arena.is_sealed());
            arena.destroy();
        }
    }

    #[test]
    fn test_arena_node_access() {
        unsafe {
            let mut arena = MultiplicityArena::build_spine(5);
            let node = GapTensorNode::new(2, 1, 1.5);
            arena.set_node(0, node);
            let read_node = arena.get_node(0);
            assert_eq!(read_node, node);
            arena.destroy();
        }
    }

    #[test]
    fn test_arena_iteration() {
        unsafe {
            let mut arena = MultiplicityArena::build_spine(3);
            arena.set_node(0, GapTensorNode::new(2, 1, 1.0));
            arena.set_node(1, GapTensorNode::new(3, 1, 1.0));
            arena.set_node(2, GapTensorNode::new(5, 1, 1.0));

            let nodes: Vec<_> = arena.iter().collect();
            assert_eq!(nodes.len(), 3);
            assert_eq!(nodes[0].prime_val, 2);
            assert_eq!(nodes[1].prime_val, 3);
            assert_eq!(nodes[2].prime_val, 5);

            arena.destroy();
        }
    }
}
