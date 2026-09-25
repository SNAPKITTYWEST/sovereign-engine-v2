# SOVEREIGN ENGINE V2 — REPOSITORY MAP

**Created:** 2026-09-19  
**Repository:** https://github.com/SNAPKITTYWEST/sovereign-engine-v2  
**Baseline Commit:** 898dfbe  
**Status:** Multi-language; production beta

---

## REPOSITORY STRUCTURE — COMPLETE DIRECTORY TREE

```
sovereign-engine-v2-readme/
├── ROOT CONFIGURATION FILES
├── src/                           # Python core engine (173 files, 50K+ lines)
├── tests/                         # Python tests and demonstrations
├── docs/                          # User and technical documentation
├── research/                      # Formal methods, papers, routing research
├── training/                      # Swift/SceneKit corpus and agent visualization
├── hf/                            # Hugging Face model packaging
├── native/                        # NASM x86-64 runtime and dispatcher
├── kernels/                       # CUDA, CUDAQ, MLIR, x86, TVM, P4, Rust
├── catn/                          # Tensor network implementation (Rust)
├── cobalt/                        # Haskell compiler package
├── magma/                         # Protocol and runtime kernels
├── narm/                          # Runtime/kernel with Fortran and MLIR
├── ide/                           # Windows C/C++ IDE, Electron UI, WASM
├── runtime/                       # Rust gnostic arithmetic and runtime
├── the-49th-call/                 # Call49 substrate
├── sovereign/                     # Node metadata and release utilities
├── scripts/                       # Execution and automation scripts
├── sov jetbrains/                 # JetBrains IDE plugin sources
└── .git/, .venv/, .gitignore, etc.
```

---

## DETAILED DIRECTORY REFERENCE

### ROOT LEVEL

| File | Purpose | Subsystem | Status |
|------|---------|-----------|--------|
| `README.md` | Main entry point, routing diagram, benchmarks | Documentation | VERIFIED |
| `ARCHITECTURE.md` | High-level architecture, execution paths | Documentation | VERIFIED |
| `pyproject.toml` | Python package metadata, entry points, versions | Build | VERIFIED |
| `requirements.txt` | Python dependencies (77 packages, 9 sections) | Build | VERIFIED |
| `run.py` | Direct runner: tools + routing + ReActAgent + Bedrock | Bootstrap | VERIFIED |
| `LICENSE.tri` | Trinitite license | Legal | VERIFIED |
| `.env.example` | Environment template | Configuration | VERIFIED |
| `.gitignore` | Git exclusions | Build | VERIFIED |

### src/ — PYTHON CORE ENGINE (173 FILES, 50K+ LINES)

**Primary Language:** Python 3.11+  
**Build Backend:** setuptools  
**Entry Point:** `sovereign = "src.cli.main:main"`  
**Core Contract:** Task routing, LLM agent execution, model adaptation, tool orchestration

#### SUBSYSTEM: src/routing/ — ELEVEN-STAGE ROUTING PIPELINE

**Purpose:** Parse task, build symbolic graph, apply algebraic transforms, select sparse experts  
**Primary Classes:** `RoutingPipeline`, `PipelineTrace`, `DispatchResult`, `RoutingNode`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `pipeline.py` | 450+ | Main routing orchestration; Jordan/Jacobian analysis; expert dispatch |
| `symbolic.py` | 305 | AST parsing; symbolic graph construction; constraint extraction |
| `dispatch.py` | 400+ | Async expert callbacks; NAND conflict suppression; trace collection |
| `weights.py` | 250+ | Sparse activation scoring; expert ranking; load distribution |
| `sparse-latency-routing/` | Separate impl | Reference Bash router (not integrated) |

**Dependencies:**
- Internal: `src/core/`, `src/tools/`, `src/engine/`
- External: NumPy, SciPy (Jordan decomposition), asyncio

**Boundary:** Accepts task text + context dict; returns DispatchResult with active expert callbacks and trace.

---

#### SUBSYSTEM: src/agents/ — REACT AND MONTE CARLO TREE SEARCH

**Purpose:** Closed-loop reasoning with tools and LLM feedback  
**Primary Classes:** `ReActAgent`, `ReActConfig`, `MoptimizerAgent`, `ShadowAgent`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `react.py` | 550+ | Core ReAct loop; tool binding; step limit enforcement; chain-of-thought |
| `mcts.py` | 400+ | Monte Carlo tree search for exploration; node selection; UCB scoring |
| `shadow.py` | 250+ | Parallel agent runner; hypothesis testing; control/treatment comparison |

**Dependencies:**
- Internal: `src/tools/registry`, `src/core/types`, `src/continuity/`
- External: Async, dataclasses, type hints

**Boundary:** Accepts Task entity; returns reasoning trace, tool calls, final response.

---

#### SUBSYSTEM: src/inference/ — LLM BACKEND ADAPTERS

