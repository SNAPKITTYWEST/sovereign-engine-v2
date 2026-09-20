# SOVEREIGN ENGINE V2 — DEPENDENCY GRAPH

**Created:** 2026-09-19  
**Status:** Complete dependency mapping

---

## PYTHON DEPENDENCY GRAPH

### Layer 0: Foundation

```
PyNaCl (Ed25519 signatures)
  └─ Used by: src/core/crypto.py

Blake3 (hashing)
  └─ Used by: src/core/evidence.py (WORM ledger)

Pydantic (data validation)
  └─ Used by: src/core/types, src/models/entities

JSONSchema (validation)
  └─ Used by: src/tools/registry, src/bridge/http_server
```

### Layer 1: Async I/O

```
asyncio (standard library)
  ├─ Used by: src/agents/react.py, src/routing/dispatch.py
  └─ Critical for concurrent tool execution

aiofiles (async file ops)
  └─ Used by: src/continuity/manager.py, src/runtime/sandbox.py

httpx (async HTTP client)
  ├─ Used by: src/bridge/http_server.py (FastAPI app)
  └─ Alternative to requests for async context
```

### Layer 2: Linear Algebra & Scientific

```
NumPy (array computation)
  ├─ Used by: src/routing/symbolic.py (Jordan decomposition)
  ├─ Used by: src/attention/ (tensor ops)
  └─ Version: >=1.26.0

SciPy (scientific algorithms)
  ├─ Used by: src/routing/pipeline.py (eigenvalue solve)
  ├─ Used by: src/entropy/governor.py (statistical sampling)
  └─ Version: >=1.12.0

Scikit-learn (optional; for clustering)
  └─ Used by: src/tools/rerank/ (document reranking)
```

### Layer 3: Machine Learning

```
PyTorch (tensor library)
  ├─ Version: >=2.2.0
  ├─ Used by: src/models/recursive_memory.py (GRU cell)
  ├─ Used by: src/attention/ (transformer blocks)
  └─ Dependency: sentence-transformers, transformers

Transformers (HuggingFace)
  ├─ Version: >=4.38.0
  ├─ Used by: src/bert/nomic_embedder.py
  ├─ Used by: src/models/ (tokenizers, configs)
  └─ Dependency: torch, tokenizers

Sentence-Transformers (embeddings)
  ├─ Version: >=2.5.0
  ├─ Used by: src/bert/adapter.py
  ├─ Used by: src/retrieval/vector_search.py
  └─ Dependency: torch, transformers
```

### Layer 4: AWS Integration

```
boto3 (AWS SDK)
  ├─ Version: >=1.34.0
  ├─ Used by: src/inference/bedrock_backend.py (Bedrock)
  ├─ Used by: src/core/storage.py (S3 backend)
  └─ Region: us-east-1 (default)

botocore (AWS core client)
  ├─ Version: >=1.34.0
  ├─ Dependency: boto3
  └─ Implicit dependency (installed with boto3)
```

### Layer 5: Web & Parsing

```
BeautifulSoup4 (HTML parsing)
  ├─ Version: >=4.12.0
  ├─ Used by: src/tools/web/ (web scraping)
  └─ Dependency: lxml

lxml (XML/HTML parser)
  ├─ Version: >=5.1.0
  ├─ Used by: BeautifulSoup4 backend
  └─ Faster than html.parser
```

### Layer 6: Testing & Development

```
pytest (unit testing)
  ├─ Version: >=8.0.0
  ├─ Used by: tests/
  └─ Entry: pytest tests/

pytest-asyncio (async test support)
  ├─ Version: >=0.23.0
  ├─ Used by: tests/live_routing_test.py
  └─ Fixtures: @pytest.mark.asyncio

pytest-cov (coverage reporting)
  ├─ Version: >=4.1.0
  └─ Entry: pytest --cov=src tests/

pytest-mock (mocking support)
  ├─ Version: >=3.12.0
  └─ Used by: tests/ (mock objects)

black (code formatter)
  ├─ Version: >=24.2.0
  └─ Entry: black src/ tests/

mypy (type checking)
  ├─ Version: >=1.8.0
  └─ Entry: mypy src/

ruff (fast linter)
  ├─ Version: >=0.2.0
  └─ Entry: ruff check src/ tests/
```

---

## INTERNAL PYTHON DEPENDENCIES

### src/routing/ → Others

