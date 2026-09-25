# Documentation

Start with [Getting started](GETTING_STARTED.md) for a local, provider-free example. All commands use the repository root unless a guide explicitly changes directories.

| Task | Guide |
|---|---|
| Set up Python and run the routing tests | [Getting started](GETTING_STARTED.md) |
| Understand subsystem boundaries | [Architecture](../ARCHITECTURE.md) |
| Add asynchronous experts and inspect traces | [Routing](ROUTING.md) |
| Register and validate a tool | [Tools](TOOLS.md) |
| Choose actual configuration fields | [Configuration](CONFIGURATION.md) |
| Inspect persistence and recovery interfaces | [Continuity](CONTINUITY.md) |
| Understand path checks, approvals, and evidence records | [Security](SECURITY.md) |
| Use the local provider adapter | [Ollama](LOCAL_TRAINING_OLLAMA.md) |
| Inspect HTTP contracts and ASR sources | [ASR and bridge](ASR_AND_BRIDGE.md) |
| Build a desktop client | [IDE](IDE.md) |
| Run the stack VM and navigate native sources | [Machine runtime](MACHINE_CODE.md) |
| Run checks and interpret failures | [Testing and troubleshooting](TESTING.md) |
| Review deployment gaps | [Deployment readiness](PRODUCTION_HARDENING.md) |
| Read the repository-sealing design | [BRICK specification](BRICK_PROTOCOL_SPECIFICATION.md) |

## Evidence conventions

Examples marked **local example** use repository code and no external provider. The [validation record](VALIDATION.md) identifies the examples actually executed. Provider examples require their service and credentials; they are interface examples unless a run is recorded.

The [benchmark artifact](benchmarks/sparse-routing-2026-09-19.json) records ten trials per strategy at source commit `898dfbe`. Test passes, native builds, proof checks, and live provider results are separate evidence. There is no whole-repository production certification.

Research manuscripts remain under [research/](../research/). Their hypotheses and specifications are not substitutes for runtime results. Obsolete sprint checklists and generated completion reports have been removed from the current documentation; their previous contents remain in Git history.