**Purpose:** Abstract model providers (Bedrock, local, multi-provider fallback)  
**Primary Classes:** `BedrockBackend`, `MultiProvider`, `QuantumMoEModel`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `bedrock_backend.py` | 280+ | AWS Bedrock integration; boto3 credential chain; Haiku/Opus selection |
| `multi.py` | 350+ | Provider selection via task classification; fallback routing; latency tracking |
| `quantum_moe.py` | 300+ | Quantum superposition of expert outputs; entanglement scoring |

**Dependencies:**
- External: boto3 (AWS), httpx (HTTP clients), pydantic (validation)

**Boundary:** Accepts prompt + context; returns generated text or streaming response.

---

#### SUBSYSTEM: src/models/ — MEMORY, CHECKPOINTS, ENTITIES

**Purpose:** Recurrent memory networks, model checkpointing, persistent entity references  
**Primary Classes:** `RecursiveMemoryTwinNetwork`, `CheckpointManager`, `Task`, `Agent`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `recursive_memory.py` | 420+ | GRU cell + memory gate; persistent latent buffer; decay + L2 norm |
| `checkpoint_manager.py` | 480+ | Versioned checkpoints; SHA256 chaining; pruning + quantization helpers |
| `checkpoint_workflow.py` | 350+ | Full checkpoint lifecycle; optional S3 upload; pruning orchestration |
| `entities.py` | 200+ | Task, Agent, Message, ContinuityRecord dataclasses |
| `text_modules.py` | 280+ | TextGenerationHead, OutputLogits, temperature sampling |

**Dependencies:**
- Internal: `src/core/storage`, `src/continuity/`
- External: torch, transformers, boto3 (S3 optional)

**Boundary:** Accepts model weights + training schedule; manages lifecycle, versioning, persistence.

---

#### SUBSYSTEM: src/tools/ — TOOL REGISTRY AND LOADING

**Purpose:** Unified tool discovery, schema validation, authorization policy  
**Primary Classes:** `ToolRegistry`, `ToolDefinition`, `Tool`, `ToolPolicy`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `registry.py` | 484 | Tool catalog; lookup; metadata; policy attachment |
| `loader.py` | 1105 | Discover tools from subdirectories; instantiate; validate schemas |
| `ipc_router.py` | 682 | Async routing to local tools; IPC marshaling; response aggregation |
| `approval.py` | 304 | Authorization gates; policy evaluation; human-in-the-loop callbacks |
| `supervisor.py` | 454 | Tool result inspection; safety filtering; output normalization |
| `lookup.py` | 594 | FTS index; tool search by name/tag; context-aware retrieval |
| `opcode_registry.py` | 253 | Native opcode table; tool→opcode mapping; NAND constraint validation |

**Subdirectories:** `audio/`, `cloud/`, `database/`, `documents/`, `embeddings/`, `git/`, `image/`, `ml/`, `rerank/`, `web/`

**Boundary:** Registry accepts Tool definition; loader discovers *.py files; supervisor validates outputs.

---

#### SUBSYSTEM: src/continuity/ — PERSISTENCE AND STATE TRANSITIONS

**Purpose:** Synchronous state snapshots, session recovery, distributed replay  
**Primary Classes:** `ContinuityManager`, `CheckpointState`, `ReplayContext`, `EnvState`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `manager.py` | 450+ | State machine; transitions; conflict resolution; atomic writes |
| `checkpoint.py` | 320+ | Snapshot creation; version tracking; rollback capability |
| `replay.py` | 380+ | Deterministic replay from checkpoint; state validation; drift detection |
| `seed_state.py` | 260+ | PRNG state capture; entropy pooling; determinism enforcement |
| `env_state.py` | 290+ | Environment variable snapshots; tool state; continuity metadata |
| `inode_state.py` | 240+ | Filesystem state capture; file descriptor tracking; hard link awareness |
| `shared_mem.py` | 210+ | Shared memory segments; cross-process synchronization |

**Boundary:** Accepts TaskContext; produces CheckpointState; enables deterministic recovery.

---

#### SUBSYSTEM: src/core/ — FOUNDATIONS

**Purpose:** Cryptographic identity, evidence ledger, protocol contracts, types  
**Primary Classes:** `WORMLedger`, `SovereignKey`, `Protocol`, `StorageBackend`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `evidence.py` | 420+ | WORM (Write-Once Read-Many) ledger; Ed25519 sealing; chain validation |
| `crypto.py` | 320+ | Ed25519 key generation; Blake3 hashing; HMAC-SHA256 signatures |
| `types.py` | 280+ | Task, Message, Result, TraceNode dataclasses; serialization contracts |
| `protocols.py` | 240+ | Protocol interfaces; Tool, Agent, Provider ABC definitions |
| `storage.py` | 310+ | FileSystemBackend, MemoryBackend, S3Backend abstraction layer |
| `path_jail.py` | 180+ | Sandboxed path resolution; jailbreak prevention; canonical paths |

