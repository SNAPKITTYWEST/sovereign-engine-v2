# `multiplicity_arena_ownership` (C016)

Tier 1 — multiplicity arena. *Generated from the crate source; regenerate after API changes.*

Lifetime tracking for arena node ranges. Owners acquire leases on ranges
with shared or exclusive access; overlapping leases conflict unless both
are shared. Lease handles are never reused, so a stale handle (used after
release) is always detected.

## Dependencies

- [C011 `multiplicity_arena_core`](../C011/README.md)
- [C015 `multiplicity_arena_pointers`](../C015/README.md)

## Re-exports

- `multiplicity_arena_pointers::{ArenaPtr, NodeRange, Region}`

## Public API

| Item | Description |
|---|---|
| `struct OwnerId(pub u64)` | Identifies the holder of a lease. |
| `enum Access` | Kind of access a lease grants. |
| `struct Lease(u64)` | Handle to an active lease. |
| `struct LeaseInfo` | What a lease covers. |
| `enum OwnershipError` | Errors from lease operations. |
| `struct OwnershipTracker` | Registry of active leases. |
| `fn OwnershipTracker::new() -> Self` | No active leases. |
| `fn OwnershipTracker::acquire(&mut self, owner: OwnerId, range: NodeRange, access: Access) -> Result<Lease, OwnershipError>` | Acquire a lease on `range`. |
| `fn OwnershipTracker::release(&mut self, lease: Lease) -> Result<LeaseInfo, OwnershipError>` | Release a lease, returning what it covered. |
| `fn OwnershipTracker::release_owner(&mut self, owner: OwnerId) -> usize` | Release every lease held by `owner`; returns how many were released. |
| `fn OwnershipTracker::info(&self, lease: Lease) -> Result<&LeaseInfo, OwnershipError>` | Details of an active lease. |
| `fn OwnershipTracker::check_read(&self, lease: Lease, ptr: ArenaPtr) -> Result<(), OwnershipError>` | Check that `lease` is active and covers `ptr`. |
| `fn OwnershipTracker::check_write(&self, lease: Lease, ptr: ArenaPtr) -> Result<(), OwnershipError>` | Check that `lease` is active, exclusive and covers `ptr`. |
| `fn OwnershipTracker::outstanding(&self) -> usize` | Number of active leases. |
| `fn OwnershipTracker::outstanding_in(&self, region: Region) -> usize` | Number of active leases in `region`. |
| `fn OwnershipTracker::leases_of(&self, owner: OwnerId) -> Vec<Lease>` | Active leases held by `owner`. |

## Tests

`cargo test -p multiplicity_arena_ownership` runs 5 unit tests.