```
src/routing/pipeline.py
├─ Imports: src/core/types, src/core/crypto, src/tools/registry
├─ Externals: numpy, scipy (linear algebra)
└─ Called by: src/agents/react.py, run.py

src/routing/symbolic.py
├─ Imports: src/core/types
├─ Externals: numpy, ast (standard library)
└─ Called by: src/routing/pipeline.py

src/routing/dispatch.py
├─ Imports: src/core/types, src/routing/weights
├─ Externals: asyncio
└─ Called by: src/routing/pipeline.py (async dispatch)

src/routing/weights.py
├─ Imports: src/core/types
├─ Externals: numpy
└─ Called by: src/routing/pipeline.py
```

### src/agents/ → Others

```
src/agents/react.py
├─ Imports: src/core/types, src/tools/registry, src/continuity/manager
├─ Imports: src/inference/* (model backends)
├─ Externals: asyncio, dataclasses
└─ Called by: run.py, src/bridge/http_server.py

src/agents/mcts.py
├─ Imports: src/core/types, src/agents/react.py
├─ Externals: asyncio, heapq (priority queue)
└─ Called by: (optional; not in run.py)

src/agents/shadow.py
├─ Imports: src/agents/react.py, src/agents/mcts.py
├─ Externals: asyncio, threading
└─ Called by: (optional; hypothesis testing)
```

### src/tools/ → Others

```
src/tools/registry.py
├─ Imports: src/core/types
├─ Exports: ToolRegistry, ToolDefinition, ToolPolicy
└─ Called by: src/agents/react.py, src/tools/loader.py, run.py

src/tools/loader.py
├─ Imports: src/tools/registry.py, src/tools/*/
├─ Imports: src/scanner/ast_analyzer.py (schema detection)
├─ Externals: importlib, pkgutil
└─ Called by: run.py

src/tools/ipc_router.py
├─ Imports: src/core/types, src/core/path_jail.py
├─ Externals: asyncio, json, subprocess
└─ Called by: src/agents/react.py (tool dispatch)

src/tools/supervisor.py
├─ Imports: src/core/types, src/tools/registry.py
├─ Externals: asyncio, json
└─ Called by: src/agents/react.py (result validation)

src/tools/approval.py
├─ Imports: src/core/types, src/tools/registry.py
├─ Externals: asyncio
└─ Called by: src/agents/react.py (authorization)
```

### src/inference/ → Others

```
src/inference/bedrock_backend.py
├─ Imports: src/core/types
├─ Externals: boto3, botocore, asyncio
└─ Called by: run.py, src/agents/react.py

src/inference/multi.py
├─ Imports: src/core/types, src/inference/bedrock_backend.py
├─ Externals: asyncio, httpx
└─ Called by: src/bridge/http_server.py (/chat endpoint)

src/inference/quantum_moe.py
├─ Imports: src/core/types, src/inference/*
├─ Externals: numpy, scipy
└─ Called by: (optional; research-only)
```

### src/models/ → Others

```
src/models/recursive_memory.py
├─ Imports: src/core/types
├─ Externals: torch, numpy
└─ Called by: src/agents/react.py (optional memory)

src/models/checkpoint_manager.py
├─ Imports: src/core/crypto, src/core/storage.py
├─ Externals: hashlib, json
└─ Called by: src/models/checkpoint_workflow.py

src/models/checkpoint_workflow.py
├─ Imports: src/models/checkpoint_manager.py, src/core/storage.py
├─ Externals: boto3 (S3 optional), asyncio
└─ Called by: (manual invocation; not in run.py)

src/models/entities.py
├─ Imports: src/core/types
├─ Externals: dataclasses, pydantic
└─ Called by: Every module using Task, Agent, Message
```

### src/continuity/ → Others

```
src/continuity/manager.py
├─ Imports: src/core/storage.py, src/core/evidence.py
├─ Imports: src/continuity/checkpoint.py, src/continuity/replay.py
├─ Externals: threading, asyncio
└─ Called by: src/agents/react.py (checkpoint after each step)

src/continuity/checkpoint.py
├─ Imports: src/core/types
├─ Externals: json, hashlib
└─ Called by: src/continuity/manager.py

src/continuity/replay.py
├─ Imports: src/core/types
├─ Externals: asyncio
└─ Called by: src/continuity/manager.py

src/continuity/seed_state.py
├─ Imports: src/core/types
├─ Externals: random, secrets
└─ Called by: src/continuity/manager.py

src/continuity/env_state.py
├─ Imports: src/core/types
├─ Externals: os
└─ Called by: src/continuity/manager.py

src/continuity/inode_state.py
├─ Imports: src/core/types
├─ Externals: os, pathlib
└─ Called by: src/continuity/manager.py

src/continuity/shared_mem.py
├─ Imports: src/core/types
├─ Externals: multiprocessing.shared_memory
└─ Called by: src/continuity/manager.py (optional)
```

