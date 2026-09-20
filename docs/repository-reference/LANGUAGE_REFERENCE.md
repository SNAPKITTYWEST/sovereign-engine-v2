# Language Reference — Sovereign Engine v2

**Repository**: `sovereign-engine-v2-readme`  
**Analysis Date**: 2026-09-19  
**Total LOC**: 98,418 across 7 languages

---

## LANGUAGE DISTRIBUTION TABLE

| Language | File Count | LOC | % Total | Runtime Role | Build Role | Primary Subsystem |
|----------|-----------|-----|--------|---|---|---|
| Python | 224 | 56,550 | 57.4% | Agent orchestration, routing, inference | DSL compilation, runtime | Core system |
| C | 122 | 28,338 | 28.8% | IDE native, IPC, graphics | C compilation | IDE native layer |
| Haskell | 27 | 3,931 | 4.0% | DSL compilation | GHC compilation | Cobalt DSL |
| Lean 4 | 11 | 2,330 | 2.4% | Formal verification | Lean verification | Research/formal |
| Rust | 16 | 2,296 | 2.3% | CATN automation, hardware | Cargo build | CATN kernels |
| TypeScript | 16 | 2,487 | 2.5% | Desktop IDE frontend | Node.js build | IDE Electron |
| Fortran | 63 | 1,486 | 1.5% | ASR computation | gfortran build | NARM kernel |

---

## KEY SUBSYSTEM LANGUAGE ASSIGNMENTS

**Core Engine** (Python 56.5K LOC):
- agents/ (12K) — ReAct, MCTS, Shadow reasoning
- routing/ (8K) — Jordan MoE, jacobian routing
- tools/ (14K) — 40+ tool implementations
- runtime/ (12K) — VM, bytecode, DSL compiler
- continuity/ (8K) — State persistence
- inference/ (4K) — Model backends

**IDE Native** (C 28.3K LOC):
- ide/native/core/ (3K) — Arena, events, threading
- ide/native/editor/ (4K) — Buffers, documents
- ide/native/platform/windows/ (4K) — Win32 API
- ide/native/bridge/ (5K) — Python interop
- ide/native/terminal/ (2K) — ConPTY emulation

**Type Theory** (Haskell 3.9K LOC):
- cobalt/Calculus/ (0.8K) — Derivatives, integrals
- cobalt/ISA/ (1K) — Instruction semantics
- cobalt/Language/Fixpoint/ (0.8K) — Liquid types

**Formal Specs** (Lean 2.3K LOC):
- research/formal/VA_243.lean — Cuneiform
- research/formal/subleq/SUBLEQ.lean — VM proofs
- research/formal/sovereign_entropy/ — Entropy bounds

**GPU/Hardware** (Rust 2.3K LOC):
- catn/src/ (0.4K) — Dispatcher
- magma/bindings/rust/ (0.4K) — Ada FFI

**Desktop** (TypeScript 2.5K LOC):
- ide/desktop/backend/ (1K) — IPC brokers
- ide/desktop/ (1.5K) — Electron/React

**ASR** (Fortran 1.5K LOC):
- narm/fortran/qwen3asr_kernels.f90 — ASR kernels

---

## CROSS-LANGUAGE BOUNDARIES

| From | To | Protocol | Data Format | Files |
|------|----|----|---|---|
| Python | C | ctypes FFI | JSON/binary | ctypes_bridge.py |
| Python | Rust | subprocess | JSON/CLI | subprocess call |
| Python | Haskell | subprocess | Prolog/CLI | subprocess call |
| Python | Fortran | ctypes | NumPy arrays | ctypes call |
| Python | CUDA | ctypes/pycuda | GPU tensors | CUDA runtime |
| TypeScript | Python | HTTP/IPC | JSON | main.ts |
| C | Windows | Win32 API | — | platform/ |
| Rust | Ada | FFI | Function ptrs | ada_ffi.rs |

---

## VERIFICATION STATUS

- **Python**: 224 files verified, all entry points traced
- **C**: 122 files categorized, 4 subsystems confirmed
- **Haskell**: 27 files examined, pipeline traced
- **Lean**: 11 specs confirmed (non-executable)
- **Rust**: 16 files scanned, FFI verified
- **TypeScript**: 16 files confirmed, IPC contract verified
- **Fortran**: 63 files identified, kernel interface verified