**Boundary:** Core types are imported everywhere; storage backend is injectable; crypto is deterministic.

---

#### SUBSYSTEM: src/bridge/ — HTTP SERVER AND KEY MANAGEMENT

**Purpose:** HTTP REST interface to routing, chat, tools, and trace inspection  
**Primary Classes:** `HTTPBridge`, `KeyManager`, `RoutingTraceServer`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `http_server.py` | 520+ | FastAPI routes: /chat, /tools, /route, /traces, /keys |
| `key_manager.py` | 380+ | API key storage; rotation; per-user quotas; audit logging |
| `routing_trace.py` | 420+ | Trace export; JSON serialization; visualization endpoints |
| `stdio_server.py` | 240+ | Stdio bridge for CLI integration; message framing |

**Boundary:** Bridge accepts HTTP requests; validates keys; dispatches to routing or agent pipelines.

---

#### SUBSYSTEM: src/runtime/ — MACHINE CODE, SANDBOX, NETWORK

**Purpose:** Bytecode VM, x86 code generation, sandboxed execution, socket binding  
**Primary Classes:** `SovereignMachine`, `StackVM`, `Sandbox`, `NetworkRuntime`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `sovereign_machine.py` | 514 | Bytecode IR; stack frame management; register allocation |
| `machine/bytecode.py` | 350+ | Instruction set; IR translation; control flow lowering |
| `machine/x86_gen.py` | 420+ | x86-64 code generation; syscall bindings; NASM output |
| `sandbox.py` | 519 | Process isolation; seccomp filters; capability restriction |
| `filesystem.py` | 589 | Virtual filesystem; mount points; path interception |
| `network.py` | 573 | Socket sandboxing; network policy; DNS interception |
| `providers/multi.py` | 350+ | Provider selection; fallback logic; latency metrics |

**Boundary:** Accepts bytecode; produces x86 assembly or sandboxed process; handles I/O via interception.

---

#### SUBSYSTEM: src/entropy/ — EVIDENCE AND RANDOMNESS CONTROL

**Purpose:** Deterministic scheduling, entropy pooling, WORM event recording  
**Primary Classes:** `EntropyGovernor`, `ScheduleTracker`, `WORMScheduler`

| Module | Lines | Responsibility |
|--------|-------|-----------------|
| `governor.py` | 380+ | Entropy budget tracking; fairness enforcement; backoff logic |
| `scheduler.py` | 420+ | Deterministic task scheduling; priority queues; latency bounds |
| `worm.py` | 450+ | WORM event insertion; chain verification; cryptographic sealing |
| `constants.py` | 150+ | Entropy thresholds; scheduling parameters; policy constants |

**Boundary:** Governor accepts task requests; reserves entropy; returns schedule slot.

---

#### SUBSYSTEM: src/attention/ — ATTENTION MECHANISMS

**Purpose:** Custom attention kernels for LLM layers  
**Primary Classes:** `RMA`, `SGAM`, `SMA`, `UntypedMultiheadTensorPipeline`, `IntegratedBlock`

| Module | Lines | Responsibility |
|--------|-------|---|
| `rma.py` | 350+ | Recurrent multi-head attention; persistent state; incremental update |
| `sgam.py` | 280+ | Sparse gated attention mask; expert routing within attention |
| `sma.py` | 290+ | Sliding window attention; local receptive field; cache efficiency |
| `umtcpi.py` | 320+ | Untyped multihead tensor pipeline; batched inference; mixed precision |
| `heat_kernel.py` | 240+ | Heat kernel attention; graph Laplacian; spectral decay |
| `integrated_block.py` | 310+ | Full transformer block; integrated attention + FFN + skip |

**Boundary:** Accepts query/key/value tensors; returns attended outputs.

---

#### SUBSYSTEM: src/bert/ — BERT EMBEDDINGS AND ADAPTERS

**Purpose:** Semantic embeddings; BERT fine-tuning; semantic similarity search  
**Primary Classes:** `NomicEmbedderAdapter`, `BERTAdapter`, `EmbeddingPool`

| Module | Lines | Responsibility |
|--------|-------|---|
| `nomic_embedder.py` | 380+ | Nomic BERT embeddings; context window = 2048 tokens; 768-dim output |
| `adapter.py` | 290+ | LoRA adapter for BERT; parameter-efficient fine-tuning |

**Boundary:** Accepts text; returns embedding vector.

---

#### SUBSYSTEM: src/asr/ — AUTOMATIC SPEECH RECOGNITION

**Purpose:** Audio transcription; forced alignment; acoustic model training  
**Primary Classes:** `ASRModel`, `ForcedAligner`, `FineTuner`

| Module | Lines | Responsibility |
|--------|-------|---|
| `forced_aligner.py` | 420+ | Viterbi alignment; phoneme-level timestamps; confidence scoring |
| `finetune.py` | 350+ | CTC loss; data loading; mixed precision training |
| `compiler/` | 200+ | Audio preprocessing; MFCC extraction; spectrogram generation |

