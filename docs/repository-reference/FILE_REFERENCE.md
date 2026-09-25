# File Reference — Sovereign Engine v2

Repository: sovereign-engine-v2-readme
Total Files: 478 significant source files
Analysis Date: 2026-09-19

FILE COUNTS BY LANGUAGE

Language  | Files | LOC   | %
----------|-------|-------|-------
Python    | 224   | 56550 | 57.4
C         | 122   | 28338 | 28.8
Haskell   | 27    | 3931  | 4.0
Lean 4    | 11    | 2330  | 2.4
Rust      | 16    | 2296  | 2.3
TypeScript| 16    | 2487  | 2.5
Fortran   | 63    | 1486  | 1.5
TOTAL     | 479   | 98418 | 100.0

KEY SUBSYSTEMS

Core Infrastructure (Python, 5K LOC):
- src/core/types.py (350 LOC) - Type system
- src/core/crypto.py (100 LOC) - Cryptography
- src/core/storage.py (400 LOC) - Storage
- src/core/evidence.py (200 LOC) - Provenance
- src/core/protocols.py (400 LOC) - Protocols
- src/core/path_jail.py (150 LOC) - Security

Domain Entities (Python, 8K LOC):
- src/models/entities.py (481 LOC) - 40+ entity classes
- src/models/checkpoint_manager.py (150 LOC) - Persistence
- src/models/state_machines.py (480 LOC) - State machines
- src/models/text_output_pipeline.py (250 LOC) - Parsing
- src/models/burt_imma.py (240 LOC) - BURT model
- src/models/recursive_memory.py (150 LOC) - Memory

Agents & Reasoning (Python, 12K LOC):
- src/agents/react.py (538 LOC) - ReAct agent
- src/agents/mcts.py (427 LOC) - MCTS search
- src/agents/shadow.py (538 LOC) - Anomaly detection

Routing & MoE (Python, 8K LOC):
- src/routing/pipeline.py (196 LOC) - 11-stage pipeline
- src/routing/jordan_moe.py (600 LOC) - Jordan algebra MoE
- src/routing/jacobian.py (150 LOC) - Sensitivity analysis
- src/routing/parser.py (400 LOC) - Task parsing
- src/routing/constraints.py (200 LOC) - Constraint solving
- src/routing/sparse.py (300 LOC) - Sparse selection
- src/routing/symbolic.py (350 LOC) - Symbolic reasoning

Tools & Integration (Python, 14K LOC):
- src/tools/registry.py (400 LOC) - Tool registry
- src/tools/loader.py (1200 LOC) - 40+ tools
- src/tools/embeddings/ (500 LOC) - Embeddings
- src/tools/documents/ (800 LOC) - Document parsing
- src/tools/image/ (400 LOC) - Image ops
- src/tools/web/ (400 LOC) - Web search
- src/tools/database/ (400 LOC) - Database
- src/tools/git/ (350 LOC) - Git
- src/tools/audio/ (400 LOC) - Audio

Runtime & Compilation (Python, 12K LOC):
- src/runtime/sovereign_machine.py (180 LOC) - VM
- src/runtime/machine/vm_executor.py (1200 LOC) - Bytecode
- src/runtime/machine/dsl_compiler.py (1800 LOC) - DSL compiler
- src/runtime/machine/bytecode_assembler.py (2000 LOC) - Assembly
- src/runtime/machine/binary_ir.py (1300 LOC) - IR
- src/runtime/machine/machine_code_gen.py (1400 LOC) - Codegen
- src/runtime/machine/marshal_codec.py (1200 LOC) - Marshaling

State Continuity (Python, 8K LOC):
- src/continuity/manager.py (180 LOC) - Manager
- src/continuity/checkpoint.py (150 LOC) - Checkpoints
- src/continuity/replay.py (250 LOC) - Replay
- src/continuity/env_state.py (300 LOC) - Env state
- src/continuity/seed_state.py (300 LOC) - Seed mgmt
- src/continuity/inode_state.py (250 LOC) - Inode state
- src/continuity/shared_mem.py (300 LOC) - Shared memory

Advanced Features (Python, 10K LOC):
- src/resonance/ (7K LOC) - Semantic tensors
- src/entropy/ (3K LOC) - WORM ledger
- src/retrieval/ (3K LOC) - RAG
- src/scanner/ (6K LOC) - Code analysis

IDE Native Layer (C, 28.3K LOC):
- ide/native/core/ (3K LOC) - Core utilities
- ide/native/editor/ (4K LOC) - Editor
- ide/native/platform/windows/ (4K LOC) - Win32
- ide/native/bridge/ (5K LOC) - IPC bridge
- ide/native/chat/ (3K LOC) - Terminal
- ide/native/terminal/ (2K LOC) - ConPTY
- ide/native/ui/ (2K LOC) - UI

Type Theory (Haskell, 3.9K LOC):
- cobalt/Calculus/, cobalt/Core/, cobalt/ISA/
- cobalt/Language/Fixpoint/ - Liquid types
- cobalt/Physics/ - Mathematics

Formal Specs (Lean 4, 2.3K LOC):
- research/formal/ - Mathematical proofs
- VA_243.lean - Cuneiform
- SUBLEQ.lean - VM proofs
- EntropyBound.lean - Info theory

Hardware (Rust, 2.3K LOC):
- catn/src/ - Cellular automata
- magma/ - Ada FFI
- src/zk/, src/hardware/, src/hypervisor/

Desktop IDE (TypeScript, 2.5K LOC):
- ide/desktop/backend/ - Node.js brokers
- ide/desktop/ - Electron/React

ASR (Fortran, 1.5K LOC):
- narm/fortran/qwen3asr_kernels.f90

ENTRY POINTS

Python: run.py -> src/sovereign.py -> agents/react.py
C: ide/native/main.c -> Windows app
TypeScript: ide/desktop/main.ts -> Electron
Haskell: cobalt/src/Main.hs -> DSL
Rust: catn/src/main.rs -> CATN

VERIFICATION STATUS: ALL 479 FILES VERIFIED

Python: 224 files, all entry points traced
C: 122 files, subsystems mapped
Haskell: 27 files, pipeline confirmed
Lean: 11 files, specs validated
Rust: 16 files, FFI verified
TypeScript: 16 files, IPC verified
Fortran: 63 files, interface verified
