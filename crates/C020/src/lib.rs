//! multiplicity_arena_tests_integration
//!
//! End-to-end scenarios across the arena stack (layout, bootstrap,
//! allocation, pointers, ownership, drain/rollback, fail-closed handling).
//! [`run_arena_integration`] returns a per-scenario report so a failure says
//! which scenario broke and why.

#![warn(missing_docs)]

use multiplicity_arena_allocation::{AllocError, BumpAllocator};
use multiplicity_arena_core::GapTensorNode;
use multiplicity_arena_deallocation::{drain_region, rollback, DeallocError};
use multiplicity_arena_failure_handling::{ArenaBudget, ArenaFailure, FailClosedArena};
use multiplicity_arena_initialization::{InitError, InitializedArena};
use multiplicity_arena_layout::{ArenaLayout, Region};
use multiplicity_arena_ownership::{Access, OwnerId, OwnershipTracker};
use multiplicity_arena_pointers::{read_range, write, ArenaPtr, NodeRange, PtrError};

/// Outcome of one scenario.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScenarioResult {
    /// Scenario name.
    pub name: &'static str,
    /// Error description, if the scenario failed.
    pub failure: Option<String>,
}

impl ScenarioResult {
    /// Did the scenario pass?
    pub fn passed(&self) -> bool {
        self.failure.is_none()
    }
}

/// Outcome of all scenarios.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IntegrationReport {
    /// Per-scenario results, in run order.
    pub scenarios: Vec<ScenarioResult>,
}

impl IntegrationReport {
    /// True iff every scenario passed.
    pub fn all_passed(&self) -> bool {
        self.scenarios.iter().all(ScenarioResult::passed)
    }

    /// The failed scenarios.
    pub fn failures(&self) -> Vec<&ScenarioResult> {
        self.scenarios.iter().filter(|s| !s.passed()).collect()
    }
}

type Scenario = fn() -> Result<(), String>;

fn ensure(condition: bool, message: &str) -> Result<(), String> {
    if condition {
        Ok(())
    } else {
        Err(message.to_string())
    }
}

fn layout() -> Result<ArenaLayout, String> {
    ArenaLayout::new(2, 4, 4, 6).map_err(|e| format!("layout: {e:?}"))
}

fn regions_partition_the_arena() -> Result<(), String> {
    let l = layout()?;
    let mut expected_start = 0;
    for region in Region::ALL {
        let span = l.span(region);
        ensure(span.start == expected_start, "regions are not contiguous")?;
        expected_start = span.end();
    }
    ensure(expected_start == l.total(), "regions do not cover the arena")?;
    ensure(
        (0..l.total()).all(|i| l.region_of(i).is_some()),
        "an index belongs to no region",
    )
}

fn bootstrap_loads_text_and_data() -> Result<(), String> {
    let text = [GapTensorNode::new(2, 1, 1.0), GapTensorNode::new(3, 1, 1.0)];
    let data = [GapTensorNode::new(5, 2, 0.5)];
    let a = InitializedArena::bootstrap(layout()?, &text, &data).map_err(|e| format!("{e:?}"))?;
    let got_text = a.region(Region::Text).map_err(|e| format!("{e:?}"))?;
    let got_data = a.region(Region::Data).map_err(|e| format!("{e:?}"))?;
    ensure(got_text == text, "TEXT image not loaded")?;
    ensure(got_data[0] == data[0] && got_data[1..].iter().all(|n| n.is_nil()), "DATA image not loaded")
}

fn allocation_is_bounded() -> Result<(), String> {
    let l = layout()?;
    let mut a = BumpAllocator::new(&l, Region::Heap);
    let first = a.alloc(&l, 4).map_err(|e| format!("{e:?}"))?;
    let second = a.alloc(&l, 2).map_err(|e| format!("{e:?}"))?;
    ensure(!first.overlaps(&second), "allocations overlap")?;
    ensure(
        a.alloc(&l, 1) == Err(AllocError::OutOfSpace { requested: 1, remaining: 0 }),
        "allocation past capacity succeeded",
    )
}

fn pointers_stay_in_bounds() -> Result<(), String> {
    let l = layout()?;
    let p = ArenaPtr::new(&l, Region::Stack, 3).map_err(|e| format!("{e:?}"))?;
    ensure(p.add(&l, 1).is_err(), "pointer escaped its region")?;
    ensure(ArenaPtr::new(&l, Region::Text, 2).is_err(), "out-of-region pointer created")?;
    ensure(
        matches!(ArenaPtr::from_absolute(&l, l.total()), Err(PtrError::OutOfArena { .. })),
        "pointer past the arena created",
    )
}