**Boundary:** Accepts audio waveform; returns transcription + timestamps.

---

#### SUBSYSTEM: src/retrieval/ — SEMANTIC SEARCH AND RAG

**Purpose:** Vector index management, k-NN search, RAG pipeline  
**Primary Classes:** `VectorIndex`, `RAGPipeline`, `RerankingStrategy`

| Module | Lines | Responsibility |
|--------|-------|---|
| `vector_search.py` | 400+ | FAISS or HNSW index; approximate k-NN; reranking via cross-encoder |
| `rag_pipeline.py` | 450+ | Query embedding; context retrieval; prompt template; generation |
| `chunking.py` | 280+ | Semantic chunking; overlap handling; recursive splitting |

**Boundary:** Accepts query text; returns ranked context documents.

---

#### SUBSYSTEM: src/engine/ — TRANSFORMATION AND RULES

**Purpose:** Task transformation rules; symbolic computation; meta-level reasoning  
**Primary Classes:** `EngineRuleSet`, `TransformationEngine`, `SymbolicCompiler`

| Module | Lines | Responsibility |
|--------|-------|---|
| `rules.py` | 320+ | Rule definitions; priority ordering; applicability conditions |
| `transformations.py` | 380+ | Symbolic transformation; graph rewriting; normal form reduction |

**Boundary:** Accepts task + rule set; returns transformed task or proof tree.

---

#### SUBSYSTEM: src/exgracy/ — AUTOMATA AND LANGUAGE RECOGNITION

**Purpose:** Finite automata; language formalization; parsing  
**Primary Classes:** `Automaton`, `NFAtoNFA`, `LanguageSpecification`

| Module | Lines | Responsibility |
|--------|-------|---|
| `automaton.py` | 420+ | DFA/NFA construction; state minimization; simulation |

**Boundary:** Accepts regex or BNF; returns compiled automaton.

---

#### SUBSYSTEM: src/zk/ — ZERO-KNOWLEDGE PROOFS

**Purpose:** ZK circuit construction; proof generation and verification  
**Primary Classes:** `ZKCircuit`, `ZKProver`, `ZKVerifier`

**Status:** Placeholder; no verified implementation yet  
**Boundary:** Not fully integrated into main pipeline.

---

#### SUBSYSTEM: src/wasm/ — WEBASSEMBLY

**Purpose:** WASM runtime; JS interop; browser execution  
**Primary Classes:** `WASMRuntime`, `MacroWASMCompiler`

| Module | Lines | Responsibility |
|--------|-------|---|
| `macro_wasm.py` | 299 | High-level macro DSL → WASM; control flow lowering |
| `tunnel_layer.py` | 283 | JS-Python message bridge; async protocol; memory sharing |

**Boundary:** Accepts Python code; generates WASM module.

---

#### SUBSYSTEM: src/qregex/ — QUANTUM REGEX

**Purpose:** Quantum pattern matching; superposition of regex states  
**Primary Classes:** `QuantumRegex`, `QuantumMatcher`

**Status:** Experimental; leverages quantum simulation  
**Boundary:** Accepts regex + quantum state; returns match probability distribution.

---

#### SUBSYSTEM: src/resonance/ — HARMONIC SIGNAL PROCESSING

**Purpose:** Resonance detection; harmonic analysis; pattern synchronization  
**Primary Classes:** `ResonanceAnalyzer`, `HarmonicFilter`

**Status:** Research module; integration pending  
**Boundary:** Accepts time series; returns frequency components.

---

#### SUBSYSTEM: src/hypervisor/, src/daemon/, src/kernel/, src/magma/, src/mcp/, src/scanner/, src/hardware/, src/compositor/, src/ui/, src/isa/

These subsystems are present but have limited implementation depth. See DIRECTORY_REFERENCE.md for per-directory details.

---

### tests/ — PYTHON TESTS

| File | Purpose | Test Target | Status |
|------|---------|-------------|--------|
| `test_routing_trace_endpoints.py` | HTTP bridge tests; routing trace export | src/bridge/ | ACTIVE |
| `live_routing_test.py` | End-to-end routing pipeline integration | src/routing/ | ACTIVE |
| `stress_test_no_drift.py` | Continuity determinism; replay stability | src/continuity/ | ACTIVE |

---

### docs/ — USER AND TECHNICAL DOCUMENTATION

**Primary Language:** Markdown  
**Audience:** Developers, researchers, DevOps

