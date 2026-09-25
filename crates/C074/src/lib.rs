//! memory_lemmas_library
//!
//! Lemmas about the multiplicity arena (Tier 1): layout partitioning, Nil
//! initialization, bump allocation, reset and rollback, and sealing.
//!
//! [`MemoryLemmasLibrary::standard`] decides every lemma over a finite
//! family of configurations by running the Tier 1 code (evidence grade
//! `Computed`). Soundness of the `unsafe` blocks themselves is stated but left
//! `Open`: it needs a separation-logic proof, not testing.

#![warn(missing_docs)]

use multiplicity_arena_allocation::{AllocError, ArenaLayout, BumpAllocator, Region};
use multiplicity_arena_core::GapTensorNode;
use multiplicity_arena_layout::LayoutError;
use std::collections::BTreeMap;

pub use type_checking_interface::{DecisionCertificate, Evidence, LeanType, ProofTerm, TypeContext, TypeError};

/// Status of a memory lemma
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MemoryLemmaStatus {
    /// Not yet proven
    Open,
    /// Proof attempt in progress
    InProgress,
    /// Proven
    Closed,
    /// Refuted (a decision procedure found a counterexample)
    Failed,
}

/// A memory safety lemma
#[derive(Clone, Debug)]
pub struct MemoryLemma {
    /// Lemma name
    pub name: String,
    /// Formal statement
    pub statement: LeanType,
    /// Proof status
    pub status: MemoryLemmaStatus,
    /// Proof, once closed
    pub proof: Option<ProofTerm>,
    /// Category: layout, allocation, deallocation, sealing or safety
    pub category: String,
    /// Counterexample, or what remains to be done
    pub note: Option<String>,
}

impl MemoryLemma {
    /// Create a new open lemma
    pub fn new(name: String, statement: LeanType, category: String) -> Self {
        Self {
            name,
            statement,
            status: MemoryLemmaStatus::Open,
            proof: None,
            category,
            note: None,
        }
    }

    /// Attach a note
    pub fn with_note(mut self, note: impl Into<String>) -> Self {
        self.note = Some(note.into());
        self
    }

    /// Close with a self-contained proof (checked in an empty context).
    pub fn prove(&mut self, proof: ProofTerm) -> Result<(), TypeError> {
        TypeContext::new().check(&proof, &self.statement)?;
        self.proof = Some(proof);
        self.status = MemoryLemmaStatus::Closed;
        Ok(())
    }

    /// Check if lemma is proven
    pub fn is_proven(&self) -> bool {
        self.status == MemoryLemmaStatus::Closed
    }

    /// Evidence grade, if proven
    pub fn evidence(&self) -> Option<Evidence> {
        self.proof.as_ref().filter(|_| self.is_proven()).map(ProofTerm::evidence)
    }
}

/// Library of memory lemmas
#[derive(Clone, Debug)]
pub struct MemoryLemmasLibrary {
    /// All lemmas indexed by name
    pub lemmas: BTreeMap<String, MemoryLemma>,
    /// Theorems and axioms available to proofs
    pub context: TypeContext,
}

fn fail<T>(msg: String) -> Result<T, String> {
    Err(msg)
}

fn check_layout_partition(t: usize, d: usize, s: usize, h: usize) -> Result<(), String> {
    let l = ArenaLayout::new(t, d, s, h).map_err(|e| format!("{e:?}"))?;
    let mut start = 0;
    for region in Region::ALL {
        let span = l.span(region);
        if span.start != start {
            return fail(format!("{region:?} of ({t},{d},{s},{h}) starts at {}", span.start));
        }
        for i in span.start..span.end() {
            if l.region_of(i) != Some(region) {
                return fail(format!("index {i} of ({t},{d},{s},{h}) not in {region:?}"));
            }
        }
        start = span.end();
    }
    if start != l.total() || l.region_of(l.total()).is_some() {
        return fail(format!("({t},{d},{s},{h}) does not cover exactly [0, total)"));
    }
    Ok(())
}

