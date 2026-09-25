# Documentation validation record

Validated September 19, 2026 local time (September 20 UTC), against implementation baseline `898dfbe` and documentation/benchmark commit `cc082b9` plus this Markdown update. No implementation source changed in this cleanup.

Environment: Windows 11 x86-64, Python 3.12.10, NumPy 2.5.3, SciPy 1.18.1, pytest 9.1.1, Hypothesis 6.168.0, PyTorch 2.14.0, jsonschema 4.26.0.

## Executed checks

| Check | Result |
|---|---|
| Research router: `python -m pytest tests/ -q` from `research/sparse-routing` | 57 passed in 0.50 seconds |
| [Routing example](ROUTING.md) | Two active experts, two successes, no failures |
| [Tool example](TOOLS.md) | Input/output schemas accepted; result `{"value": 5}` |
| [Continuity example](CONTINUITY.md) | Step 1 and THINKING inode flag observed in a temporary directory |
| [Path boundary example](SECURITY.md) | In-root path accepted; outside path rejected |
| [VM arithmetic example](MACHINE_CODE.md) | Result 5 within the instruction budget |
| [BURT-IMMA example](../hf/burt-imma/README.md) | Finite 8-element output; softmax weights sum to one |
| [Memory checkpoint example](../hf/sovereign-memory-twin/README.md) | Initialized latent state restored exactly from a temporary checkpoint |
| [Corpus-schema example](../hf/sovereign-training-corpus/README.md) | Schema checked and minimal document accepted |

The eight examples were extracted from their Markdown Python fences and executed from the directories specified in each guide. Temporary data was confined to temporary directories. No model downloads or remote provider requests were needed.

The prior [ten-trial benchmark artifact](benchmarks/sparse-routing-2026-09-19.json) remains unchanged. Its timings and method are explained in the [root README](../README.md#benchmarks).

## Not established by these checks

These results do not validate full agent orchestration, live Bedrock/Ollama inference, HTTP startup or authorization, native/Electron/Swift builds, GPU throughput, ASR training, or native Lean/Agda proof checking. See [deployment readiness](PRODUCTION_HARDENING.md) for known integration issues and [testing](TESTING.md) for subsystem entrypoints.

Examples describe initialized models and structural checks; they do not demonstrate trained-model quality or a published dataset.