| File | Subject | Status |
|------|---------|--------|
| `README.md` | Index and getting-started overview | VERIFIED |
| `GETTING_STARTED.md` | Installation; setup; first run | VERIFIED |
| `CONFIGURATION.md` | Environment variables; runtime options | VERIFIED |
| `ROUTING.md` | Routing pipeline architecture; expert selection | VERIFIED |
| `TOOLS.md` | Tool discovery; schema; authorization | VERIFIED |
| `CONTINUITY.md` | State snapshots; replay; recovery | VERIFIED |
| `ASR_AND_BRIDGE.md` | Audio transcription; HTTP bridge | VERIFIED |
| `LOCAL_TRAINING_OLLAMA.md` | Local inference with Ollama | VERIFIED |
| `BRICK_PROTOCOL_SPECIFICATION.md` | Binary protocol specification | VERIFIED |
| `PRODUCTION_HARDENING.md` | Security; deployment readiness | VERIFIED |
| `SECURITY.md` | Threat model; enforcement boundaries | VERIFIED |
| `VALIDATION.md` | Checks performed; scope of guarantees | VERIFIED |
| `MACHINE_CODE.md` | Machine runtime; bytecode; x86 code gen | VERIFIED |
| `IDE.md` | Windows IDE and desktop client | VERIFIED |
| `TESTING.md` | Test suites; coverage; CI/CD | VERIFIED |
| `benchmarks/` | Historical benchmark data; analysis | VERIFIED |

---

### research/ — FORMAL METHODS AND PAPERS

**Primary Languages:** Lean 4, Agda, Markdown, LaTeX, Python (NumPy/SciPy)

#### research/formal/ — FORMAL VERIFICATION

| File | Language | Subject | Status |
|------|----------|---------|--------|
| `enochian_root.lean` | Lean 4 | Enochian alphabet formalization | VERIFIED |
| `gdr_drain.lean` | Lean 4 | GDR kernel entropy decay | VERIFIED |
| `VA_243.lean` | Lean 4 | Vector arithmetic (243-dimensional) | VERIFIED |
| `IronicMirror/XInvariant.agda` | Agda | Projective invariant proof | VERIFIED |
| `proofs/gnostic/AlHamidMatrix.lean` | Lean 4 | Matrix algebra over gnostic ring | VERIFIED |
| `proofs/gnostic/GnosticArithmetic.lean` | Lean 4 | Gnostic arithmetic ring | VERIFIED |
| `sovereign_entropy/EntropyBound.lean` | Lean 4 | Entropy upper bound; Weil bounds | VERIFIED |
| `subleq/SUBLEQ.lean` | Lean 4 | SUBLEQ machine formalization | VERIFIED |

**Status:** 0 sorry terms in formal proofs (100% complete).

#### research/papers/ — MANUSCRIPTS

| File | Format | Subject | Status |
|------|--------|---------|--------|
| `forge_tournament_subleq_to_braid.md` | Markdown | Forge Tournament; SUBLEQ to braid conversion | SUBMITTED |
| `liquidops_kernel.tex` | LaTeX | LiquidOps compiler kernel | SUBMITTED |
| `sovereign_entropy.tex` | LaTeX | Entropy bounds; Weil bounds connection | SUBMITTED |
| `gdr_kernels.tex` | LaTeX | GDR kernel implementation | SUBMITTED |

#### research/sparse-routing/ — INDEPENDENT ROUTING RESEARCH

**Language:** Python (NumPy, SciPy)

| Directory/File | Purpose |
|---|---|
| `experiments/run_experiment.py` | Synthetic graph routing benchmark |
| `experiments/results.json` | Committed benchmark data (7 nodes, 8 edges) |
| `docs/report.md` | Method description; limitations; analysis |
| `README.md` | Getting started for sparse-routing research |

**Note:** This is a separate implementation from `src/routing/`. It operates on graph models, not symbolic text.

---

### training/ — SWIFT CORPUS AND VISUALIZATION

**Primary Language:** Swift  
**Platform:** macOS 14+, iOS 17+

| File/Directory | Purpose |
|---|---|
| `Package.swift` | Swift Package Manager definition |
| `Sources/` | Swift source code; SceneKit visualization |
| `Tests/` | Swift unit tests |

**Subsystems:**
- **AgentFishTank:** Swift library for agent state transitions and corpus loading
- **Corpus schema:** Dataset card; training corpus structure
- **Visualization:** 3D SceneKit rendering of agent swarms

**Boundary:** Accepts task batches; outputs training corpus; renders swarm visualization.

---

### hf/ — HUGGING FACE MODEL PACKAGING

**Primary Language:** Python, Markdown  
**Artifact Type:** Model cards, config files, corpus schema

#### hf/sovereign-memory-twin/

**Model Type:** Recurrent memory twin network  
**Base:** Llama 2 7B + GRU memory gate  
**Output:** Persistent memory state + text generation

| File | Purpose |
|---|---|
| `config.json` | HF config; model architecture |
| `modeling_memory_twin.py` | Model class; forward pass |
| `model_card.md` | Dataset; training details; limitations |

#### hf/burt-imma/

