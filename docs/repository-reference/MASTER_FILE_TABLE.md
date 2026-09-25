# Master File Table

PYTHON: 224 files, 56,550 LOC

CORE (6 files):
- src/core/types.py - Bounded types
- src/core/crypto.py - Cryptography  
- src/core/storage.py - Storage abstraction
- src/core/evidence.py - Provenance
- src/core/protocols.py - Protocols
- src/core/path_jail.py - Security

MODELS (6 files):
- src/models/entities.py - Domain entities
- src/models/checkpoint_manager.py - Persistence
- src/models/state_machines.py - State machines
- src/models/text_output_pipeline.py - Output parsing
- src/models/burt_imma.py - BURT model
- src/models/recursive_memory.py - Memory

AGENTS (3 files):
- src/agents/react.py - ReAct
- src/agents/mcts.py - MCTS
- src/agents/shadow.py - Shadow

ROUTING (8 files):
- src/routing/pipeline.py - Main pipeline
- src/routing/jordan_moe.py - MoE
- src/routing/jacobian.py - Sensitivity
- src/routing/parser.py - Parser
- src/routing/constraints.py - Constraints
- src/routing/sparse.py - Sparse
- src/routing/symbolic.py - Symbolic
- src/routing/dispatch.py - Dispatch

INFERENCE (8 files):
- src/inference/bedrock_backend.py - Bedrock
- src/inference/quantum_moe.py - Quantum
- src/runtime/providers/*.py - 6 providers

TOOLS (12 files):
- src/tools/registry.py - Registry
- src/tools/loader.py - Loader
- src/tools/* - 40+ tool implementations

RUNTIME (11 files):
- src/runtime/sovereign_machine.py - VM
- src/runtime/machine/*.py - 7 machine modules
- src/runtime/sandbox.py - Sandbox
- src/runtime/filesystem.py - File ops
- src/runtime/network.py - Network

CONTINUITY (7 files):
- src/continuity/*.py - 7 state modules

RETRIEVAL (5 files):
- src/retrieval/*.py - RAG pipeline

RESONANCE (7 files):
- src/resonance/*.py - Semantic tensors

ADVANCED (10 files):
- src/entropy/*.py - WORM, entropy
- src/scanner/*.py - Analysis
- src/exgracy/*.py - Automata
- src/hardware/*.py - Synthesis
- src/bridge/*.py - Servers

ENTRY (3 files):
- run.py - Main
- src/cli/main.py - CLI
- src/sovereign.py - Facade

C: 122 files, 28,338 LOC
HASKELL: 27 files, 3,931 LOC
LEAN: 11 files, 2,330 LOC
RUST: 16 files, 2,296 LOC
TYPESCRIPT: 16 files, 2,487 LOC
FORTRAN: 63 files, 1,486 LOC

TOTAL: 479 files, 98,418 LOC

