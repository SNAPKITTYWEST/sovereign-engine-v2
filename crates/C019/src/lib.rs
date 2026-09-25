//! multiplicity_arena_statistics
//!
//! Usage tracking for arenas and bump allocators: occupancy of an arena,
//! utilization of an allocator, and a tracker that records peak usage and
//! allocation successes and failures over time.

#![warn(missing_docs)]

use multiplicity_arena_allocation::{AllocError, ArenaLayout, BumpAllocator, NodeRange, Region};
use multiplicity_arena_core::MultiplicityArena;

/// Contents of an arena.
#[derive(Debug, Clone, PartialEq)]
pub struct ArenaStats {
    /// Total nodes.
    pub total_nodes: usize,
    /// Non-nil nodes.
    pub live_nodes: usize,
    /// Nil nodes.
    pub nil_nodes: usize,
    /// Sum of multiplicities of live nodes.
    pub total_multiplicity: u64,
    /// Sum of resonance of live nodes.
    pub total_resonance: f64,
    /// Whether the arena is sealed.
    pub sealed: bool,
}

impl ArenaStats {
    /// Fraction of nodes that are live.
    pub fn occupancy(&self) -> f64 {
        if self.total_nodes == 0 {
            0.0
        } else {
            self.live_nodes as f64 / self.total_nodes as f64
        }
    }
}

/// Scan an arena.
pub fn arena_stats(arena: &MultiplicityArena) -> ArenaStats {
    let mut stats = ArenaStats {
        total_nodes: arena.len(),
        live_nodes: 0,
        nil_nodes: 0,
        total_multiplicity: 0,
        total_resonance: 0.0,
        sealed: arena.is_sealed(),
    };
    for node in arena.iter() {
        if node.is_nil() {
            stats.nil_nodes += 1;
        } else {
            stats.live_nodes += 1;
            stats.total_multiplicity += node.multiplicity as u64;
            stats.total_resonance += node.multiplicity as f64 * node.spectral_weight as f64;
        }
    }
    stats
}

/// State of a bump allocator.
#[derive(Debug, Clone, PartialEq)]
pub struct AllocatorStats {
    /// Region served.
    pub region: Region,
    /// Region capacity.
    pub capacity: usize,
    /// Nodes in use.
    pub used: usize,
    /// Nodes free.
    pub remaining: usize,
    /// Successful allocations over the allocator's lifetime.
    pub allocations: u64,
}

impl AllocatorStats {
    /// Fraction of capacity in use.
    pub fn utilization(&self) -> f64 {
        if self.capacity == 0 {
            0.0
        } else {
            self.used as f64 / self.capacity as f64
        }
    }
}

/// Snapshot an allocator.
pub fn allocator_stats(allocator: &BumpAllocator) -> AllocatorStats {
    AllocatorStats {
        region: allocator.region(),
        capacity: allocator.capacity(),
        used: allocator.used(),
        remaining: allocator.remaining(),
        allocations: allocator.allocation_count(),
    }
}

/// Records allocation outcomes and peak usage.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct UsageTracker {
    peak_used: usize,
    successes: u64,
    failures: u64,
    nodes_allocated: u64,
}

impl UsageTracker {
    /// Nothing recorded.
    pub fn new() -> Self {
        Self::default()
    }

    /// Allocate through `allocator`, recording the outcome.
    pub fn alloc(
        &mut self,
        allocator: &mut BumpAllocator,
        layout: &ArenaLayout,
        len: usize,
    ) -> Result<NodeRange, AllocError> {
        let result = allocator.alloc(layout, len);
        match &result {
            Ok(range) => {
                self.successes += 1;
                self.nodes_allocated += range.len() as u64;
            }
            Err(_) => self.failures += 1,
        }
        self.observe(allocator);
        result
    }

    /// Update peak usage from the allocator's current state.
    pub fn observe(&mut self, allocator: &BumpAllocator) {
        self.peak_used = self.peak_used.max(allocator.used());
    }

    /// Highest `used` value observed.
    pub fn peak_used(&self) -> usize {
        self.peak_used
    }

    /// Successful allocations recorded.
    pub fn successes(&self) -> u64 {
        self.successes
    }

    /// Failed allocations recorded.
    pub fn failures(&self) -> u64 {
        self.failures
    }

    /// Nodes handed out by recorded allocations.
    pub fn nodes_allocated(&self) -> u64 {
        self.nodes_allocated
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use multiplicity_arena_core::GapTensorNode;

    #[test]
    fn arena_contents() {
        let l = ArenaLayout::new(0, 4, 0, 0).unwrap();
        let mut arena = l.allocate();
        l.write_region(
            &mut arena,
            Region::Data,
            &[GapTensorNode::new(2, 2, 1.5), GapTensorNode::new(3, 1, 1.0)],
        )
        .unwrap();
        let s = arena_stats(&arena);
        assert_eq!((s.total_nodes, s.live_nodes, s.nil_nodes), (4, 2, 2));
        assert_eq!(s.total_multiplicity, 3);
        assert!((s.total_resonance - 4.0).abs() < 1e-9);
        assert!((s.occupancy() - 0.5).abs() < 1e-12);
        assert!(!s.sealed);
    }

    #[test]
    fn allocator_utilization_and_peak() {
        let l = ArenaLayout::new(0, 0, 0, 10).unwrap();
        let mut a = BumpAllocator::new(&l, Region::Heap);
        let mut t = UsageTracker::new();
        t.alloc(&mut a, &l, 4).unwrap();
        let mark = a.mark();
        t.alloc(&mut a, &l, 5).unwrap();
        assert!(t.alloc(&mut a, &l, 2).is_err());
        a.release_to(mark).unwrap();
        t.observe(&a);

        let s = allocator_stats(&a);
        assert_eq!((s.used, s.remaining, s.allocations), (4, 6, 2));
        assert!((s.utilization() - 0.4).abs() < 1e-12);
        assert_eq!(t.peak_used(), 9);
        assert_eq!((t.successes(), t.failures(), t.nodes_allocated()), (2, 1, 9));
    }
}