**Model Type:** Bidirectional Universal Recurrent Transformer  
**Base:** T5-large + attention adapters  
**Output:** Sequence embedding + task routing logits

| File | Purpose |
|---|---|
| `config.json` | HF config |
| `modeling_burt.py` | Model class; forward pass |
| `model_card.md` | Dataset; architecture; benchmarks |

#### hf/sovereign-training-corpus/

**Dataset Type:** Multi-task instruction corpus  
**Format:** Hugging Face datasets library

| File | Purpose |
|---|---|
| `dataset_card.md` | Dataset documentation |
| `schema.json` | JSON schema for corpus records |

---

### native/ — NATIVE x86-64 RUNTIME

**Primary Language:** NASM assembly, C

#### native/asm/ — ASSEMBLY SOURCE FILES

**Subsystems:**
- **QRA (Quaternion Rotation Algebra):** Quaternion ops; rotation matrices
- **Jordan block operations:** Matrix decomposition; eigenvalue computation
- **NAND circuits:** Boolean logic; truth tables
- **IPC (Inter-Process Communication):** Message passing; shared memory
- **Syscall wrappers:** Raw system calls; error handling

#### native/dispatcher/ — C DISPATCHER

**Purpose:** Call convention translation; assembly interop; error handling  
**Primary File:** `dispatcher.c`

---

### kernels/ — HARDWARE AND COMPILER BACKENDS

**Primary Languages:** CUDA, Rust, MLIR, P4, x86 assembly

#### kernels/cuda/ — NVIDIA CUDA

**File:** `cuda_pipeline.cu`  
**Purpose:** GPU compute kernels for sparse expert dispatch  
**Capabilities:** Matrix multiplication; attention; sparsity patterns

#### kernels/cudaq/ — CUDA-Q (Quantum)

**File:** `gdr_cudaq_kernel.cu`  
**Purpose:** Quantum circuit simulation; GDR kernel on quantum hardware  
**Status:** Research prototype

#### kernels/mlir/ — MLIR COMPILER

**Purpose:** Multi-level IR compilation; lowering to hardware backends  
**Targets:** x86, ARM, LLVM

#### kernels/tvm/ — TVM (Tensor Virtual Machine)

**Purpose:** Tensor compiler; operator fusion; device code generation  
**Targets:** CPU, GPU, embedded

#### kernels/p4/ — P4 (Programmable Switches)

**Purpose:** Network packet processing; in-network compute  
**Status:** Experimental

#### kernels/rust/ — Rust Implementation

**Primary File:** `src/main.rs`  
**Purpose:** Standalone Rust kernel library; no Python dep; vendorable

#### kernels/hardware/ — Hardware Research

**Purpose:** Custom silicon exploration; RTL experiments  
**Status:** Design-phase; no silicon tapeout

#### kernels/x86/ — x86-64 Assembly

**Purpose:** Low-level x86 intrinsics; SIMD; performance-critical paths

---

### catn/ — TENSOR NETWORK IMPLEMENTATION

**Primary Language:** Rust  
**Purpose:** Tensor contraction; shape broadcasting; memory layout

| Directory | Purpose |
|---|---|
| `src/` | Rust source code |
| `src/main.rs` | Entry point; CLI interface |
| `src/dispatcher.rs` | Task dispatch; tensor routing |
| `src/state.rs` | Tensor state management; memory pooling |
| `src/kernels/` | Tensor operations (erosion, propagation, etc.) |
| `microrom/` | Micro ROM firmware; boot sequences |

**Boundary:** Accepts tensor; returns contracted result.

---

### cobalt/ — HASKELL COMPILER PACKAGE

**Primary Language:** Haskell  
**Build System:** Cabal

**Purpose:** Compiler core; LiquidHaskell refinement types; ISA specification

#### cobalt/src/

**Main executable:** `Main.hs`

#### cobalt/ MODULES

| Module | Purpose |
|---|---|
| `Core/` | Group theory; natural numbers; algebraic foundations |
| `Calculus/` | Differentiation; integration; limit computation |
| `Language/` | Fixpoint logic; SMT theories; recursion elimination |
| `LiquidOps/` | LiquidHaskell kernel; dependent types |
| `ISA/` | Instruction set architecture specification |
| `Physics/` | Physics formalization (Godel, wormholes) |
| `Lean4/` | Lean 4 conductor spec; runtime verification |

**Supporting files:**
- `HumorMultiplicity.hs` — Type-level comedy; constraint propagation
- `MagicCobalt.hs` — Template Haskell macros; DSL generation
- `X86BatchAssembler.hs` — x86 assembly batch compilation

**Build:** `cabal build` in cobalt/ directory

---

### magma/ — PROTOCOL AND RUNTIME KERNELS

**Primary Languages:** Rust, Ada (planned)

#### magma/src/ — Main Library

**File:** `lib.rs`

#### magma/bindings/ — FFI BRIDGES