fn check_bump(capacity: usize, size: usize) -> Result<(), String> {
    let l = ArenaLayout::new(0, 0, 0, capacity).map_err(|e| format!("{e:?}"))?;
    let mut a = BumpAllocator::new(&l, Region::Heap);
    let mut ranges = Vec::new();
    loop {
        let remaining = a.remaining();
        match a.alloc(&l, size) {
            Ok(r) => {
                if remaining < size || r.region() != Region::Heap || r.end_offset() > capacity {
                    return fail(format!("cap {capacity}, size {size}: bad range {r:?}"));
                }
                if ranges.iter().any(|q: &multiplicity_arena_allocation::NodeRange| q.overlaps(&r)) {
                    return fail(format!("cap {capacity}, size {size}: overlapping ranges"));
                }
                ranges.push(r);
            }
            Err(AllocError::OutOfSpace { remaining: rem, .. }) if rem < size && rem == remaining => break,
            Err(e) => return fail(format!("cap {capacity}, size {size}: unexpected {e:?}")),
        }
    }
    if ranges.len() != capacity / size {
        return fail(format!("cap {capacity}, size {size}: {} allocations", ranges.len()));
    }
    Ok(())
}

impl MemoryLemmasLibrary {
    /// Create an empty library
    pub fn new() -> Self {
        Self {
            lemmas: BTreeMap::new(),
            context: TypeContext::new(),
        }
    }

