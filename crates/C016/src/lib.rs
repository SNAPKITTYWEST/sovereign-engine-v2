//! multiplicity_arena_ownership
//!
//! Lifetime tracking for arena node ranges. Owners acquire leases on ranges
//! with shared or exclusive access; overlapping leases conflict unless both
//! are shared. Lease handles are never reused, so a stale handle (used after
//! release) is always detected.

#![warn(missing_docs)]

pub use multiplicity_arena_pointers::{ArenaPtr, NodeRange, Region};
use std::collections::BTreeMap;
use std::fmt;

/// Identifies the holder of a lease.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct OwnerId(pub u64);

/// Kind of access a lease grants.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Access {
    /// Read-only; may overlap other shared leases.
    Shared,
    /// Read-write; may not overlap any other lease.
    Exclusive,
}

/// Handle to an active lease.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Lease(u64);

/// What a lease covers.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LeaseInfo {
    /// Holder.
    pub owner: OwnerId,
    /// Covered nodes.
    pub range: NodeRange,
    /// Access kind.
    pub access: Access,
}

/// Errors from lease operations.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OwnershipError {
    /// The requested range overlaps an incompatible active lease.
    Conflict {
        /// Owner of the conflicting lease.
        holder: OwnerId,
        /// The conflicting lease.
        lease: Lease,
    },
    /// The lease was never issued or has been released.
    UnknownLease(Lease),
    /// A write was checked against a shared lease.
    NotExclusive(Lease),
    /// The pointer lies outside the lease's range.
    OutsideLease {
        /// The lease.
        lease: Lease,
        /// The pointer.
        ptr: ArenaPtr,
    },
}

impl fmt::Display for OwnershipError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for OwnershipError {}

/// Registry of active leases.
#[derive(Debug, Clone, Default)]
pub struct OwnershipTracker {
    next: u64,
    active: BTreeMap<Lease, LeaseInfo>,
}

impl OwnershipTracker {
    /// No active leases.
    pub fn new() -> Self {
        Self::default()
    }

    /// Acquire a lease on `range`.
    pub fn acquire(
        &mut self,
        owner: OwnerId,
        range: NodeRange,
        access: Access,
    ) -> Result<Lease, OwnershipError> {
        for (&lease, info) in &self.active {
            let compatible = access == Access::Shared && info.access == Access::Shared;
            if info.range.overlaps(&range) && !compatible {
                return Err(OwnershipError::Conflict {
                    holder: info.owner,
                    lease,
                });
            }
        }
        let lease = Lease(self.next);
        self.next += 1;
        self.active.insert(lease, LeaseInfo { owner, range, access });
        Ok(lease)
    }

    /// Release a lease, returning what it covered.
    pub fn release(&mut self, lease: Lease) -> Result<LeaseInfo, OwnershipError> {
        self.active
            .remove(&lease)
            .ok_or(OwnershipError::UnknownLease(lease))
    }

    /// Release every lease held by `owner`; returns how many were released.
    pub fn release_owner(&mut self, owner: OwnerId) -> usize {
        let before = self.active.len();
        self.active.retain(|_, info| info.owner != owner);
        before - self.active.len()
    }

    /// Details of an active lease.
    pub fn info(&self, lease: Lease) -> Result<&LeaseInfo, OwnershipError> {
        self.active
            .get(&lease)
            .ok_or(OwnershipError::UnknownLease(lease))
    }

    /// Check that `lease` is active and covers `ptr`.
    pub fn check_read(&self, lease: Lease, ptr: ArenaPtr) -> Result<(), OwnershipError> {
        let info = self.info(lease)?;
        if !info.range.contains(ptr) {
            return Err(OwnershipError::OutsideLease { lease, ptr });
        }
        Ok(())
    }

    /// Check that `lease` is active, exclusive and covers `ptr`.
    pub fn check_write(&self, lease: Lease, ptr: ArenaPtr) -> Result<(), OwnershipError> {
        self.check_read(lease, ptr)?;
        if self.info(lease)?.access != Access::Exclusive {
            return Err(OwnershipError::NotExclusive(lease));
        }
        Ok(())
    }