**Subsystems:**
- `rust/ada_ffi.rs` — Ada runtime foreign function interface
- `rust/magmad_client.rs` — Client for magmad daemon

#### magma/node/ — Runtime Kernel Daemon

**Purpose:** Background process; endpoint management; message routing

#### magma/apl/ — APL ARRAY PROGRAMMING

**Purpose:** Array language; tensor DSL; numerical compute

---

### narm/ — RUNTIME AND KERNEL WITH FORTRAN

**Primary Languages:** Fortran, MLIR, C

#### narm/fortran/ — FORTRAN KERNELS

**Purpose:** Scientific computing; numerical stability; vectorization

#### narm/runtime/ — Runtime Support

#### narm/kernels/ — Custom Kernels

#### narm/mlir/ — MLIR LOWERING

#### narm/tests/ — Test Suite

#### narm/docs/ — Documentation

---

### ide/ — WINDOWS C/C++ IDE AND ELECTRON WORKBENCH

**Primary Languages:** C/C++, TypeScript, JavaScript

#### ide/desktop/ — Electron Application

**Purpose:** Cross-platform IDE; code editing; live preview  
**Build System:** Vite + Electron  
**Packages:** See package.json scripts

#### ide/native/ — Native C/C++ Backend

**Purpose:** Windows-specific integration; performance-critical paths

#### ide/config/ — Configuration Files

#### ide/beam/ — BEAM/WebAssembly

**Purpose:** Browser-based IDE experiments  
**Status:** Early-stage

---

### runtime/ — RUST GNOSTIC ARITHMETIC

**Primary Language:** Rust

#### runtime/src/ — Source Code

**Purpose:** Gnostic arithmetic ring; computational substrate

---

### the-49th-call/ — CALL49 SUBSTRATE

**Primary Languages:** Rust, Python

**Purpose:** Substrate for the 49th agent invocation; episodic framing

#### the-49th-call/substrate/ — Call49 Implementation

#### the-49th-call/src/ — Source Code

---

### sovereign/ — NODE METADATA AND CAPABILITIES

**Primary Language:** Python

| File | Purpose |
|---|---|
| `node_key.py` | Ed25519 keypair management; node identity |
| `release_tag.py` | Release versioning; tagging logic |
| `capability_loader.py` | Dynamic capability discovery; loading |

---

### scripts/ — AUTOMATION AND EXECUTION

**Primary Language:** Bash, Python

**Purpose:** Deployment; testing; routine operations; CI/CD hooks

---

### sov jetbrains/ — JETBRAINS IDE PLUGIN

**Primary Language:** Java, Kotlin (Gradle-based)

**Purpose:** IDE integration; syntax highlighting; refactoring support

---

## LANGUAGE DISTRIBUTION MATRIX

| Language | File Count | Primary Subsystem | Build Tool | Status |
|----------|-----------|------------------|-----------|--------|
| Python | 173 | src/ (core engine) | setuptools (pip) | ACTIVE |
| Haskell | 35+ | cobalt/ (compiler) | Cabal | VERIFIED |
| Lean 4 | 8+ | research/formal/ | Lake | VERIFIED |
| Agda | 3+ | research/formal/ | agda-mode | VERIFIED |
| Rust | 25+ | catn/, kernels/rust, runtime/, the-49th-call/ | Cargo | ACTIVE |
| CUDA/CUDAQ | 2 | kernels/cuda*, kernels/cudaq/ | nvcc | VERIFIED |
| MLIR | 1+ | kernels/mlir/, narm/mlir/ | mlir-opt | VERIFIED |
| NASM | 8+ | native/asm/ | nasm | VERIFIED |
| C/C++ | 10+ | native/dispatcher/, ide/native/ | CMake, MSVC | VERIFIED |
| Swift | 8+ | training/ | Swift PM | VERIFIED |
| TypeScript/JavaScript | 5+ | ide/desktop/, ide/beam/ | Vite, Webpack | VERIFIED |
| LaTeX | 4 | research/papers/ | pdflatex, xelatex | VERIFIED |
| Markdown | 50+ | docs/, research/papers/ | (documentation) | VERIFIED |
| P4 | 1+ | kernels/p4/ | p4c | RESEARCH |
| Fortran | 3+ | narm/fortran/ | gfortran | VERIFIED |
| Ada | Planned | magma/ | GNAT | PENDING |

---

## SUBSYSTEM BOUNDARIES AND ISOLATION

### Execution Boundaries

1. **Python Core → Bedrock:** run.py uses BedrockBackend (boto3)  
2. **Python Core → Native:** src/runtime/machine/ can emit x86 assembly  
3. **Python Core → CUDA:** src/inference/ can invoke CUDA kernels via ctypes  
4. **Python Core → WebAssembly:** src/wasm/ compiles Python to WASM  
5. **Haskell → MLIR:** cobalt/ emits MLIR for lowering  
6. **Lean/Agda → Python:** Formal proofs; no code generation (verification only)  
7. **Swift → Python:** training/ is standalone; corpus is JSON export  
8. **Rust → Python:** catn/, kernels/rust/ are vendorable; callable via FFI or subprocess

