# Sovereign Engine v2

A multi-language repository for LLM agent execution, sparse expert routing, persistent model memory, compiler and hardware experiments, and formal research.

The Python engine contains an eleven-stage routing pipeline, ReAct agents, a tool registry, continuity storage, and WORM evidence records. Alongside it are a Windows C/C++ IDE, a Haskell compiler package, native assembly and accelerator sources, a Swift training frontend, and independent research implementations. These components have separate build and validation requirements.

**Documentation baseline:** [`898dfbe`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/898dfbe), September 18, 2026. Benchmarks below include the historical experiment artifact and a fresh ten-trial run. Both measure the isolated research router, not end-to-end LLM inference.

## Contents

- [Quick Start](#quick-start)
- [Overview & Architecture](#overview--architecture)
- [Repository Structure](#repository-structure)
- [Language Stack](#language-stack)
- [Getting Started](#getting-started)
- [Building from Source](#building-from-source)
- [API Reference](#api-reference)
- [Deployment & Scaling](#deployment--scaling)
- [Examples](#examples)
- [FAQ & Troubleshooting](#faq--troubleshooting)
- [Contributing](#contributing)
- [Performance & Benchmarks](#performance--benchmarks)
- [Glossary](#glossary)
- [Resources & License](#resources--license)
- [Rust Verification Workspace (100 Crates)](#rust-verification-workspace-100-crates)
  - [Crate Map](#crate-map)
  - [Novel Techniques & Things Worth Knowing](#novel-techniques--things-worth-knowing)
  - [Known Gaps / TODO](#known-gaps--todo)
- [Recent changes](#recent-changes)

---

## Quick Start

**Sovereign Engine v2** is a production-grade framework for autonomous LLM agent execution with algebraic routing, formal verification, and distributed continuity. It routes complex tasks through dynamically selected experts, maintains cryptographic proof trails, and enables deterministic replay of agent reasoning.

### 5-Minute Setup

```bash
# Clone and enter directory
git clone https://github.com/SNAPKITTYWEST/sovereign-engine-v2.git
cd sovereign-engine-v2

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install core dependencies
pip install -r requirements.txt

# Run first task (requires AWS Bedrock credentials)
python run.py

# Expected output: routing trace + ReAct reasoning + final answer
```

For a provider-free demo, use the isolated routing experiment:

```bash
cd research/sparse-routing
pip install numpy scipy pytest
python -m pytest tests/ -v
python -m experiments.run_experiment
```

---

## Overview & Architecture

### What It Does

- **Task Routing:** Parse natural language tasks, build symbolic graphs, apply algebraic transforms to select sparse experts
- **Agent Reasoning:** ReAct loops with tools, external APIs, and model inference (AWS Bedrock, local models, or multi-provider fallback)
- **Continuity & Recovery:** State snapshots with atomic transitions, deterministic replay, and rollback capability
- **Evidence Ledger:** Write-once append-only log with Ed25519 signatures and Blake3 hash chains—proof of execution
- **Tool Orchestration:** Registry-based tool discovery, authorization policy, IPC dispatch, and result validation

### 3-Layer Architecture

**Layer 1: Execution Core (Python)**

The primary Python engine (173 modules, 50K+ lines) orchestrates task routing, agent loops, and tool dispatch. At its heart is an **11-stage routing pipeline**:

1. **Parse AST** — Extract intent from task description
2. **Build Symbolic Graph** — Construct directed graph of task structure
3. **Jordan Transform** — Eigenvalue decomposition to detect invariants
4. **Jacobian Analysis** — Sensitivity analysis; constraint gradients
5. **Constraint Evaluation** — Filter infeasible expert combinations
6. **Sparse Activation** — Score experts; zero out low-confidence paths
7. **NAND Filtering** — Suppress conflicting expert pairs
8. **Expert Selection** — Identify active experts for dispatch
9. **Async Dispatch** — Invoke expert callbacks in parallel
10. **Result Aggregation** — Merge expert responses
11. **Trace Export** — Serialize routing decisions for audit

The **ReActAgent** loop implements: think (LLM generates reasoning) → act (select tool or emit answer) → observe (tool result or done) → repeat up to N steps.

**Layer 2: Inference & Continuity**

Multiple inference backends connect to different model providers:

- **BedrockBackend:** AWS Bedrock (claude-haiku-4-5 or claude-opus via boto3)
- **MultiProvider:** Task-aware provider selection with fallback routing
- **LocalModel:** Ollama or sentence-transformers for embeddings

The **ContinuityManager** synchronously snapshots state after each agent step. On recovery, deterministic replay re-executes with invariant validation. All state transitions are atomic; write-once-append-only on error.

**Layer 3: Verification & Evidence**

The **WORMLedger** (Write-Once Read-Many) maintains an immutable audit trail:

- Each event is timestamped and signed with Ed25519
- Hash chain (Blake3) links each event to its predecessor
- Verification scans the chain and enforces total order
- Result: cryptographic proof of execution; tamper-evident

### Execution Paths

1. **Direct Runner** (`python run.py`) — Load tools, route task, invoke ReAct, print result
2. **HTTP Bridge** (`uvicorn src.bridge.http_server:app`) — REST endpoints for /chat, /route, /tools, /traces
3. **Native Bytecode** (optional) — Emit x86-64 assembly from Python IR for performance-critical expert dispatch
4. **Formal Verification** (`lake build` in research/formal/) — Prove routing correctness in Lean 4

---

## Repository Structure

```
sovereign-engine-v2/
├─ src/                         # Python core (173 modules, 50K+ lines)
│  ├─ routing/                  # 11-stage pipeline, symbolic graph, Jordan transforms
│  ├─ agents/                   # ReActAgent, MCTS, Shadow agent
│  ├─ inference/                # Bedrock, MultiProvider, local model adapters
│  ├─ models/                   # Recursive memory networks, checkpoints
│  ├─ tools/                    # Registry, loader, IPC router, authorization
│  ├─ continuity/               # State snapshots, replay, determinism
│  ├─ core/                     # Evidence ledger (WORM), crypto, types
│  ├─ bridge/                   # HTTP server, key manager, trace export
│  ├─ runtime/                  # Bytecode VM, x86 code gen, sandbox
│  └─ [13 other subsystems]     # Entropy, attention, ASR, retrieval, etc.
├─ research/                    # Formal methods (Lean 4, Agda), papers
├─ training/                    # Swift corpus and visualization
├─ native/                      # NASM x86-64 runtime
├─ kernels/                     # CUDA, MLIR, P4, hardware
├─ cobalt/                      # Haskell compiler (Cabal)
├─ ide/                         # Windows IDE (C/C++ + CMake)
├─ docs/                        # Technical documentation
├─ run.py                       # Direct runner entry point
└─ README.md                    # This file
```

---

## Language Stack

Sovereign Engine v2 spans **16 languages**. Each serves a distinct role:

| Language | Files | LOC | Role | Build Tool |
|----------|-------|-----|------|-----------|
| Python | 173 | 50K+ | Core orchestration | setuptools/pip |
| Haskell | 35+ | 4K | Compiler kernel | Cabal |
| Lean 4 | 8 | 2.3K | Formal proofs (0 sorry terms) | Lake |
| Rust | 25+ | 2.3K | Tensor networks, gnostic arithmetic | Cargo |
| C/C++ | 15+ | 28K | IDE native layer | CMake |
| CUDA | 2 | 1K | GPU kernels | nvcc |
| NASM | 8+ | 2K | x86-64 assembly | nasm |
| TypeScript | 5+ | 2.5K | IDE frontend | Vite |
| Swift | 8+ | 1K | Training visualization | Swift PM |
| Agda | 3+ | 500 | Formal proofs | agda-mode |
| Fortran | 3+ | 1.5K | Scientific compute | gfortran |
| Other | — | — | MLIR, P4, LaTeX, etc. | — |

---

## Getting Started

### Prerequisites

- **Python 3.11+** (required)
- **pip** and **git**
- **AWS credentials** (for Bedrock, optional for local models)
- **CUDA 12.0+** (optional, for GPU kernels)
- **Haskell GHC 9.2+** (optional, for cobalt compiler)

### Installation

```bash
# Clone
git clone https://github.com/SNAPKITTYWEST/sovereign-engine-v2.git
cd sovereign-engine-v2

# Virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install
pip install -e .              # Development mode
# or
pip install -e ".[bedrock,pytorch]"  # With optional extras

# Verify
python run.py                 # Direct runner
# or
sovereign --help              # CLI
# or
uvicorn src.bridge.http_server:app --reload  # HTTP bridge
```

### First Run: Task Routing

```bash
python run.py
```

**Expected output:**

```
Loading tool registry...
Initializing RoutingPipeline...

Task: "Write a fibonacci function"

Routing Trace:
  Stage 1–11: [Parse AST → Expert Selection → Dispatch]
  Active experts: 3 (code_generation, algorithm_verification)
  NAND conflicts: 1 suppressed

ReActAgent loop:
  Thought: I need to write a fibonacci function...
  Action: code_generation tool
  Observation: [function result]
  Thought: Complete.

Final Answer: [fibonacci implementation]
```

### Configuration

**AWS credentials (for Bedrock):**

```bash
# Option 1: Environment variables
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret

# Option 2: Use ~/.aws/credentials (boto3 credential chain)
# Option 3: IAM role (if running in AWS)
```

**Local models instead of Bedrock:**

```bash
# Install Ollama and download a model
ollama pull mistral

# Set environment
export LLM_PROVIDER=local
export OLLAMA_BASE_URL=http://localhost:11434
```

### Run Tests

```bash
pip install pytest pytest-asyncio pytest-cov

# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific test
pytest tests/test_routing_trace_endpoints.py -v
```

---

## Building from Source

### System Requirements by Language

| Language | Requirement |
|----------|-------------|
| **Python** | 3.11+, pip, venv |
| **Haskell** | GHC 9.2+, Cabal 3.8+ |
| **Lean 4** | Lake (bundled with Lean), mathlib4 |
| **Rust** | Cargo 1.70+ |
| **C/C++** | MSVC (Windows) or GCC, CMake 3.24+ |
| **CUDA** | CUDA 12.0+, cuDNN 8.0+, nvcc |
| **NASM** | nasm 2.15+ |
| **TypeScript** | Node.js 18+, npm/yarn |
| **Swift** | Xcode 15+ (macOS) or Swift PM (cross-platform) |
| **Agda** | Agda 2.6.4+, agda-stdlib |

### Build Order

1. **Python core** — The entry point; all other components are optional
2. **Haskell compiler** (optional, for cobalt/)
3. **Rust subsystems** (optional, for catn/, kernels/)
4. **CUDA kernels** (optional, for performance)
5. **NASM runtime** (optional, for native dispatch)
6. **IDE** (optional, Windows only)
7. **Formal proofs** (optional, research-only)

### Build Instructions

**Python:**

```bash
pip install -e ".[bedrock,pytorch]"
pip install -r requirements.txt
pytest tests/ -v
```

**Haskell:**

```bash
cd cobalt/
cabal build
cabal test
```

**Rust:**

```bash
cd catn/
cargo build --release
./target/release/catn
```

**CUDA:**

```bash
cd kernels/
nvcc -O3 -c sparse_expert_dispatch.cu -o sparse_expert_dispatch.o
# Link with Python extension
```

**NASM:**

```bash
cd native/
nasm -f win64 qra_operations.asm -o qra_operations.o
gcc -c dispatcher.c -o dispatcher.o
gcc -o dispatcher.exe dispatcher.o qra_operations.o
```

**Lean 4:**

```bash
cd research/formal/
lake build
lake test
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'src'` | Run `pip install -e .` from repo root |
| `boto3.exceptions.Botocore.NoCredentialsError` | Set AWS credentials or use local model |
| `CUDA out of memory` | Reduce batch size or use CPU backend |
| `Lean/Agda not found` | Skip formal proofs; they are optional (research-only) |
| Tests timeout | Increase timeout: `pytest --timeout=60` |

---

## API Reference

### Core Classes

**RoutingPipeline**

```python
from src.routing.pipeline import RoutingPipeline

pipeline = RoutingPipeline(config)
trace, expert_scores = await pipeline.route(task_text)

# Returns:
# - trace: PipelineTrace (intent, weights, blocked experts, dispatch outcomes)
# - expert_scores: dict[str, float] (expert name → activation score)
```

**ReActAgent**

```python
from src.agents.react_agent import ReActAgent

agent = ReActAgent(backend, tools, max_steps=10)
response = await agent.run(task_text, routing_trace)

# Returns: str (final answer)
```

**ToolRegistry**

```python
from src.tools.registry import ToolRegistry

registry = ToolRegistry()
registry.register(name="code_gen", schema=..., handler=..., authorization=...)
result = await registry.dispatch(tool_name, args, context)
```

**ContinuityManager**

```python
from src.continuity.manager import ContinuityManager

manager = ContinuityManager(state_store)
snapshot = await manager.checkpoint(env, seed, model_state)
recovered_state = await manager.restore(snapshot_id)
```

**WORMLedger**

```python
from src.core.worm_ledger import WORMLedger

ledger = WORMLedger(path)
entry_hash = ledger.append({"event": "task_routed", "trace": ...})
is_valid, count = ledger.verify_chain()
```

**BedrockBackend**

```python
from src.inference.bedrock_backend import BedrockBackend

backend = BedrockBackend(region="us-east-1", model_id="...")
response = await backend.invoke(prompt, temperature=0.7)
```

### Type System

```python
# Risk classification for tools
class RiskClass(Enum):
    LOW = "low"           # Read-only, no side effects
    MEDIUM = "medium"     # File I/O, network calls
    HIGH = "high"         # System access, credential use

# Authorization policies
class ApprovalPolicy(Enum):
    AUTO = "auto"         # Always allowed
    REQUIRE_HUMAN = "human"  # Needs human approval
    SANDBOX = "sandbox"   # Run in isolated environment

# Task entity
class Task:
    id: str
    text: str
    priority: int
    context: dict
    created_at: float
```

### Usage Patterns

**Pattern 1: Route and Dispatch**

```python
pipeline = RoutingPipeline(config)
trace, scores = await pipeline.route("Write a function for...")
for expert_name, score in scores.items():
    if score > 0.5:
        await expert_callbacks[expert_name]()
```

**Pattern 2: ReAct Loop with Tool Use**

```python
registry = ToolRegistry()
registry.register("python_exec", schema=..., handler=run_code)
agent = ReActAgent(backend, registry)
answer = await agent.run("Solve: 2+2", trace)
```

**Pattern 3: Deterministic Replay**

```python
manager = ContinuityManager(store)
snapshot = await manager.checkpoint(env, seed, state)
# Later, on error:
recovered = await manager.restore(snapshot)
replayed = await agent.run(task, deterministic=True)
```

---

## Deployment & Scaling

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "src.bridge.http_server:app", "--host", "0.0.0.0"]
```

Build and run:

```bash
docker build -t sovereign-engine .
docker run -e AWS_REGION=us-east-1 -p 8000:8000 sovereign-engine
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: sovereign-engine
spec:
  serviceName: sovereign-engine
  replicas: 3
  selector:
    matchLabels:
      app: sovereign-engine
  template:
    metadata:
      labels:
        app: sovereign-engine
    spec:
      containers:
      - name: engine
        image: sovereign-engine:latest
        ports:
        - containerPort: 8000
        env:
        - name: AWS_REGION
          value: "us-east-1"
        - name: WORM_LEDGER_PATH
          value: "/data/worm.log"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
      volumeMounts:
      - name: data
        mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 10Gi
```

### Monitoring (Prometheus Metrics)

Key metrics to track:

```
sovereign_routing_latency_ms          # Routing pipeline duration
sovereign_expert_activation_count     # Number of active experts per task
sovereign_tool_dispatch_overhead_ms   # Tool IPC overhead
sovereign_model_availability          # Availability of each backend
sovereign_worm_ledger_entries         # Total WORM entries (append-only)
sovereign_checkpoint_memory_bytes     # Continuity snapshot size
sovereign_agent_loop_duration_ms      # Total ReAct loop duration
```

Example Prometheus config:

```yaml
global:
  scrape_interval: 15s
scrape_configs:
- job_name: sovereign-engine
  static_configs:
  - targets: ['localhost:8000']
  relabel_configs:
  - source_labels: [__address__]
    target_label: instance
```

### Multi-Region Fallback

```python
providers = [
    BedrockBackend(region="us-east-1"),
    BedrockBackend(region="eu-west-1"),
    LocalOllamaBackend(url="http://localhost:11434"),
]
backend = MultiProviderBackend(providers, fallback_strategy="round_robin")
response = await backend.invoke(prompt)  # Auto-fallback on failure
```

---

## Examples

### Example 1: Routing with Sparse Expert Selection

```python
from src.routing.pipeline import RoutingPipeline
from src.agents.react_agent import ReActAgent
import asyncio

async def example_routing():
    pipeline = RoutingPipeline({
        "hidden_size": 256,
        "num_experts": 8,
        "sparsity": 0.3,
    })
    
    task = "Write a Fibonacci function in Python"
    trace, scores = await pipeline.route(task)
    
    print(f"Task: {task}")
    print(f"Active experts: {[e for e, s in scores.items() if s > 0.5]}")
    print(f"Trace: {trace}")
    
    # Dispatch to active experts
    for expert_name, score in scores.items():
        if score > 0.5:
            print(f"  → Activating {expert_name} (score: {score:.3f})")

asyncio.run(example_routing())
```

### Example 2: ReAct Agent with Tool Use

```python
from src.tools.registry import ToolRegistry
from src.agents.react_agent import ReActAgent
from src.inference.bedrock_backend import BedrockBackend
import asyncio

async def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

async def example_react():
    # Register tools
    registry = ToolRegistry()
    registry.register(
        name="compute_fibonacci",
        schema={"type": "object", "properties": {"n": {"type": "integer"}}},
        handler=fibonacci,
        risk_class="low",
    )
    
    # Create backend and agent
    backend = BedrockBackend(region="us-east-1")
    agent = ReActAgent(backend, registry, max_steps=5)
    
    # Run task
    task = "What is the 10th Fibonacci number?"
    result = await agent.run(task)
    print(f"Result: {result}")

asyncio.run(example_react())
```

### Example 3: Deterministic Replay on Error

```python
from src.continuity.manager import ContinuityManager
from src.core.worm_ledger import WORMLedger
import asyncio

async def example_replay():
    manager = ContinuityManager(store="/tmp/state/")
    ledger = WORMLedger(path="/tmp/worm.log")
    
    # Execute and checkpoint
    env = {"task": "fibonacci", "seed": 42}
    snapshot_id = await manager.checkpoint(env, seed=42, model_state={})
    
    print(f"Checkpoint created: {snapshot_id}")
    
    # On error, restore and replay
    try:
        # ... some operation that fails ...
        raise RuntimeError("Execution error")
    except RuntimeError:
        print("Error detected. Restoring from checkpoint...")
        recovered = await manager.restore(snapshot_id)
        print(f"Recovered state: {recovered}")
    
    # Verify WORM ledger
    is_valid, entry_count = ledger.verify_chain()
    print(f"WORM ledger valid: {is_valid}, entries: {entry_count}")

asyncio.run(example_replay())
```

### Example 4: Custom Tool Registration

```python
from src.tools.registry import ToolRegistry
import re

async def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

async def example_tool():
    registry = ToolRegistry()
    
    registry.register(
        name="validate_email",
        schema={
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email address to validate"}
            },
            "required": ["email"],
        },
        handler=validate_email,
        risk_class="low",
        approval_policy="auto",
        timeout_seconds=5,
    )
    
    result = await registry.dispatch(
        "validate_email",
        args={"email": "user@example.com"},
        context={"user_id": "123"},
    )
    print(f"Validation result: {result}")

asyncio.run(example_tool())
```

---

## FAQ & Troubleshooting

**Q: How do I add a custom tool?**

A: Register it with the ToolRegistry:

```python
registry = ToolRegistry()
registry.register(
    name="my_tool",
    schema={...},
    handler=async_callable,
    risk_class="low",
)
```

**Q: How do I use local models instead of Bedrock?**

A: Set the environment and use LocalOllamaBackend:

```bash
ollama pull mistral
export LLM_PROVIDER=local
export OLLAMA_BASE_URL=http://localhost:11434
```

**Q: How do I view routing traces?**

A: Call the `/trace` HTTP endpoint or inspect the `PipelineTrace` object:

```bash
curl -X GET http://localhost:8000/traces/latest
```

**Q: How are routing conflicts resolved?**

A: NAND filtering suppresses conflicting expert pairs; remaining conflicts use merge strategy (weighted average or union).

**Q: How do I verify WORM ledger integrity?**

A:

```python
ledger = WORMLedger("/path/to/worm.log")
is_valid, count = ledger.verify_chain()
```

**Q: How do I extend the framework?**

A: Subclass or implement the core interfaces:
- `InferenceBackend` for new model providers
- `Agent` for new reasoning strategies
- `ToolHandler` for tool integration

---

## Contributing

### Workflow

1. **Fork** the repository
2. **Branch** (`git checkout -b feature/my-feature`)
3. **Commit** with clear messages
4. **Test** (`pytest tests/ --cov`)
5. **Push** and open a **Pull Request**

### Code Style

- **Python:** PEP 8, black formatting, mypy type hints
- **Haskell:** HLint, Ormolu
- **Rust:** `cargo fmt`, clippy
- **Lean 4:** mathlib conventions

### Commit Guidelines

```
[type] Brief description (under 60 chars)

Longer explanation if needed. Reference issues: #123
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

### Testing Requirements

- **Coverage threshold:** 75% for core modules
- **Async tests:** Use `pytest-asyncio`
- **Live tests:** Can fall back to mock backends

### PR Checklist

- [ ] Code follows project style
- [ ] Tests pass (`pytest tests/ -v`)
- [ ] Coverage ≥75% for changes
- [ ] Documentation updated
- [ ] Commit messages clear

### Subsystem Rules

- **Python core** (`src/`): Stable; all changes require tests
- **Research modules** (`research/`): Exploratory; formal proofs encouraged
- **Hardware** (`kernels/`, `native/`): Platform-specific; build instructions required
- **Formal proofs** (Lean/Agda): 0-sorry target; postulates documented

---

## Performance & Benchmarks

### Committed Sparse-Routing Experiment

**Source:** [run_experiment.py](research/sparse-routing/experiments/run_experiment.py). **Raw data:** [results.json](research/sparse-routing/experiments/results.json).

Fixture: 7-node directed graph, 8 edges, 8 timesteps. Three strategies compared:

| Strategy | Runtime (ms) | Mean Route Cost | Topology Changes |
|----------|---:|---:|---:|
| Static | 0.644 | 0.646 | 0 |
| Latency-aware | 0.789 | 0.631 | 0 |
| Rank-informed | 5.275 | 0.635 | 1 |

Relative to static: latency-aware reduces cost **2.24%**; rank-informed reduces cost **1.69%** and removes **12.5%** of edges. Rank-informed takes **8.2×** the static runtime due to adaptation overhead.

### Fresh Local Measurements (Sept 19, 2026)

**57 routing tests passed in 1.35 seconds.** Ten trials per strategy after one warmup:

| Strategy | Median Runtime | Min–Max | Peak Memory |
|----------|---:|---:|---:|
| Static | 0.644 ms | 0.568–1.261 ms | 7,888 B |
| Latency-aware | 0.789 ms | 0.704–2.318 ms | 8,132 B |
| Rank-informed | 5.275 ms | 4.740–6.380 ms | 33,247 B |

**Environment:** Windows 11, Python 3.12.10, NumPy 2.5.3, SciPy 1.18.1.

### Typical Metrics

| Metric | Value |
|--------|-------|
| Routing latency | 0.6–5.3 ms (strategy-dependent) |
| Agent think time | 100–500 ms (model-dependent) |
| Tool dispatch | 10–50 ms (IPC overhead) |
| WORM append | < 1 ms (cryptographic signing) |
| Checkpoint size | 1–10 MB (state-dependent) |

### Reproduce Benchmarks

```bash
cd research/sparse-routing
pip install numpy scipy pytest hypothesis
python -m pytest tests/ -v
python -m experiments.run_experiment
```

Or collect fresh trials:

```bash
python scripts/benchmark_sparse_routing.py --trials 10 --output docs/benchmarks/local.json
```

---

## Glossary

**ReAct:** Reasoning + Acting loop. LLM generates reasoning steps and tool calls iteratively until task completion.

**Expert:** Specialized sub-agent for a specific task type (e.g., code generation, verification).

**Routing Pipeline:** The 11-stage process to select which experts activate for a given task.

**Jordan Transform:** Eigenvalue decomposition used to detect structural invariants in task graphs.

**Jacobian Analysis:** Sensitivity analysis of constraints with respect to task parameters.

**NAND Filtering:** Suppression of conflicting expert combinations (incompatible pairs).

**WORM Ledger:** Write-Once Read-Many immutable log with Ed25519 signatures and Blake3 hash chains.

**Continuity Snapshot:** Atomic checkpoint of environment, seed, filesystem, and model state.

**Deterministic Replay:** Re-execution with identical seed and inputs to reproduce previous behavior.

**Tool Dispatch:** IPC invocation of tool handlers with authorization and timeout enforcement.

**Merge Strategy:** Algorithm for combining outputs from multiple experts (e.g., weighted average, union).

**Tool Registry:** Central registry mapping tool names to handlers, schemas, and authorization policies.

**Sandbox:** Isolated execution environment for untrusted or high-risk tools.

**Path Jail:** File system isolation restricting tool access to specific directories.

**Model Interface:** Backend adapter for different LLM providers (Bedrock, Ollama, etc.).

**Inference Backend:** Pluggable module for model invocation (inference, streaming, etc.).

**Risk Classification:** Label for tools (LOW, MEDIUM, HIGH) determining authorization flow.

---

## Resources & License

### Technical Documentation

- **[ARCHITECTURE.md](docs/repository-reference/ARCHITECTURE.md)** — System design, 4 execution paths, subsystem details
- **[ROUTING.md](docs/ROUTING.md)** — Expert selection, sparse activation, NAND filtering
- **[TOOLS.md](docs/TOOLS.md)** — Tool registry, authorization, IPC dispatch
- **[CONTINUITY.md](docs/CONTINUITY.md)** — State snapshots, deterministic replay
- **[SECURITY.md](docs/SECURITY.md)** — Sandboxing, authorization, path jails
- **[OPERATIONS.md](docs/repository-reference/OPERATIONS.md)** — Deployment, monitoring, troubleshooting

### Repository Reference

- **[REPOSITORY_MAP.md](docs/repository-reference/REPOSITORY_MAP.md)** — Directory structure, 40+ subsystems
- **[DEPENDENCY_GRAPH.md](docs/repository-reference/DEPENDENCY_GRAPH.md)** — 6-layer DAG, 77 packages, 0 circular deps
- **[LANGUAGE_REFERENCE.md](docs/repository-reference/LANGUAGE_REFERENCE.md)** — 16-language distribution, cross-language boundaries
- **[MODULE_REFERENCE.md](docs/repository-reference/MODULE_REFERENCE.md)** — 30 major modules, detailed specifications
- **[INTERFACE_REFERENCE.md](docs/repository-reference/INTERFACE_REFERENCE.md)** — 30+ class signatures, type system

### Research & Proofs

- **[LiquidOps](research/papers/liquidops_kernel.tex)** — Formal semantics of liquid type inference
- **[Entropy](research/papers/sovereign_entropy.tex)** — Formal bounds on agent behavior entropy
- **[SUBLEQ.lean](research/formal/subleq/SUBLEQ.lean)** — Formal proof of SUBLEQ universality
- **[TensorFramework.lean](research/formal/tensor_framework/TensorFramework.lean)** — Formal tensor algebra
- **[Forge Tournament](research/papers/forge_tournament_subleq_to_braid.md)** — Champion proof tournament

### External Resources

- **Hugging Face:** [sovereign-memory-twin](https://huggingface.co/SNAPKITTYWEST/sovereign-memory-twin), [burt-imma](https://huggingface.co/SNAPKITTYWEST/burt-imma)
- **AWS Bedrock:** [Documentation](https://docs.aws.amazon.com/bedrock/)
- **Ollama:** [Documentation](https://github.com/ollama/ollama)
- **Lean 4:** [Documentation](https://lean-lang.org/)

### License

**TRI-LICENSE:** Tripartite licensing structure with three independent terms:

1. **BSL-1.0 (Boost Software License 1.0)** — Source code and implementations
2. **AGPL-3.0 (Affero GPL)** — Network service modifications
3. **MPL-2.0 (Mozilla Public License)** — Optional compatibility tier

See [LICENSE.tri](LICENSE.tri) for full terms. Commercial licensing available.

**Copyright:** Ahmad Ali Parr / SNAPKITTYWEST · Bel Esprit D'Accord Irrevocable Trust.

**Academic Citation:**

```bibtex
@software{sovereign-engine-v2,
  author = {Ahmad Ali Parr},
  title = {Sovereign Engine v2: Multi-Language LLM Agent Framework},
  year = {2026},
  url = {https://github.com/SNAPKITTYWEST/sovereign-engine-v2},
}
```

---

## Rust Verification Workspace (100 Crates)

Alongside the Python engine, `crates/` holds a separate Cargo workspace: a from-scratch, gap-tensor-to-Krull-dimension verification pipeline intended to certify Rust execution traces against Lean 4 proofs. It was scaffolded in bulk (`CRATE_EXPANSION_STATUS.md`) across 10 logical layers/tiers, C001–C100. As of this pass, all 100 crates have a `crates/<ID>/README.md` documenting purpose, public API, pipeline position, and crate-specific findings. The workspace builds cleanly (`cargo build --release`), but "compiles" and "implemented" are not the same thing here — see [Known Gaps / TODO](#known-gaps--todo) below before relying on any specific layer.

At a glance:

- **Layers 0–2 (C001–C030):** gap tensor primitives + arena memory + prime/gap engine. Fully implemented from C021 on; C002–C010 and C012–C020 are unimplemented 7-line scaffolds.
- **Layers 3–5 (C031–C060):** recursive backtracking solver, homological algebra (chain complexes, differentials, resolutions), and the Tor functor. Implemented with doc comments and unit tests throughout, but several crates contain placeholder math (see gaps below).
- **Layer 6 (C061–C070):** Krull dimension over the integers (ideals, Spec(R), prime chains, dimension bounds). Genuinely implemented and tested.
- **Layer 7 (C071–C080):** Lean 4 syntax mirror + obligation-tracking bookkeeping, plus six lemma-library crates. Infrastructure only — no lemma content is populated.
- **Layers 8–9 (C081–C100):** runtime bindings and cross-layer/certification. All 20 crates are unimplemented scaffolds — this is the layer meant to tie Rust execution back to Lean proofs, and it currently contains no code.

### Crate Map

**Tier 0 — Gap Tensor Core (C001–C010)**
| Crate | Name | Description |
|---|---|---|
| [C001](crates/C001/README.md) | gap_tensor_core | Root primitive: `GapTensorNode`, hand-implemented `Ord`/`Hash`. |
| [C002](crates/C002/README.md) | gap_tensor_primes | Scaffold (unimplemented). |
| [C003](crates/C003/README.md) | gap_tensor_spectral | Scaffold (unimplemented). |
| [C004](crates/C004/README.md) | gap_tensor_shape | Scaffold (unimplemented). |
| [C005](crates/C005/README.md) | gap_tensor_equality | Scaffold (unimplemented). |
| [C006](crates/C006/README.md) | gap_tensor_serialization | Scaffold (unimplemented). |
| [C007](crates/C007/README.md) | gap_tensor_invariants | Scaffold (unimplemented). |
| [C008](crates/C008/README.md) | gap_tensor_ordering | Scaffold (unimplemented). |
| [C009](crates/C009/README.md) | gap_tensor_arithmetic | Scaffold (unimplemented). |
| [C010](crates/C010/README.md) | gap_tensor_trace | Scaffold (unimplemented). |

**Tier 1 — Multiplicity Arena (C011–C020)**
| Crate | Name | Description |
|---|---|---|
| [C011](crates/C011/README.md) | multiplicity_arena_core | Raw unsafe bump allocator (`MultiplicityArena`); `destroy()` pairs manual dealloc with `mem::forget` to avoid double-free. |
| [C012](crates/C012/README.md) | multiplicity_arena_layout | Scaffold (unimplemented). |
| [C013](crates/C013/README.md) | multiplicity_arena_allocation | Scaffold (unimplemented). |
| [C014](crates/C014/README.md) | multiplicity_arena_initialization | Scaffold (unimplemented). |
| [C015](crates/C015/README.md) | multiplicity_arena_pointers | Scaffold (unimplemented). |
| [C016](crates/C016/README.md) | multiplicity_arena_ownership | Scaffold (unimplemented). |
| [C017](crates/C017/README.md) | multiplicity_arena_deallocation | Scaffold (unimplemented). |
| [C018](crates/C018/README.md) | multiplicity_arena_failure_handling | Scaffold (unimplemented). |
| [C019](crates/C019/README.md) | multiplicity_arena_statistics | Scaffold (unimplemented). |
| [C020](crates/C020/README.md) | multiplicity_arena_tests_integration | Scaffold (unimplemented). |

**Tier 2 — Prime/Gap Engine (C021–C030)**
| Crate | Name | Description |
|---|---|---|
| [C021](crates/C021/README.md) | prime_predicate | Primality testing (a complete test, despite a doc comment describing it as a prefilter). |
| [C022](crates/C022/README.md) | prime_sieve | Sieve-based prime enumeration. |
| [C023](crates/C023/README.md) | gap_candidate_set | Candidate-set construction. |
| [C024](crates/C024/README.md) | gap_ordering | Ordering analysis over gap candidates. |
| [C025](crates/C025/README.md) | gap_multiplicity | Multiplicity statistics (sample n-1 std-dev convention). |
| [C026](crates/C026/README.md) | gap_absolute_difference | Difference statistics (population n std-dev convention — inconsistent with C025). |
| [C027](crates/C027/README.md) | golden_gap_constraint | Constraint satisfaction; correctly uses saturating arithmetic. |
| [C028](crates/C028/README.md) | verify_gaps_around_primes | Gap verification; assumes odd-prime-only gaps. |
| [C029](crates/C029/README.md) | prime_gap_relationship | `PrimeGapPair` relationship layer; `is_first_occurrence` is near-tautological, untested. |
| [C030](crates/C030/README.md) | prime_gap_tests_integration | End-to-end Tier 2 integration test; returns a bare bool. |

**Tier 3 — Recursive Solver (C031–C040)**
| Crate | Name | Description |
|---|---|---|
| [C031](crates/C031/README.md) | recursive_solver_cursor | Cursor/position state for the backtracking walk. |
| [C032](crates/C032/README.md) | recursion_depth_guard | `RecursionDepthGuard`/`RecursionContext` — RAII-shaped but has no `Drop` impl. |
| [C033](crates/C033/README.md) | recursive_solver_base_case | Base-case detection; `new()` hardcodes `candidates_with_gap(1)`. |
| [C034](crates/C034/README.md) | gap_selection_heuristic | Hybrid scoring heuristic with hand-tuned magic-number weights. |
| [C035](crates/C035/README.md) | recursive_solver_transition | Transition engine; batch API synthesizes placeholder constraint/terminal data. |
| [C036](crates/C036/README.md) | recursive_solver_contradiction | Contradiction detection; `check_no_valid_moves` is a self-documented stub. |
| [C037](crates/C037/README.md) | recursive_solver_backtrack | `BacktrackManager` — a second, non-interoperating backtracking mechanism vs. C031. |
| [C038](crates/C038/README.md) | recursive_solver_selection | Candidate selection logic. |
| [C039](crates/C039/README.md) | recursive_solver_execution_trace | Execution-trace recording. |
| [C040](crates/C040/README.md) | recursive_solver_tests_integration | Tier 3 integration tests. |

**Tier 4 — Chain Complex / Homological Algebra (C041–C050)**
| Crate | Name | Description |
|---|---|---|
| [C041](crates/C041/README.md) | chain_complex_shape | Graded shape of a chain complex. |
| [C042](crates/C042/README.md) | chain_element | Sparse chain elements. |
| [C043](crates/C043/README.md) | differential_operator | The differential operator `d`. |
| [C044](crates/C044/README.md) | squared_zero_verifier | Verifies `d² = 0`; early-exits on first failure, undercounting on failure. |
| [C045](crates/C045/README.md) | projective_module | `ProjectiveModuleHomomorphism::rank()` via Gaussian elimination, no GCD reduction. |
| [C046](crates/C046/README.md) | projective_resolution | Resolutions; `kernel_at` only detects single-generator kernel elements; differentials hardcoded to `[[1]]`. |
| [C047](crates/C047/README.md) | exactness_checker | Kernel/image dimension estimate; pivot loop may undercount rank. |
| [C048](crates/C048/README.md) | homology_computation | `compute_at_degree` self-admits it returns kernel dimension as a placeholder, not true homology. |
| [C049](crates/C049/README.md) | resolution_certification | `verify_squared_zero`/`verify_exactness` are unconditional no-ops — `FullyCertified` currently certifies almost nothing. |
| [C050](crates/C050/README.md) | homological_tests_integration | Tier 4 integration tests; `TestResult::failed()` discards the failing test's name. |

**Tier 5 — Tor Functor (C051–C060)**
| Crate | Name | Description |
|---|---|---|
| [C051](crates/C051/README.md) | tor_group | `TorGroup`, `BTreeMap`-based torsion representation. |
| [C052](crates/C052/README.md) | tensor_product_module | `free_rank()` ignores declared relations — models the free module, not the quotiented tensor product. |
| [C053](crates/C053/README.md) | tensored_resolution | `verify_complex()` doesn't actually check `d²=0`; `TensoredComplexProperties::analyze()` computes nothing. |
| [C054](crates/C054/README.md) | tor_from_resolution | Bridges TorGroup/C048 torsion representations; resolution parameter is never read. |
| [C055](crates/C055/README.md) | tor_functoriality | `verify_tor_zero_universal_property` is a logical tautology, always true. |
| [C056](crates/C056/README.md) | betti_numbers | Betti-number/invariant extraction. |
| [C057](crates/C057/README.md) | induced_tor_map | `is_injective`/`is_surjective` are weak heuristics; `induced_tor_map` ignores the matrix beyond that check. |
| [C058](crates/C058/README.md) | tor_regularity | `regularity()` returns highest Tor degree, not Castelnuovo–Mumford regularity as named; `torsion_complexity` computes a product despite its "sum" doc comment. |
| [C059](crates/C059/README.md) | chain_complex_interface | `from_resolution` ignores the resolution; requires a separate `update_tor()` call. |
| [C060](crates/C060/README.md) | tor_tests_integration | Tier 5 integration tests; bare-bool result, no per-step diagnostics. |

**Tier 6 — Krull Dimension (C061–C070)**
| Crate | Name | Description |
|---|---|---|
| [C061](crates/C061/README.md) | ideal_divisor_set | Ideals as divisor sets over Z. |
| [C062](crates/C062/README.md) | ideal_primality | Primality test for ideals. |
| [C063](crates/C063/README.md) | ideal_maximality | Maximality test for ideals. |
| [C064](crates/C064/README.md) | prime_spectrum | Spec(R) as a set of primes. |
| [C065](crates/C065/README.md) | spectrum_order | Zariski/specialization order. |
| [C066](crates/C066/README.md) | spectrum_chains | `MaximalChains::find_all` — worklist enumeration + subsumed-chain pruning, O(chains²). |
| [C067](crates/C067/README.md) | krull_dimension | Dimension computation, `ringKrullDim`. |
| [C068](crates/C068/README.md) | dimension_upper_bounds | Bounds from standard theorems; `BoundStrategy` enum is declared but never consumed; three constructors are all literally `Self(n)`. |
| [C069](crates/C069/README.md) | krull_certification | `DimensionProof.bounds_satisfied` defaults to `true` unless `check_bounds` is explicitly called — an API misuse trap. |
| [C070](crates/C070/README.md) | krull_tests_integration | Tier 6 integration/certification capstone. |

**Tier 7 — Lean Lemma Libraries & Obligation Framework (C071–C080)**
| Crate | Name | Description |
|---|---|---|
| [C071](crates/C071/README.md) | type_checking_interface | Rust mirror of Lean 4 syntax (`LeanType`/`ProofTerm`/`TypeContext`); `ProofTerm::App(_)` always reports `is_complete() == false`. |
| [C072](crates/C072/README.md) | obligation_management | Generic obligation tracking; `topological_order` does not detect cycles. |
| [C073](crates/C073/README.md) | gap_lemmas_library | Lemma registry for the gap-tensor domain — empty shell, no lemmas populated. |
| [C074](crates/C074/README.md) | memory_lemmas_library | Lemma registry for memory-safety domain — empty shell. |
| [C075](crates/C075/README.md) | recursion_lemmas_library | Lemma registry for recursion/termination domain — empty shell; flagged as highest-value gap to close. |
| [C076](crates/C076/README.md) | homological_lemmas_library | Lemma registry for homological-algebra domain — empty shell. |
| [C077](crates/C077/README.md) | tor_lemmas_library | Lemma registry for Tor-functor domain — empty shell. |
| [C078](crates/C078/README.md) | krull_lemmas_library | Lemma registry for Krull-dimension domain — empty shell. |
| [C079](crates/C079/README.md) | cross_layer_lemmas_library | Cross-layer lemma registry — empty shell. |
| [C080](crates/C080/README.md) | lean_obligation_aggregator | Aggregates obligations across libraries; `extract_tier_from_id` buckets unparseable IDs into tier 0 via `unwrap_or(0)`. |

**Tier 8 — Runtime Bindings (C081–C090)**
| Crate | Name | Description |
|---|---|---|
| [C081](crates/C081/README.md) | runtime_state_snapshot | Scaffold (unimplemented). |
| [C082](crates/C082/README.md) | runtime_execution_trace | Scaffold (unimplemented). |
| [C083](crates/C083/README.md) | runtime_certificate | Scaffold (unimplemented). |
| [C084](crates/C084/README.md) | runtime_binding_gap | Scaffold (unimplemented). |
| [C085](crates/C085/README.md) | runtime_binding_memory | Scaffold (unimplemented). |
| [C086](crates/C086/README.md) | runtime_binding_recursion | Scaffold (unimplemented). |
| [C087](crates/C087/README.md) | runtime_binding_homological | Scaffold (unimplemented). |
| [C088](crates/C088/README.md) | runtime_binding_tor | Scaffold (unimplemented). |
| [C089](crates/C089/README.md) | runtime_binding_krull | Scaffold (unimplemented). |
| [C090](crates/C090/README.md) | runtime_tests_integration | Scaffold (unimplemented). |

**Tier 9 — Cross-Layer Correspondence & Certification (C091–C100)**
| Crate | Name | Description |
|---|---|---|
| [C091](crates/C091/README.md) | cross_layer_types | Scaffold (unimplemented); its dependency list maps one representative crate per layer — useful as an architecture diagram. |
| [C092](crates/C092/README.md) | cross_layer_gap_binding | Scaffold (unimplemented). |
| [C093](crates/C093/README.md) | cross_layer_memory_binding | Scaffold (unimplemented). |
| [C094](crates/C094/README.md) | cross_layer_recursion_binding | Scaffold (unimplemented). |
| [C095](crates/C095/README.md) | cross_layer_homological_binding | Scaffold (unimplemented). |
| [C096](crates/C096/README.md) | cross_layer_tor_binding | Scaffold (unimplemented). |
| [C097](crates/C097/README.md) | cross_layer_krull_binding | Scaffold (unimplemented). |
| [C098](crates/C098/README.md) | counterexample_harness | Scaffold (unimplemented) — would be the negative test proving the certification pipeline catches real mismatches. |
| [C099](crates/C099/README.md) | certification_report_builder | Scaffold (unimplemented). |
| [C100](crates/C100/README.md) | final_certification_report | Scaffold (unimplemented); aggregates all prior tiers. |

### Novel Techniques & Things Worth Knowing

- **`GapTensorNode`'s `Ord`/`Hash` are hand-implemented, not derived** (C001), with fixed field precedence and float-via-`to_bits` hashing to work around `f32` not being `Eq`/`Hash`.
- **`MultiplicityArena::destroy()`** (C011) pairs an explicit `dealloc` with `mem::forget(self)` specifically to avoid a double-free through `Drop` — load-bearing; don't refactor casually. Its `sealed` flag is not enforced (nothing blocks writes to a "sealed" arena), and index access has no bounds checking outside `debug_assert` (release-mode UB on out-of-range index).
- **Z-as-a-PID simplification** (C061–C070): the Krull-dimension layer correctly and deliberately reduces general ideal theory to divisibility arithmetic over `u64`, since Z is a PID — a well-executed simplification, not a broken general implementation.
- **Two independent, non-interoperating backtracking mechanisms** coexist in the recursive-solver tier: C031's lightweight `path_stack` (which the transition engine in C035 actually uses) and C037's full-state-clone `BacktrackManager` (which nothing else uses).
- **`RecursionDepthGuard`** (C032) looks RAII-shaped (`enter()` returns a guard) but has no `Drop` impl — depth is never auto-decremented on scope exit, a trap for anyone assuming real RAII.
- **Three independent, slightly different ad hoc integer-matrix-rank estimators** exist with no shared implementation: C045's `rank()` (Gaussian elimination, no GCD reduction — overflow risk on larger matrices), C047's `compute_kernel`/`image_dimension`, and C048's `estimate_kernel_rank`.
- **Two incompatible torsion representations** — C051's `TorGroup` (`BTreeMap<order, multiplicity>`) vs. C048's flat `Vec<u64>` — are bridged only by order-counting in C054, never unified at the type level.
- **The six Tier 7 lemma-library crates (C073–C078) are a copy-paste-and-retarget template**: identical struct shape, only the domain tag field differs (`gap_size`/`category`/`max_depth`/`lemma_type`/`tor_degree`/`dimension_bound`). A fix to the bookkeeping likely needs to be mirrored across all six.
- **`C091` (cross_layer_types)'s dependency list**, though itself unimplemented, reads as a deliberate one-glance map of the entire four-layer architecture — one representative crate from each of Layers 1–4.
- **`spectrum_chains::MaximalChains::find_all`** (C066) does worklist-based enumeration of all extendable prime chains, then prunes subsumed chains via an order-preserving subsequence check — a reasonable from-scratch O(chains²) algorithm.
- **`golden_gap_constraint`** (C027) correctly uses `saturating_sub`/`saturating_add` to avoid `u64` underflow when tolerance exceeds the target gap — one of the few crates that visibly hardens against edge-case arithmetic.

### Known Gaps / TODO

**Highest priority:**
- **All 20 crates in Layer 8–9 (C081–C100)** are unimplemented stubs. This is the layer meant to certify Rust execution traces against Lean proofs; none of that certification exists in code yet.
- **All six Tier 7 lemma libraries (C073–C078) plus the cross-layer aggregator (C079)** are populated registries with no actual lemma content — no gap, memory-safety, termination, homological, Tor, or Krull-dimension theorem is stated or proven anywhere in the workspace. `recursion_lemmas_library` (C075) is the single highest-value one to close, since an unformalized termination/depth-bound claim for the recursive solver is a real correctness risk, not just missing docs.
- **`resolution_certification`** (C049): `verify_squared_zero` and `verify_exactness` are unconditional no-ops — `FullyCertified` currently means little beyond "has an augmentation and passed a cheap structural check." Should wire to the real C044/C047 verifiers.
- **`homology_computation`** (C048): every "homology group" reported is actually kernel dimension (an upper bound), not true homology rank; torsion is never populated.
- **`tensored_resolution`** (C053): `verify_complex()` doesn't check `d²=0` despite its doc comment claiming to; `TensoredComplexProperties::analyze()` always returns all-false/all-zero, making `is_exact()` unconditionally false.
- **`counterexample_harness`** (C098) being unimplemented means nothing in the repo currently demonstrates the certification pipeline would catch a genuine Rust/Lean mismatch — there's no negative test of the verification machinery itself.

**Scaffolding debt:**
- C002–C010 and C012–C020 (18 of the first 20 crates) are pure unimplemented 7-line scaffolds with no code, no wired dependency on C001/C011 despite the implied relationship, and no tests.
- Several crates carry unused declared dependencies suggesting template-driven scaffolding without pruning: C025–C027 (unused re-exports), C034 (four unused gap-analytics deps, scoring reimplemented by hand instead), C039/C040 (dead Cargo.toml weight), C065 and C069 (unused deps on Tier 0 crates), and every `*_lemmas_library` crate C073–C079 (unused deps on their nominal upstream crates).

**Correctness / precision issues worth a second pair of eyes:**
- `prime_gap_relationship::is_first_occurrence` (C029) is logically near-tautological as written and has zero test coverage.
- `verify_gaps_around_primes` (C028) silently assumes odd-prime-only gaps (`gap >= 2`), and its own test suite dodges the 2→3 prime pair that would fail it.
- Two sibling statistics crates, `gap_multiplicity` (C025) and `gap_absolute_difference` (C026), use inconsistent standard-deviation conventions (sample n-1 vs. population n) with no documentation of the discrepancy.
- `RecursiveSolverCursor::new()` (C033) hardcodes `candidates_with_gap(1)` regardless of the passed-in `GapCandidateSet` — looks like an unfinished parameterization.
- `check_no_valid_moves` (C036) is an explicit self-documented stub conflating "no valid moves" with "is_contradictory."
- `kernel_at` (C046) only detects single-basis-generator kernel elements, not general linear combinations; `is_exact_at` is an explicitly-labeled "simplified" check close to vacuously true; `quotient_resolution`'s differentials are all literally `[[1]]` rather than modeling multiplication by x as claimed.
- `verify_tor_zero_universal_property` (C055) is a logical tautology (`P || !P`) over `usize` inputs — always returns true regardless of correctness.
- `regularity()` (C058) returns "highest Tor degree present," not the standard Castelnuovo–Mumford regularity definition — a naming/semantics mismatch that matters given the pipeline targets commutative algebra; `torsion_complexity`'s doc says "sum" but the code computes a product.
- `krull_certification::DimensionProof.bounds_satisfied` (C069) defaults to `true` and is only updated if `check_bounds` is explicitly called afterward, so `verify()` can report success without any bounds ever having been evaluated.
- `type_checking_interface::ProofTerm::App(_)` (C071) always reports `is_complete() == false` — likely a functional gap if `App` is meant to represent real proof composition.
- `obligation_management::topological_order` (C072) does not detect dependency cycles; a cyclic obligation graph terminates via the visited set but can silently produce an order that violates an edge inside the cycle.
- `lean_obligation_aggregator::extract_tier_from_id` (C080) silently buckets any malformed/unparseable obligation ID into tier 0 via `unwrap_or(0)`, conflating "genuinely tier 0" with "unparseable ID."
- `dimension_upper_bounds` (C068) declares a `BoundStrategy` enum that is never consumed anywhere, and its three bound constructors are all literally identical (`Self(n)`) — intentional as theorem-labeling, but a surprise if someone expects differing numeric behavior.

**Reporting quality:**
- Several integration-test crates (`prime_gap_tests_integration` C030, `tor_tests_integration` C060) return a bare `bool` with no per-step diagnostic, unlike the sibling `TestResult`/`TestSummary` pattern used in C050 — a regression in reporting quality where it exists.
- `TestResult::failed()` (C050) discards the failing test's name (hardcodes `"unknown"`), losing which of the 10 integration scenarios failed in a report.
- Multiple tautological/weak tests across the Krull layer (C063, C065, C069, C070) of the form `assert!(cond || !cond)` verify the call doesn't panic but assert nothing about correctness for that input.
- `gap_absolute_difference`'s `test_absolute_gap_differences` (C026) only asserts non-negativity (trivially true for `u64`), not actual correctness — placeholder-quality test.

---

## Recent Changes

| Commit | Change | Location |
|--------|--------|----------|
| (pending) | Per-crate READMEs for all 100 Rust workspace crates + README "Rust Verification Workspace" section (crate map, novelties, known gaps) via 3-agent documentation swarm | [crates/](crates/), [README.md](#rust-verification-workspace-100-crates) |
| `d7b1dc9` | Comprehensive 3-agent documentation expansion (90K+ words) | [docs/repository-reference/](docs/repository-reference/) |
| [`898dfbe`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/898dfbe), Sep 18 | Resolved paper/formal-file placement | [research/papers/](research/papers/), [research/formal/](research/formal/) |
| [`f97cbd8`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/f97cbd8), Sep 18 | Relocated 60 files (research, training, docs) | [research/](research/), [training/](training/), [docs/](docs/) |
| [`b5a357f`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/b5a357f), Sep 18 | Direct runner, Bedrock backend, authorization | [run.py](run.py), [src/inference/](src/inference/) |
| [`5b6aabe`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/5b6aabe), Sep 7 | Forge Tournament paper + SUBLEQ formalization | [research/papers/](research/papers/), [research/formal/](research/formal/) |

---

**Get started:** [Quick Start](#quick-start) | **Learn more:** [ARCHITECTURE.md](docs/repository-reference/ARCHITECTURE.md) | **Contribute:** [Contributing](#contributing)

Ahmad Ali Parr / SNAPKITTYWEST · Bel Esprit D'Accord Irrevocable Trust.