### src/core/ (Foundation, no internal deps)

```
src/core/types.py
├─ Externals: dataclasses, typing, pydantic
├─ Imports: None (foundational)
└─ Called by: Every module

src/core/crypto.py
├─ Externals: PyNaCl, hashlib, secrets
├─ Imports: None (foundational)
└─ Called by: src/core/evidence.py, src/core/path_jail.py

src/core/evidence.py
├─ Imports: src/core/types, src/core/crypto
├─ Externals: json, hashlib
└─ Called by: src/continuity/manager.py, src/agents/react.py

src/core/storage.py
├─ Imports: src/core/types
├─ Externals: json, pathlib, boto3 (optional)
└─ Called by: src/continuity/manager.py, src/models/checkpoint_manager.py

src/core/protocols.py
├─ Imports: src/core/types
├─ Externals: typing, abc
├─ Imports: None (foundational)
└─ Called by: src/agents/react.py, src/tools/registry.py

src/core/path_jail.py
├─ Imports: src/core/types, src/core/crypto
├─ Externals: pathlib, os
└─ Called by: src/tools/ipc_router.py, src/runtime/sandbox.py
```

### src/bridge/ → Others

```
src/bridge/http_server.py
├─ Imports: src/routing/pipeline.py, src/agents/react.py
├─ Imports: src/bridge/key_manager.py, src/bridge/routing_trace.py
├─ Externals: fastapi, uvicorn, asyncio
└─ Entry: uvicorn src.bridge.http_server:app

src/bridge/key_manager.py
├─ Imports: src/core/crypto, src/core/storage.py
├─ Externals: json, asyncio
└─ Called by: src/bridge/http_server.py (/keys endpoint)

src/bridge/routing_trace.py
├─ Imports: src/core/types, src/routing/pipeline.py
├─ Externals: json
└─ Called by: src/bridge/http_server.py (/traces endpoint)

src/bridge/stdio_server.py
├─ Imports: src/routing/pipeline.py, src/agents/react.py
├─ Externals: asyncio, json
└─ Called by: (optional; stdio-based interface)
```

### src/runtime/ → Others

```
src/runtime/sovereign_machine.py
├─ Imports: src/runtime/machine/*
├─ Externals: asyncio, ctypes (optional), struct
└─ Called by: (optional; performance path)

src/runtime/machine/bytecode.py
├─ Imports: None
├─ Externals: struct, enum
└─ Called by: src/runtime/sovereign_machine.py

src/runtime/machine/x86_gen.py
├─ Imports: src/runtime/machine/bytecode.py
├─ Externals: struct, enum
└─ Called by: src/runtime/sovereign_machine.py

src/runtime/sandbox.py
├─ Imports: src/core/path_jail.py, src/core/types
├─ Externals: subprocess, os, asyncio
└─ Called by: src/tools/ipc_router.py (optional isolation)

src/runtime/filesystem.py
├─ Imports: src/core/types
├─ Externals: os, pathlib, mmap
└─ Called by: src/runtime/sandbox.py (VFS layer)

src/runtime/network.py
├─ Imports: src/core/types
├─ Externals: socket, asyncio
└─ Called by: src/runtime/sandbox.py (network policy)

src/runtime/providers/multi.py
├─ Imports: src/inference/bedrock_backend.py
├─ Externals: asyncio, httpx
└─ Called by: src/bridge/http_server.py (/chat endpoint)
```

### src/entropy/ → Others

```
src/entropy/governor.py
├─ Imports: src/core/types
├─ Externals: asyncio, random, time
└─ Called by: src/agents/react.py (entropy budgeting)

src/entropy/scheduler.py
├─ Imports: src/core/types
├─ Externals: heapq, asyncio, time
└─ Called by: src/entropy/governor.py

src/entropy/worm.py
├─ Imports: src/core/evidence.py
├─ Externals: asyncio, json
└─ Called by: src/agents/react.py (event recording)

src/entropy/constants.py
├─ Externals: (pure constants)
└─ Imported by: src/entropy/governor.py, src/entropy/scheduler.py
```