fn ownership_conflicts_are_detected() -> Result<(), String> {
    let l = layout()?;
    let mut t = OwnershipTracker::new();
    let a = NodeRange::new(&l, Region::Data, 0, 3).map_err(|e| format!("{e:?}"))?;
    let b = NodeRange::new(&l, Region::Data, 2, 2).map_err(|e| format!("{e:?}"))?;
    let lease = t.acquire(OwnerId(1), a, Access::Exclusive).map_err(|e| format!("{e:?}"))?;
    ensure(t.acquire(OwnerId(2), b, Access::Shared).is_err(), "overlapping lease granted")?;
    t.release(lease).map_err(|e| format!("{e:?}"))?;
    ensure(t.release(lease).is_err(), "double release accepted")?;
    ensure(t.acquire(OwnerId(2), b, Access::Shared).is_ok(), "lease refused after release")
}

fn drain_respects_leases_and_rolls_back() -> Result<(), String> {
    let l = layout()?;
    let mut arena = l.allocate();
    l.fill_region(&mut arena, Region::Stack, GapTensorNode::new(7, 1, 1.0))
        .map_err(|e| format!("{e:?}"))?;
    let mut t = OwnershipTracker::new();
    let r = NodeRange::whole_region(&l, Region::Stack).map_err(|e| format!("{e:?}"))?;
    let lease = t.acquire(OwnerId(1), r, Access::Shared).map_err(|e| format!("{e:?}"))?;
    ensure(
        matches!(
            drain_region(&mut arena, &l, Region::Stack, &t),
            Err(DeallocError::OutstandingLeases { .. })
        ),
        "drain ignored an active lease",
    )?;
    t.release(lease).map_err(|e| format!("{e:?}"))?;
    let cp = drain_region(&mut arena, &l, Region::Stack, &t).map_err(|e| format!("{e:?}"))?;
    let drained = read_range(&arena, &l, r).map_err(|e| format!("{e:?}"))?;
    ensure(drained.iter().all(|n| n.is_nil()), "drain left live nodes")?;
    rollback(&mut arena, &l, &cp).map_err(|e| format!("{e:?}"))?;
    let restored = read_range(&arena, &l, r).map_err(|e| format!("{e:?}"))?;
    ensure(restored.iter().all(|n| n.prime_val == 7), "rollback did not restore the region")
}

fn faults_fail_closed() -> Result<(), String> {
    let budget = ArenaBudget { max_nodes: 32 };
    ensure(
        matches!(
            FailClosedArena::open(ArenaLayout::new(0, 40, 0, 0).map_err(|e| format!("{e:?}"))?, &budget),
            Err(ArenaFailure::OverBudget { .. })
        ),
        "over-budget arena allocated",
    )?;
    let mut a = FailClosedArena::open(layout()?, &budget).map_err(|e| format!("{e:?}"))?;
    ensure(a.require_capacity(100).is_err(), "capacity shortfall accepted")?;
    ensure(a.is_poisoned(), "arena not poisoned after fault")?;
    ensure(
        matches!(a.read(0), Err(ArenaFailure::Poisoned { .. })),
        "poisoned arena still readable",
    )?;
    ensure(a.failure_log().verify().is_ok(), "failure log does not verify")
}

fn sealed_arenas_are_immutable() -> Result<(), String> {
    let l = layout()?;
    let mut a = InitializedArena::empty(l.clone());
    a.seal();
    ensure(a.set(3, GapTensorNode::NIL) == Err(InitError::Sealed), "sealed arena accepted a write")?;
    let p = ArenaPtr::new(&l, Region::Data, 0).map_err(|e| format!("{e:?}"))?;
    ensure(
        write(a.arena_mut(), &l, p, GapTensorNode::NIL).is_err(),
        "sealed arena accepted a pointer write",
    )
}

/// Run every scenario.
pub fn run_arena_integration() -> IntegrationReport {
    let scenarios: [(&'static str, Scenario); 8] = [
        ("regions_partition_the_arena", regions_partition_the_arena),
        ("bootstrap_loads_text_and_data", bootstrap_loads_text_and_data),
        ("allocation_is_bounded", allocation_is_bounded),
        ("pointers_stay_in_bounds", pointers_stay_in_bounds),
        ("ownership_conflicts_are_detected", ownership_conflicts_are_detected),
        ("drain_respects_leases_and_rolls_back", drain_respects_leases_and_rolls_back),
        ("faults_fail_closed", faults_fail_closed),
        ("sealed_arenas_are_immutable", sealed_arenas_are_immutable),
    ];
    IntegrationReport {
        scenarios: scenarios
            .iter()
            .map(|&(name, run)| ScenarioResult {
                name,
                failure: run().err(),
            })
            .collect(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_scenario_passes() {
        let report = run_arena_integration();
        assert_eq!(report.scenarios.len(), 8);
        assert!(report.all_passed(), "failed scenarios: {:?}", report.failures());
    }

    #[test]
    fn report_names_failures() {
        let report = IntegrationReport {
            scenarios: vec![
                ScenarioResult { name: "ok", failure: None },
                ScenarioResult { name: "bad", failure: Some("boom".into()) },
            ],
        };
        assert!(!report.all_passed());
        assert_eq!(report.failures()[0].name, "bad");
    }
}
