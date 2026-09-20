# Sovereign Engine v2

A multi-language repository for LLM agent execution, sparse expert routing, persistent model memory, compiler and hardware experiments, and formal research.

The Python engine contains an eleven-stage routing pipeline, ReAct agents, a tool registry, continuity storage, and WORM evidence records. Alongside it are a Windows C/C++ IDE, a Haskell compiler package, native assembly and accelerator sources, a Swift training frontend, and independent research implementations. These components have separate build and validation requirements.

**Documentation baseline:** [`898dfbe`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/898dfbe), September 18, 2026. Benchmarks below include the historical experiment artifact and a fresh ten-trial run. Both measure the isolated research router, not end-to-end LLM inference.

## Contents

- [Recent changes](#recent-changes)
- [Starter and technical guides](docs/README.md)
- [Repository map](#repository-map)
- [Execution and routing](#execution-and-routing)
- [Models and training](#models-and-training)
- [Benchmarks](#benchmarks)
- [Getting started](#getting-started)
- [Native builds and research](#native-builds-and-research)
- [Validation boundaries](#validation-boundaries)
- [Documentation and license](#documentation-and-license)

## Recent changes

| Commit | Change | Where to inspect it |
|---|---|---|
| [`898dfbe`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/898dfbe), Sep 18 | Resolved incoming paper/formal-file placement after the reorganization | [Research papers](research/papers/) and [formal sources](research/formal/) |
| [`f97cbd8`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/f97cbd8), Sep 18 | Relocated 60 files with no content insertions or deletions; research and training now have dedicated roots | [research/](research/), [training/](training/), [docs/](docs/) |
| [`b5a357f`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/b5a357f), Sep 18 | Added a direct runner, Bedrock backend, and node authorization artifacts; updated the engine wiring | [run.py](run.py), [bedrock_backend.py](src/inference/bedrock_backend.py), [node_key.py](sovereign/node_key.py) |
| [`5b6aabe`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/5b6aabe), Sep 7 | Added the Forge Tournament paper and SUBLEQ formalization | [Paper](research/papers/forge_tournament_subleq_to_braid.md), [SUBLEQ.lean](research/formal/subleq/SUBLEQ.lean) |
| [`e2f5631`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/e2f5631), Sep 7 | Added Hugging Face-oriented model code, configurations, cards, and a corpus schema | [hf/](hf/) |
| [`d953b98`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/d953b98), Sep 7 | Added AgentFishTank, Call49 substrate, gnostic arithmetic sources, and the BRICK specification | [training/](training/), [the-49th-call/](the-49th-call/), [BRICK](docs/BRICK_PROTOCOL_SPECIFICATION.md) |
| [`cc59e96`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/cc59e96), [`a5395c7`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/a5395c7), Sep 7 | Added versioned checkpoints, hash seals, pruning, quantization, and optional S3 upload workflow | [Checkpoint manager](src/models/checkpoint_manager.py), [workflow](src/models/checkpoint_workflow.py) |
| [`71555f2`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/71555f2), [`3ba399d`](https://github.com/SNAPKITTYWEST/sovereign-engine-v2/commit/3ba399d), Sep 6 | Added recurrent memory and the independent sparse-routing research implementation | [Memory network](src/models/recursive_memory.py), [routing research](research/sparse-routing/) |

## Repository map

| Path | Contents |
|---|---|
| [src/](src/) | Python agents, routing, tools, inference, bridge, continuity, retrieval, model memory, entropy, and runtime modules; also experimental hardware/language sources |
| [ide/](ide/) | Windows C/C++ IDE and its CMake project, desktop sources, and BEAM-style WebAssembly experiments |
| [native/](native/) | NASM runtime, QRA/Jordan/NAND operations, IPC assembly, and C dispatcher |
| [cobalt/](cobalt/) | Cabal package: compiler core, LiquidOps, ISA, mathematics, and LiquidHaskell-oriented modules |
| [kernels/](kernels/) | Rust, CUDA, CUDA-Q, x86, MLIR, TVM, P4, and hardware sources |
| [magma/](magma/), [narm/](narm/), [catn/](catn/) | Protocol, runtime/kernel, and tensor-network implementations with their own tooling |
| [research/formal/](research/formal/) | Lean and Agda sources, including entropy, tensors, GDR drain, SUBLEQ, and gnostic arithmetic |
| [research/papers/](research/papers/) | LiquidOps, entropy, GDR kernels, and Forge Tournament manuscripts |
| [research/sparse-routing/](research/sparse-routing/) | Independent NumPy/SciPy routing package, tests, XML specification, report, and experiment |
| [training/](training/) | AgentFishTank Swift/SceneKit library; formerly `training-frontend/` |
| [hf/](hf/) | Model packaging sources and training-corpus schema |
| [the-49th-call/](the-49th-call/), [runtime/](runtime/) | Call49 substrate and Rust gnostic arithmetic source |
| [sovereign/](sovereign/), [scripts/](scripts/) | Node/release metadata, capability loading, and execution-gate scripts |
| [tests/](tests/), [docs/](docs/) | Engine tests, demonstrations, configuration and subsystem documentation |

The Python research router now lives at `research/sparse-routing/`. The separate Bash reference router remains at [src/routing/sparse-latency-routing/](src/routing/sparse-latency-routing/). They are distinct implementations.

## Execution and routing

[RoutingPipeline](src/routing/pipeline.py) parses a task, builds a symbolic graph, applies Jordan and Jacobian analysis, evaluates constraints, selects sparse expert weights, suppresses registered NAND conflicts, and dispatches experts. A `PipelineTrace` exposes intent, weights, blocked/dead experts, and dispatch outcomes.

```mermaid
flowchart LR
    Input[Task text] --> Parse[Regex and AST]
    Parse --> Graph[Symbolic graph]
    Graph --> Jordan[Jordan transform]
    Jordan --> Jacobian[Jacobian analysis]
    Jacobian --> Constraints[Constraint evaluation]
    Constraints --> Sparse[Sparse activation and expert scores]
    Sparse --> NAND[NAND conflict filter]
    NAND --> Dispatch[Async expert dispatch]
    Dispatch --> Merge[Weighted output merge and trace]
```

The new [run.py](run.py) loads tools, routes a fixed Fibonacci task, then calls a ReAct agent with a `Task` entity. Its model backend calls AWS Bedrock. Routing and generation are sequential operations here: the runner's expert callbacks return task metadata, while the ReAct agent makes the model request.

[BedrockBackend](src/inference/bedrock_backend.py) defaults to region `us-east-1` and model ID `us.anthropic.claude-haiku-4-5-20251001-v1:0`. It uses boto3's credential chain and returns the first response text block. Although its interface accepts `stream`, the implementation uses a non-streaming `invoke_model` call.

[SovereignEngine](src/sovereign.py) also assembles continuity, a WORM ledger, native-tool routing, and an optional shadow agent. The direct runner explicitly bypasses this draft orchestration path; neither path should be inferred to have passed end-to-end validation from this README update.

## Models and training

- **Recursive memory:** [RecursiveMemoryTwinNetwork](src/models/recursive_memory.py) combines a GRU cell and learned memory gate with a persistent latent-state buffer, decay, and L2 normalization. Its harness saves and restores state and processes vectors asynchronously.
- **Checkpoint workflow:** [CheckpointManager and ModelPruner](src/models/checkpoint_manager.py) provide checkpoint metadata and hash chaining, structured/unstructured pruning, and dynamic quantization helpers. [full_checkpoint_workflow](src/models/checkpoint_workflow.py) composes these operations and optionally uploads to S3. Its parameter-count size estimates are not measured inference throughput.
- **Model packaging:** [sovereign-memory-twin](hf/sovereign-memory-twin/) and [burt-imma](hf/burt-imma/) contain modeling code, configurations, and model cards. [sovereign-training-corpus](hf/sovereign-training-corpus/) contains the dataset card and schema. These files alone do not establish published weights or trained-model quality.
- **AgentFishTank:** [training/](training/) contains corpus loading, agent state transitions, task scheduling, and a SceneKit visualization. Its [Swift package](training/Package.swift) targets macOS 14 and iOS 17. Swarm visualization is separate from demonstrated distributed gradient training.
- **Local inference and ASR:** See [local training/Ollama](docs/LOCAL_TRAINING_OLLAMA.md) and [ASR/message bridge](docs/ASR_AND_BRIDGE.md). The current root runner selects Bedrock; those guides describe additional paths.

## Benchmarks

### Committed sparse-routing experiment

Source: [run_experiment.py](research/sparse-routing/experiments/run_experiment.py). Raw data: [results.json](research/sparse-routing/experiments/results.json). Method and limitations: [research report, sections 20–21](research/sparse-routing/docs/report.md).

The fixture is a synthetic directed graph with **7 nodes, 8 edges, and 8 timesteps**. Edge costs vary deterministically with a sinusoidal schedule. A 3×3 Jacobian drops from rank 3 to rank 2 at steps 2 and 3, then recovers. The experiment compares a frozen route, per-step shortest-path selection, and rank-informed topology adaptation.

**Historical measurements from the committed JSON:** each strategy was measured once with `time.perf_counter()` and `tracemalloc`. The artifact does not record CPU, OS, Python/dependency versions, warmups, or repeated-trial distributions. Runtime covers each strategy's complete eight-step execution. Memory is peak traced allocation, not process RSS or GPU memory.

| Strategy | Runtime (ms, measured) | Peak traced bytes (measured) | Mean route cost (simulated) | Final active edges | Committed adaptation steps | Topology changes |
|---|---:|---:|---:|---:|---:|---:|
| Static | 2.318 | 14,227 | 0.645835 | 8 | 0 | 0 |
| Latency-aware | 2.338 | 9,608 | 0.631356 | 8 | 0 | 0 |
| Rank-informed | 12.125 | 43,975 | 0.634892 | 7 | 8 | 1 |

Mean route cost is the arithmetic mean of the eight `per_timestep_route_cost` values. It is a model cost, not measured network latency. Relative to static routing, latency-aware routing reduces mean modeled cost by **2.24%**; rank-informed routing reduces it by **1.69%** and removes **1 of 8 edges (12.5%)**. Rank-informed execution takes **5.23×** the recorded static runtime because it also runs adaptation and verification. This fixture demonstrates a cost/topology tradeoff, not a universal speedup.

The JSON records zero verification failures for all strategies. Only rank-informed routing actually runs the adaptation engine; zero for the other two is not evidence that they underwent the same checks. Rank-informed edge expansion is disabled, and the generous latency threshold does not exercise rejection under tight latency limits.

These numbers do not measure LLM tokens/second, model accuracy, native IPC latency, GPU kernel throughput, or performance against a commercial accelerator.

### Fresh local measurements — September 19, 2026

**57 routing tests passed in 1.35 seconds.** The [repeated benchmark runner](scripts/benchmark_sparse_routing.py) then measured ten trials per strategy after one warmup each. [Raw trials and environment metadata](docs/benchmarks/sparse-routing-2026-09-19.json) are included; the timestamp is September 20 at 02:27 UTC (September 19 locally).

Environment: Windows 11 x86-64, AMD64 Family 25 Model 97 Stepping 2, Python 3.12.10, NumPy 2.5.3, SciPy 1.18.1, pytest 9.1.1, Hypothesis 6.168.0. Trials use a fixed strategy order, without CPU affinity or thread limits. Timings include the original `tracemalloc` instrumentation and exclude module imports.

| Strategy | Median runtime (ms) | Min–max runtime (ms) | Median peak traced bytes |
|---|---:|---:|---:|
| Static | 0.644 | 0.568–1.261 | 7,888 |
| Latency-aware | 0.789 | 0.704–2.318 | 8,132 |
| Rank-informed | 5.275 | 4.740–6.380 | 33,247 |

Every trial matched the historical structural outputs exactly and route costs within relative/absolute tolerance `1e-12`. A static-route cost differed by about `1.11e-16` across environments, so bitwise equality is not the reproduction criterion. These measurements use the same source baseline as the historical artifact; differences in runtime are not evidence of a code optimization.

### Reproduce the routing experiment

Use Python 3.11+ in an isolated environment. From the repository root:

```bash
python -m venv .venv
# POSIX: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install numpy scipy pytest hypothesis
cd research/sparse-routing
python -m pytest tests/ -v
python -m experiments.run_experiment
```

The module invocation keeps this directory on the import path. The experiment **overwrites `experiments/results.json`**. Deterministic model outputs should agree; execution time and allocation measurements vary. Record the commit, machine, interpreter, dependency versions, and trial count alongside any new timings before making comparisons.

To preserve the historical artifact and collect repeated trials instead, run this from the repository root after installing the same four dependencies:

```bash
python scripts/benchmark_sparse_routing.py --trials 10 --output docs/benchmarks/sparse-routing-local.json
```

The wrapper verifies model outputs against the original artifact and records individual trials, runtime summaries, dependency versions, platform, and source commit. The 57-test result above applies only to `research/sparse-routing/tests/`, not to every subsystem in this repository.

## Getting started

### Python engine and Bedrock demo

The repository requires Python 3.11+. It is not dependency-free: the engine imports packages including PyNaCl, Pydantic, and jsonschema, and the default backend imports boto3. The full [requirements.txt](requirements.txt) also includes scientific, embedding, testing, and documentation dependencies.

```bash
git clone https://github.com/SNAPKITTYWEST/sovereign-engine-v2.git
cd sovereign-engine-v2
python -m venv .venv
# POSIX: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

The last command requires AWS credentials and access to the backend's configured Bedrock model and can incur provider charges. The runner currently has a hard-coded demonstration task. The root [pyproject.toml](pyproject.toml) declares `bedrock` and `pytorch` extras but does not list all core runtime dependencies; an editable install alone is not equivalent to installing the requirements file.

For a provider-free starting point, use the isolated routing experiment above. It exercises the research router, not the full agent runtime.

### HTTP bridge

The bridge implementation is [src/bridge/http_server.py](src/bridge/http_server.py):

```bash
python -m src.bridge.http_server
```

See [ASR and bridge documentation](docs/ASR_AND_BRIDGE.md) for dependencies, handler contracts, and known integration gaps. The module uses the default loopback address and does not parse host/port flags. Bridge startup and live inference are separate validation steps from the routing benchmark.

## Native builds and research

Run each command from the repository root unless the block changes directories.

**Windows IDE:** CMake 3.24+, a Windows C/C++ toolchain, and Windows SDK libraries are required. The build definition is at `ide/CMakeLists.txt`, not `ide/native/`.

```powershell
cmake -S ide -B ide/build -G "Visual Studio 17 2022"
cmake --build ide/build --config Release
```

**Cobalt:** inspect [cobalt.cabal](cobalt/cobalt.cabal) for GHC/Cabal and solver dependencies.

```bash
cd cobalt
cabal build
cabal test
```

**Bash reference router:** separate from the Python benchmark.

```bash
bash src/routing/sparse-latency-routing/bin/sparse_router.sh run src/routing/sparse-latency-routing/spec/network.xml
bash src/routing/sparse-latency-routing/tests/run_tests.sh
```

**Research reading:** [LiquidOps](research/papers/liquidops_kernel.tex), [entropy](research/papers/sovereign_entropy.tex), [GDR kernels](research/papers/gdr_kernels.tex), and [Forge Tournament: SUBLEQ to Braid](research/papers/forge_tournament_subleq_to_braid.md). Their source locations changed; manuscript claims and target venues do not establish peer review or implementation validation.

## Validation boundaries

- **Formal status varies by file.** [gdr_drain.lean](research/formal/gdr_drain.lean) and [TensorFramework.lean](research/formal/tensor_framework/TensorFramework.lean) contain `sorry`; [SUBLEQ.lean](research/formal/subleq/SUBLEQ.lean) assumes universality as an axiom; [XInvariant.agda](research/formal/IronicMirror/XInvariant.agda) uses postulates. A repository-wide “zero sorry” or “every layer proved” claim is therefore inaccurate. Native proof checking must specify its file, dependencies, and result.
- **Authorization artifacts are not full gate validation.** [node_key.py](sovereign/node_key.py) loads a nonempty capability and checks `ACTIVE` status when an authorization file exists. It does not itself verify a capability signature or expiry. [scripts/sovereign_gate.py](scripts/sovereign_gate.py) is incomplete in this baseline, including a malformed `except` block and missing verification method definitions. Neither the direct runner nor the shown engine constructor calls that gate.
- **Runner wiring still needs integration tests.** `run.py` provides synchronous expert lambdas, while [AgentDispatch](src/routing/dispatch.py) expects awaitable expert callbacks. `SovereignEngine.run` passes a string and a `context` argument to the agent, whereas the direct runner constructs a `Task`. Documented entry points should not be read as a successful live run.
- **Native and accelerator sources have separate build requirements.** Their presence does not establish compiled kernel performance or equivalence across ISAs. This README's measured table is solely the Python research experiment.
- **Test scopes differ.** [stress_test_no_drift.py](tests/stress_test_no_drift.py) exercises deterministic VM operations; [live_routing_test.py](tests/live_routing_test.py) can fall back to a mock backend. Neither alone establishes live model determinism or a whole-repository pass.

## Documentation and license

Start with the [documentation index](docs/README.md), [getting started](docs/GETTING_STARTED.md), [configuration](docs/CONFIGURATION.md), and [architecture](ARCHITECTURE.md). Technical guides cover [routing](docs/ROUTING.md), [tools](docs/TOOLS.md), [continuity](docs/CONTINUITY.md), [security](docs/SECURITY.md), [desktop builds](docs/IDE.md), and [the machine runtime](docs/MACHINE_CODE.md). See [validation](docs/VALIDATION.md) for executed examples and the [sparse-routing report](research/sparse-routing/docs/report.md) for research methodology.

The repository's licensing document is [LICENSE.tri](LICENSE.tri). Consult it and component-specific metadata for terms; the earlier README's `LICENSE` link and BSL-to-MIT date did not match the tracked licensing file.

Ahmad Ali Parr / SNAPKITTYWEST · Bel Esprit D'Accord Irrevocable Trust.