### src/attention/ → Others

```
src/attention/rma.py
├─ Imports: src/core/types
├─ Externals: torch, numpy
└─ Called by: src/models/recursive_memory.py (optional)

src/attention/sgam.py
├─ Imports: src/core/types
├─ Externals: torch, numpy
└─ Called by: src/models/* (sparse attention)

src/attention/sma.py
├─ Imports: src/core/types
├─ Externals: torch
└─ Called by: src/models/* (sliding window)

src/attention/umtcpi.py
├─ Imports: src/core/types
├─ Externals: torch, numpy
└─ Called by: src/models/* (batched inference)

src/attention/heat_kernel.py
├─ Imports: src/core/types
├─ Externals: torch, scipy
└─ Called by: (optional; spectral attention)

src/attention/integrated_block.py
├─ Imports: src/attention/*, src/core/types
├─ Externals: torch
└─ Called by: src/models/* (transformer block)
```

### src/bert/ → Others

```
src/bert/nomic_embedder.py
├─ Imports: src/core/types
├─ Externals: sentence_transformers, torch
└─ Called by: src/retrieval/vector_search.py

src/bert/adapter.py
├─ Imports: src/core/types
├─ Externals: torch, transformers
└─ Called by: (optional; fine-tuning)
```

### src/retrieval/ → Others

```
src/retrieval/vector_search.py
├─ Imports: src/bert/nomic_embedder.py
├─ Externals: numpy, faiss (optional), asyncio
└─ Called by: src/bridge/http_server.py (/search endpoint, optional)

src/retrieval/rag_pipeline.py
├─ Imports: src/retrieval/vector_search.py, src/agents/react.py
├─ Externals: asyncio
└─ Called by: (optional; RAG mode)

src/retrieval/chunking.py
├─ Imports: src/core/types
├─ Externals: re (regex)
└─ Called by: src/retrieval/rag_pipeline.py
```

### src/scanner/ → Others

```
src/scanner/ast_analyzer.py
├─ Imports: src/core/types
├─ Externals: ast (standard library), inspect
└─ Called by: src/tools/loader.py (schema detection)

src/scanner/dependencies.py
├─ Imports: src/core/types
├─ Externals: ast, importlib
└─ Called by: (optional; dependency analysis)
```

### src/engine/ → Others

```
src/engine/rules.py
├─ Imports: src/core/types
├─ Externals: abc
└─ Called by: src/engine/transformations.py

src/engine/transformations.py
├─ Imports: src/engine/rules.py, src/core/types
├─ Externals: asyncio
└─ Called by: src/agents/react.py (optional; task rewriting)
```

### Subsystems with No/Minimal Implementation

```
src/asr/ (ASR module)
├─ Imports: torch, transformers, numpy
└─ Status: Partial implementation; not integrated

src/cli/ (Command-line interface)
├─ Imports: src/routing/, src/agents/
├─ Entry point: sovereign = "src.cli.main:main"
└─ Status: Placeholder

src/compositor/ (Composition layer)
├─ Status: Placeholder; no implementation

src/daemon/ (Background daemon)
├─ Imports: src/agents/react.py, asyncio
└─ Status: Placeholder

src/exgracy/ (Automata)
├─ Imports: (DFA/NFA constructs)
└─ Status: Minimal implementation

src/hardware/ (Hardware synthesis)
├─ Status: Placeholder; research-only

src/hypervisor/ (Virtualization)
├─ Status: Not implemented

src/isa/ (Instruction set)
├─ Imports: (ISA definitions)
└─ Status: Minimal; reference only

src/kernel/ (Kernel-level ops)
├─ Status: Placeholder

src/magma/ (Protocol binding)
├─ Status: Placeholder

src/mcp/ (Model context protocol)
├─ Status: Placeholder

src/mum/ (Multimodal)
├─ Status: Placeholder

src/qregex/ (Quantum regex)
├─ Imports: (quantum simulation)
└─ Status: Research-only

src/resonance/ (Signal processing)
├─ Status: Placeholder

src/ui/ (User interface)
├─ Status: Placeholder

src/wasm/ (WebAssembly)
├─ Imports: (WASM compilation)
└─ Status: Experimental

src/zk/ (Zero-knowledge)
├─ Status: Placeholder; circuits not implemented
```