    /// The Tier 1 lemma set, with every finite lemma decided.
    pub fn standard() -> Self {
        fn lemma(name: &str, statement: String, category: &str) -> MemoryLemma {
            MemoryLemma::new(name.into(), LeanType::atom(statement), category.into())
        }
        let mut lib = Self::new();

        lib.add_lemma(
            lemma("unsafe_blocks_sound", "every unsafe block in multiplicity_arena_core and multiplicity_arena_layout is memory-safe under its documented preconditions".into(), "safety")
                .with_note("needs a separation-logic proof; the bounds checks it relies on are decided below"),
        );
        lib.add_lemma(
            lemma("destroy_frees_once", "MultiplicityArena.destroy deallocates exactly once (mem::forget suppresses Drop)".into(), "deallocation")
                .with_note("needs a proof about Drop/forget semantics; not decidable by testing"),
        );

        lib.decide(
            lemma("layout_partitions_arena", "∀ region sizes in {0..3}⁴ not all zero, TEXT, DATA, STACK, HEAP are contiguous, in order, and partition [0, total)".into(), "layout"),
            "enumerate_layouts",
            || {
                let mut cases = 0;
                for t in 0..4 {
                    for d in 0..4 {
                        for s in 0..4 {
                            for h in 0..4 {
                                if t + d + s + h == 0 {
                                    continue;
                                }
                                check_layout_partition(t, d, s, h)?;
                                cases += 1;
                            }
                        }
                    }
                }
                Ok(cases)
            },
        );
        lib.decide(
            lemma("arena_nil_initialized", "∀ 1 ≤ n ≤ 64, every node of a freshly allocated n-node arena is Nil".into(), "allocation"),
            "allocate_and_scan",
            || {
                for n in 1..=64usize {
                    let arena = ArenaLayout::new(0, n, 0, 0).map_err(|e| format!("{e:?}"))?.allocate();
                    if !arena.iter().all(|node| node == GapTensorNode::NIL) {
                        return fail(format!("arena of {n} nodes not Nil"));
                    }
                }
                Ok(64)
            },
        );
        lib.decide(
            lemma("bump_allocations_disjoint", "∀ capacity ≤ 12, size ≤ 4, repeated bump allocation yields ⌊capacity/size⌋ disjoint in-region ranges, then OutOfSpace exactly when remaining < size".into(), "allocation"),
            "exhaust_allocators",
            || {
                let mut cases = 0;
                for capacity in 1..=12 {
                    for size in 1..=4 {
                        check_bump(capacity, size)?;
                        cases += 1;
                    }
                }
                Ok(cases)
            },
        );
        lib.decide(
            lemma("reset_restores_capacity", "∀ capacity ≤ 12, k ≤ capacity: after k unit allocations and reset, remaining = capacity and the next allocation starts at offset 0".into(), "deallocation"),
            "allocate_reset_allocate",
            || {
                let mut cases = 0;
                for capacity in 1..=12usize {
                    let l = ArenaLayout::new(0, 0, capacity, 0).map_err(|e| format!("{e:?}"))?;
                    for k in 0..=capacity {
                        let mut a = BumpAllocator::new(&l, Region::Stack);
                        for _ in 0..k {
                            a.alloc(&l, 1).map_err(|e| format!("{e:?}"))?;
                        }
                        a.reset();
                        let r = a.alloc(&l, 1).map_err(|e| format!("{e:?}"))?;
                        if a.remaining() != capacity - 1 || r.start().offset() != 0 {
                            return fail(format!("capacity {capacity}, k {k}"));
                        }
                        cases += 1;
                    }
                }
                Ok(cases)
            },
        );
        lib.decide(
            lemma("release_to_mark_is_lifo", "∀ capacity ≤ 10, i + j ≤ capacity: releasing to a mark taken after i allocations undoes exactly the j later ones".into(), "deallocation"),
            "mark_and_release",
            || {
                let mut cases = 0;
                for capacity in 1..=10usize {
                    let l = ArenaLayout::new(0, 0, 0, capacity).map_err(|e| format!("{e:?}"))?;
                    for i in 0..=capacity {
                        for j in 0..=capacity - i {
                            let mut a = BumpAllocator::new(&l, Region::Heap);
                            for _ in 0..i {
                                a.alloc(&l, 1).map_err(|e| format!("{e:?}"))?;
                            }
                            let mark = a.mark();
                            for _ in 0..j {
                                a.alloc(&l, 1).map_err(|e| format!("{e:?}"))?;
                            }
                            a.release_to(mark).map_err(|e| format!("{e:?}"))?;
                            if a.used() != i {
                                return fail(format!("capacity {capacity}, i {i}, j {j}: used {}", a.used()));
                            }
                            cases += 1;
                        }
                    }
                }
                Ok(cases)
            },
        );
        lib.decide(
            lemma("sealed_arenas_reject_writes", "∀ region sizes in {1..2}⁴, after sealing, region writes and fills return Sealed and leave the arena unchanged".into(), "sealing"),
            "seal_and_write",
            || {
                let mut cases = 0;
                for t in 1..=2 {
                    for d in 1..=2 {
                        for s in 1..=2 {
                            for h in 1..=2 {
                                let l = ArenaLayout::new(t, d, s, h).map_err(|e| format!("{e:?}"))?;
                                let mut arena = l.allocate();
                                arena.mark_sealed();
                                let node = GapTensorNode::new(7, 1, 1.0);
                                for region in Region::ALL {
                                    if l.write_region(&mut arena, region, &[node]) != Err(LayoutError::Sealed)
                                        || l.fill_region(&mut arena, region, node) != Err(LayoutError::Sealed)
                                    {
                                        return fail(format!("({t},{d},{s},{h}) {region:?} accepted a write"));
                                    }
                                }
                                if !arena.iter().all(|n| n.is_nil()) {
                                    return fail(format!("({t},{d},{s},{h}) sealed arena changed"));
                                }
                                cases += 1;
                            }
                        }
                    }
                }
                Ok(cases)
            },
        );
        lib
    }

    /// Register `lemma` and run its decision procedure.
    pub fn decide(
        &mut self,
        mut lemma: MemoryLemma,
        procedure: &str,
        check: impl FnOnce() -> Result<u64, String>,
    ) {
        match DecisionCertificate::run(lemma.statement.clone(), procedure, check) {
            Ok(cert) => {
                lemma.proof = Some(ProofTerm::Decided(cert));
                lemma.status = MemoryLemmaStatus::Closed;
                self.context.add_theorem(lemma.name.clone(), lemma.statement.clone());
            }
            Err(counterexample) => {
                lemma.status = MemoryLemmaStatus::Failed;
                lemma.note = Some(counterexample);
            }
        }
        self.add_lemma(lemma);
    }

