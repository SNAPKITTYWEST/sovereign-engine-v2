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

## Recent Changes

| Commit | Change | Location |
|--------|--------|----------|
| `d7b1dc9` | Comprehensive 3-agent documentation expansion (90K+ words) | [docs/repository-reference/](docs/repository-reference/) |
| [`898dfbe`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/898dfbe), Sep 18 | Resolved paper/formal-file placement | [research/papers/](research/papers/), [research/formal/](research/formal/) |
| [`f97cbd8`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/f97cbd8), Sep 18 | Relocated 60 files (research, training, docs) | [research/](research/), [training/](training/), [docs/](docs/) |
| [`b5a357f`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/b5a357f), Sep 18 | Direct runner, Bedrock backend, authorization | [run.py](run.py), [src/inference/](src/inference/) |
| [`5b6aabe`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/5b6aabe), Sep 7 | Forge Tournament paper + SUBLEQ formalization | [research/papers/](research/papers/), [research/formal/](research/formal/) |

---

**Get started:** [Quick Start](#quick-start) | **Learn more:** [ARCHITECTURE.md](docs/repository-reference/ARCHITECTURE.md) | **Contribute:** [Contributing](#contributing)

Ahmad Ali Parr / SNAPKITTYWEST · Bel Esprit D'Accord Irrevocable Trust.