---

## BUILD SYSTEM DEPENDENCIES

### Python (setuptools)

```
pyproject.toml
├─ Core: PyNaCl, aiofiles, httpx, pydantic, jsonschema
├─ Scientific: numpy, scipy
├─ ML: torch, transformers, sentence-transformers
├─ Cloud: boto3, botocore
├─ Web: beautifulsoup4, lxml
├─ Testing: pytest, pytest-asyncio, pytest-cov, pytest-mock
├─ Linting: black, mypy, ruff
└─ Build: setuptools>=68.0, wheel

Entry point: src.cli.main:main
```

### Haskell (Cabal)

```
cobalt/cobalt.cabal
├─ Packages: base, ghc-lib-parser, liquid-fixpoint, ghc-lib
├─ Modules: Core/, Calculus/, Language/, LiquidOps/, ISA/, Physics/
└─ Executables: Main.hs
```

### Rust (Cargo)

```
catn/Cargo.toml
├─ Dependencies: serde, rayon, ndarray
└─ Build: cargo build

kernels/rust/Cargo.toml
└─ Standalone; no Python dependency

runtime/Cargo.toml
└─ Standalone; no Python dependency

the-49th-call/Cargo.toml
└─ Standalone; no Python dependency
```

### Swift (Swift Package Manager)

```
training/Package.swift
├─ Platforms: macOS 14, iOS 17
├─ Dependencies: SceneKit (system framework)
└─ Products: AgentFishTank library
```

### Formal (Lake/agda-mode)

```
research/formal/
├─ Lean 4: lake build (in .lean file directory)
├─ Agda: agda --compile
└─ No Python dependency
```

---

## CIRCULAR DEPENDENCY CHECK

**Status:** No circular dependencies detected

Verified paths:
- src/core/* → (no imports from src/)
- src/routing/* → src/core/ (one-way)
- src/agents/* → src/routing/, src/core/ (one-way)
- src/tools/* → src/core/ (one-way)
- src/inference/* → src/core/ (one-way)
- src/continuity/* → src/core/, src/core/evidence (one-way)
- src/bridge/* → src/routing/, src/agents/, src/inference/ (one-way)

**Conclusion:** Dependency graph is a DAG (directed acyclic graph).

---

## DEPENDENCY METRICS

| Metric | Value | Status |
|--------|-------|--------|
| Total Python modules | 173 | VERIFIED |
| Python lines of code | 50,474 | MEASURED |
| External dependencies (core) | 11 | ACTIVE |
| Optional dependencies | 4 | (bedrock, pytorch, etc.) |
| Internal dependencies | 40+ | (src/ ↔ src/) |
| Circular dependencies | 0 | VERIFIED |
| Max dependency depth | 7 layers | (src/core → src/bridge → http_server) |

---

## CROSS-LANGUAGE DEPENDENCIES

| From | To | Mechanism | Status |
|------|----|----|--------|
| Python | NASM | subprocess + ctypes | OPTIONAL |
| Python | CUDA | ctypes or PyCUDA | OPTIONAL |
| Python | Haskell | No runtime coupling | VERIFIED |
| Python | Lean 4 | No code generation | VERIFIED |
| Python | Rust | subprocess or FFI | OPTIONAL |
| Python | Swift | JSON export | VERIFIED |
| Haskell | Lean 4 | No coupling | VERIFIED |
| Rust | C | FFI | (magma/bindings/) |

---

## DEPENDENCY MANAGEMENT STRATEGY

### Version Pinning

```
requirements.txt: Exact versions
pyproject.toml: >=X.Y.Z (minimum versions)
Cabal files: >=X.Y (Haskell)
Cargo.toml: >=X.Y (Rust)
Package.swift: >=X.Y (Swift)
```

### Upgrade Path

1. **Minor/patch:** pip install --upgrade -r requirements.txt
2. **Major:** Review breaking changes; update pyproject.toml
3. **Formal proofs:** lake update (Lean); agda --version (Agda)

### Security

- Regular dependency audits: `pip audit`
- Locked versions for production: requirements.txt
- AWS credentials: boto3 credential chain (not hardcoded)

---

## END OF DEPENDENCY GRAPH

For subsystem details, see REPOSITORY_MAP.md.  
For architecture overview, see ARCHITECTURE.md.