    /// Close lemma `name` with `proof`, checked in this library's context.
    pub fn prove_lemma(&mut self, name: &str, proof: ProofTerm) -> Result<(), TypeError> {
        let lemma = self
            .lemmas
            .get(name)
            .ok_or_else(|| TypeError::UnknownName(name.to_string()))?;
        self.context.check(&proof, &lemma.statement)?;
        let statement = lemma.statement.clone();
        let lemma = self.lemmas.get_mut(name).expect("checked above");
        lemma.proof = Some(proof);
        lemma.status = MemoryLemmaStatus::Closed;
        self.context.add_theorem(name.to_string(), statement);
        Ok(())
    }

    /// Add a lemma
    pub fn add_lemma(&mut self, lemma: MemoryLemma) {
        self.lemmas.insert(lemma.name.clone(), lemma);
    }

    /// Get a lemma by name
    pub fn get_lemma(&self, name: &str) -> Option<&MemoryLemma> {
        self.lemmas.get(name)
    }

    /// Get mutable lemma
    pub fn get_lemma_mut(&mut self, name: &str) -> Option<&mut MemoryLemma> {
        self.lemmas.get_mut(name)
    }

    /// Count proven lemmas
    pub fn count_proven(&self) -> usize {
        self.count_status(MemoryLemmaStatus::Closed)
    }

    /// Count open lemmas
    pub fn count_open(&self) -> usize {
        self.count_status(MemoryLemmaStatus::Open)
    }

    /// Count refuted lemmas
    pub fn count_failed(&self) -> usize {
        self.count_status(MemoryLemmaStatus::Failed)
    }

    fn count_status(&self, status: MemoryLemmaStatus) -> usize {
        self.lemmas.values().filter(|l| l.status == status).count()
    }

    /// Lemmas in a category
    pub fn lemmas_by_category(&self, category: &str) -> Vec<&MemoryLemma> {
        self.lemmas.values().filter(|l| l.category == category).collect()
    }

    /// Allocation lemmas
    pub fn allocation_lemmas(&self) -> Vec<&MemoryLemma> {
        self.lemmas_by_category("allocation")
    }

    /// Deallocation lemmas
    pub fn deallocation_lemmas(&self) -> Vec<&MemoryLemma> {
        self.lemmas_by_category("deallocation")
    }
}

impl Default for MemoryLemmasLibrary {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standard_library_decides_every_bounded_lemma() {
        let lib = MemoryLemmasLibrary::standard();
        let failed: Vec<_> = lib
            .lemmas
            .values()
            .filter(|l| l.status == MemoryLemmaStatus::Failed)
            .map(|l| (l.name.clone(), l.note.clone()))
            .collect();
        assert!(failed.is_empty(), "refuted: {failed:?}");
        assert_eq!(lib.count_proven(), 6);
        assert_eq!(lib.count_open(), 2);
        assert_eq!(lib.allocation_lemmas().len(), 2);
        assert_eq!(lib.deallocation_lemmas().len(), 3);
    }

    #[test]
    fn proofs_are_checked() {
        let mut lib = MemoryLemmasLibrary::standard();
        assert!(lib.prove_lemma("unsafe_blocks_sound", ProofTerm::Trivial).is_err());
        let mut lemma = MemoryLemma::new("t".into(), LeanType::truth(), "misc".into());
        assert!(lemma.prove(ProofTerm::Trivial).is_ok());
        assert!(lemma.is_proven());
    }

    #[test]
    fn decision_failures_are_recorded() {
        let mut lib = MemoryLemmasLibrary::new();
        lib.decide(
            MemoryLemma::new("bogus".into(), LeanType::atom("an allocator of capacity 2 fits 3 nodes"), "allocation".into()),
            "try",
            || {
                let l = ArenaLayout::new(0, 0, 0, 2).map_err(|e| format!("{e:?}"))?;
                BumpAllocator::new(&l, Region::Heap).alloc(&l, 3).map(|_| 1).map_err(|e| format!("{e:?}"))
            },
        );
        assert_eq!(lib.count_failed(), 1);
        assert!(lib.get_lemma("bogus").unwrap().note.as_ref().unwrap().contains("OutOfSpace"));
    }
}