    /// Number of active leases.
    pub fn outstanding(&self) -> usize {
        self.active.len()
    }

    /// Number of active leases in `region`.
    pub fn outstanding_in(&self, region: Region) -> usize {
        self.active
            .values()
            .filter(|info| info.range.region() == region)
            .count()
    }

    /// Active leases held by `owner`.
    pub fn leases_of(&self, owner: OwnerId) -> Vec<Lease> {
        self.active
            .iter()
            .filter(|(_, info)| info.owner == owner)
            .map(|(&lease, _)| lease)
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use multiplicity_arena_pointers::ArenaLayout;

    fn setup() -> (ArenaLayout, NodeRange, NodeRange, NodeRange) {
        let l = ArenaLayout::new(0, 8, 2, 0).unwrap();
        let a = NodeRange::new(&l, Region::Data, 0, 4).unwrap();
        let b = NodeRange::new(&l, Region::Data, 2, 4).unwrap();
        let c = NodeRange::new(&l, Region::Data, 6, 2).unwrap();
        (l, a, b, c)
    }

    #[test]
    fn exclusive_leases_conflict() {
        let (_, a, b, c) = setup();
        let mut t = OwnershipTracker::new();
        let la = t.acquire(OwnerId(1), a, Access::Exclusive).unwrap();
        assert_eq!(
            t.acquire(OwnerId(2), b, Access::Shared),
            Err(OwnershipError::Conflict { holder: OwnerId(1), lease: la })
        );
        assert!(t.acquire(OwnerId(1), b, Access::Exclusive).is_err());
        assert!(t.acquire(OwnerId(2), c, Access::Exclusive).is_ok());
    }

    #[test]
    fn shared_leases_coexist() {
        let (_, a, b, _) = setup();
        let mut t = OwnershipTracker::new();
        t.acquire(OwnerId(1), a, Access::Shared).unwrap();
        t.acquire(OwnerId(2), b, Access::Shared).unwrap();
        assert_eq!(t.outstanding(), 2);
        assert!(t.acquire(OwnerId(3), b, Access::Exclusive).is_err());
    }

    #[test]
    fn stale_handles_are_detected() {
        let (_, a, _, _) = setup();
        let mut t = OwnershipTracker::new();
        let lease = t.acquire(OwnerId(1), a, Access::Exclusive).unwrap();
        t.release(lease).unwrap();
        assert_eq!(t.release(lease), Err(OwnershipError::UnknownLease(lease)));
        let again = t.acquire(OwnerId(1), a, Access::Exclusive).unwrap();
        assert_ne!(again, lease);
    }

    #[test]
    fn access_checks() {
        let (l, a, _, c) = setup();
        let mut t = OwnershipTracker::new();
        let w = t.acquire(OwnerId(1), a, Access::Exclusive).unwrap();
        let r = t.acquire(OwnerId(2), c, Access::Shared).unwrap();
        let inside = ArenaPtr::new(&l, Region::Data, 3).unwrap();
        let in_c = ArenaPtr::new(&l, Region::Data, 7).unwrap();
        assert!(t.check_write(w, inside).is_ok());
        assert_eq!(t.check_write(w, in_c), Err(OwnershipError::OutsideLease { lease: w, ptr: in_c }));
        assert!(t.check_read(r, in_c).is_ok());
        assert_eq!(t.check_write(r, in_c), Err(OwnershipError::NotExclusive(r)));
    }

    #[test]
    fn per_owner_and_region_accounting() {
        let (l, a, _, c) = setup();
        let mut t = OwnershipTracker::new();
        t.acquire(OwnerId(1), a, Access::Exclusive).unwrap();
        t.acquire(OwnerId(1), c, Access::Exclusive).unwrap();
        let s = NodeRange::whole_region(&l, Region::Stack).unwrap();
        t.acquire(OwnerId(2), s, Access::Shared).unwrap();
        assert_eq!(t.outstanding_in(Region::Data), 2);
        assert_eq!(t.outstanding_in(Region::Stack), 1);
        assert_eq!(t.leases_of(OwnerId(1)).len(), 2);
        assert_eq!(t.release_owner(OwnerId(1)), 2);
        assert_eq!(t.outstanding(), 1);
    }
}