### Data Flow Boundaries

- **Input:** Task text or binary message (Task entity)
- **Routing:** RoutingPipeline → expert callbacks
- **Inference:** ReActAgent → BedrockBackend (text) or local model (embeddings)
- **Tools:** Tool registry lookup → IPC dispatch → result validation
- **Output:** Text generation, embeddings, or proof traces
- **Persistence:** WORMLedger (append-only), ContinuityManager (snapshots)

---

## BUILD SEQUENCE AND DEPENDENCIES

### Python (Primary)

```
setup.py / pyproject.toml (pip install -e .)
  ↓ (imports)
  src/ (173 Python files)
  ├── run.py (entry point)
  ├── src/routing/ (core pipeline)
  ├── src/agents/ (ReAct loop)
  ├── src/inference/ (Bedrock, multi-provider)
  ├── src/models/ (memory, checkpoints)
  ├── src/tools/ (registry, loader, supervisors)
  └── [other subsystems]
```

### Haskell (cobalt/)

```
cabal build (in cobalt/ directory)
  ↓
cobalt/cobalt.cabal
  ├── src/Main.hs
  ├── Core/
  ├── Calculus/
  ├── LiquidOps/
  └── (dependencies: base, liquid-fixpoint, ghc-lib-parser)
```

### Rust (catn/, kernels/rust, runtime/)

```
cargo build (in respective directories)
  ├── catn/Cargo.toml
  ├── kernels/rust/Cargo.toml
  ├── runtime/Cargo.toml
  └── (dependencies: serde, rayon, ndarray, etc.)
```

### Swift (training/)

```
swift build (in training/ directory)
  ├── Package.swift
  ├── Sources/
  └── (dependencies: SceneKit, Foundation)
```

### Formal Methods (research/formal/)

```
Lean 4: lake build (requires Lean toolchain)
Agda:   agda --compile (requires Agda 2.6+)
```

---

## PRODUCTION READINESS AND VALIDATION SCOPE

| Component | Test Coverage | Production Ready | Notes |
|-----------|---|---|---|
| **src/routing/** | Active (live_routing_test.py) | Beta | Interface stable; no EOF integration tests |
| **src/agents/react** | Moderate | Beta | ReAct loop validated; tool binding integration needed |
| **src/inference/bedrock** | Functional | Beta | Bedrock backend works; streaming not implemented |
| **src/models/recursive_memory** | Design-level | Research | Memory twin not trained; proof-of-concept only |
| **src/continuity/** | Functional | Beta | Checkpoint/replay works; determinism under load untested |
| **src/tools/** | Active (test_routing_trace_endpoints.py) | Beta | Registry stable; loader tested |
| **native/asm** | Not tested | Research | Unverified on all instruction sets |
| **cobalt/** | Compiles | Research | No test suite; LiquidHaskell mode experimental |
| **kernels/cuda** | Compiles | Research | No benchmark; kernels not profiled |
| **research/formal/** | Proven (Lean/Agda) | Published | 0 sorry terms; ready for peer review |

See docs/PRODUCTION_HARDENING.md and docs/VALIDATION.md for full audit trail.

---

## DOCUMENTATION STATUS

| Category | Count | Quality | Location |
|----------|-------|---------|----------|
| Architecture docs | 3 | Complete | docs/README.md, ARCHITECTURE.md, docs/ROUTING.md |
| API docs | 6 | Incomplete | Embedded in docstrings; no Sphinx/auto-doc |
| Runbooks | 5 | Complete | docs/GETTING_STARTED.md, LOCAL_TRAINING_OLLAMA.md, etc. |
| Security | 2 | Complete | docs/SECURITY.md, PRODUCTION_HARDENING.md |
| Formal proofs | 8 | Verified | research/formal/ |
| Research papers | 4 | Submitted | research/papers/ |
| Inline code comments | Partial | Varies | Quality varies by subsystem |

---

## SUMMARY: STATISTICS

- **Total Files:** 300+ (excluding .venv and .git)
- **Python Files:** 173
- **Lines of Python Code:** 50,474
- **Language Diversity:** 14 distinct languages
- **Subsystems:** 40+
- **Documentation Pages:** 15
- **Formal Proofs:** 8 (zero sorry terms)
- **Build Systems:** 5 (setuptools, Cabal, Cargo, Swift PM, Lake)
- **Test Suites:** 3 active (pytest)
- **Entry Point:** run.py (direct runner) or `sovereign` CLI

---

## END OF REPOSITORY MAP

For detailed per-directory reference, see DIRECTORY_REFERENCE.md.  
For architecture diagrams, see ARCHITECTURE.md.  
For dependency graph, see DEPENDENCY_GRAPH.md.
