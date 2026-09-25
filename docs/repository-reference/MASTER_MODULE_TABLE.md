# Master Module Table — Sovereign Engine v2

| Module | Directory | Language | Purpose | Entry Point | Dependencies | Tests | LOC |
|--------|-----------|----------|---------|---|---|---|---|
| **agents.react** | src/agents/ | Python | ReAct reasoning + tool calling | `async run(task)` | models, tools, inference, routing | live_routing_test.py | 538 |
| **agents.mcts** | src/agents/ | Python | Monte Carlo tree search | `async search()` | models, sandbox | stress_test.py | 427 |
| **agents.shadow** | src/agents/ | Python | Anomaly detection observer | `observe_*()` | core.evidence | implicit | 538 |
| **routing.pipeline** | src/routing/ | Python | 11-stage MoE routing | `async route()` | jordan_moe, jacobian, constraints | live_routing_test.py | 196 |
| **routing.jordan_moe** | src/routing/ | Python | Jordan algebra MoE | `route()` | numpy, scipy | routing tests | 600+ |
| **routing.jacobian** | src/routing/ | Python | Jacobian sensitivity | `analyze()` | numpy, scipy | routing tests | 150+ |
| **inference.bedrock** | src/inference/ | Python | AWS Bedrock backend | `async generate()` | boto3, models | implicit | 56 |
| **inference.quantum_moe** | src/inference/ | Python | Quantum-inspired MoE | `route()` | numpy, scipy | implicit | 150+ |
| **models.entities** | src/models/ | Python | Domain entities | Constructor | pydantic | entity tests | 481 |
| **models.checkpoint** | src/models/ | Python | Checkpoint management | `save()`, `load()` | core.storage, crypto | implicit | 150+ |
| **models.state_machines** | src/models/ | Python | Agent state machines | transition() | enum | implicit | 480+ |
| **models.burt_imma** | src/models/ | Python | BURT-Imma model | forward() | torch, numpy | implicit | 240+ |
| **continuity.manager** | src/continuity/ | Python | Continuity orchestrator | `transition()` | all continuity.* | implicit | 180+ |
| **continuity.checkpoint** | src/continuity/ | Python | Checkpoint I/O | `save()`, `restore()` | core.crypto, storage | implicit | 150+ |
| **continuity.replay** | src/continuity/ | Python | Execution replay | `async replay()` | checkpoint | implicit | 250+ |
| **runtime.sovereign_machine** | src/runtime/ | Python | Virtual machine | `async execute()` | machine.*, continuity | implicit | 180+ |
| **runtime.vm_executor** | src/runtime/machine/ | Python | Bytecode execution | `execute_bytecode()` | binary_ir | implicit | 1200+ |
| **runtime.dsl_compiler** | src/runtime/machine/ | Python | DSL→bytecode | `compile()` | binary_ir | implicit | 1800+ |
| **tools.registry** | src/tools/ | Python | Tool registration | `register()` | jsonschema | implicit | 400+ |
| **tools.loader** | src/tools/ | Python | Tool loader | `load_all_tools()` | all tools.* | implicit | 1200+ |
| **retrieval.pipeline** | src/retrieval/ | Python | RAG pipeline | `async retrieve()` | vector_store, embeddings | implicit | 300+ |
| **core.types** | src/core/ | Python | Bounded types | Type constructors | pydantic | implicit | 350 |
| **core.crypto** | src/core/ | Python | Cryptography | `hash_content()` | cryptography | implicit | 100+ |
| **resonance.fabric** | src/resonance/ | Python | Semantic composition | `weave()` | numpy | implicit | 150+ |
| **entropy.worm** | src/entropy/ | Python | WORM ledger | `append()` | json, hashlib | implicit | 50+ |
| **scanner.ast_analyzer** | src/scanner/ | Python | AST analysis | `analyze_file()` | ast | implicit | 400+ |
| **CATN** | catn/src/ | Rust | Cellular automata | main() | cuda, tenferro_tensor | implicit | 400 |
| **Cobalt** | cobalt/src/ | Haskell | DSL compiler | main() | parsePrologRules | implicit | 150 |
| **IDE Native** | ide/native/ | C | Windows native layer | main() | Win32 API | desktop tests | 28.3K |
| **IDE Desktop** | ide/desktop/ | TypeScript | Electron frontend | createWindow() | electron, node | desktop tests | 2.5K |

**Summary**: 30 major modules verified across 7 languages. Total: 98,418 LOC.

