# Testing and troubleshooting

Run checks for the subsystem you changed. A syntax check, import, unit test, benchmark, live provider call, native build, and proof check establish different things.

## Research routing

From the repository root, with the environment from [Getting started](GETTING_STARTED.md):

```bash
cd research/sparse-routing
python -m pytest tests/ -q
cd ../..
python scripts/benchmark_sparse_routing.py --trials 10 --output docs/benchmarks/sparse-routing-local.json
```

The runner records versions, source commit, warmups, trials, timings, and traced allocations. The historical artifact lacks some machine metadata; do not interpret a different machine's timings as a code speedup.

## Documentation examples

The Python examples in Routing, Tools, Continuity, Security, and Machine runtime are standalone files run from the repository root. Tool registration additionally needs `jsonschema`. Check [the validation record](VALIDATION.md) for actual executions.

## Other check surfaces

| Surface | Command or location | Scope |
|---|---|---|
| Engine VM stress script | `python tests/stress_test_no_drift.py` | Deterministic operations; read assertions first |
| Trace endpoint examples | [test_routing_trace_endpoints.py](../tests/test_routing_trace_endpoints.py) | Requires inspection of server assumptions |
| Live routing demonstration | [live_routing_test.py](../tests/live_routing_test.py) | Can use a mock fallback |
| Bash router | `bash src/routing/sparse-latency-routing/tests/run_tests.sh` | Separate reference implementation |
| Cobalt | `cabal build`, `cabal test` inside `cobalt/` | Haskell package and its declared suites |
| Desktop | `npm run verify` inside `ide/desktop/` | TypeScript/build and Jest, after `npm ci` |
| Native IDE | [IDE guide](IDE.md) | Windows CMake project |
| Formal sources | [research/formal/](../research/formal/) | Requires individual proof-project dependencies |

These are check entry points, not a claim that all currently pass.

## Troubleshooting

| Symptom | Check |
|---|---|
| `No module named sparse_routing` | Run research tests from `research/sparse-routing`; use the root wrapper for repeated benchmarks |
| Missing `numpy`, `scipy`, `pytest`, or `hypothesis` | Install the research requirements with the selected environment's `python -m pip` |
| Missing `aiohttp` | Provider/bridge modules use it; it is absent from the root requirements list |
| “object dict can't be used in await” / awaitable error | Expert callbacks must be async; see Routing |
| Unexpected `context` argument or missing continuity task method | Known engine integration mismatch; see deployment readiness |
| Bedrock credential/model error | Confirm the backend's configured region/model and your account access; no live call is part of the offline benchmark |
| Ollama connection or model error | Confirm the service URL and a locally installed model; inspect direct provider health/list methods |
| Bridge ignores `--port` | Its module entrypoint does not parse CLI flags |
| Native CMake failure on another OS | The IDE's CMake project explicitly requires Windows |
| Desktop Vite input not found | Check that the declared `desktop/index.html` renderer exists in your checkout |

Record failures without replacing them with simulated success output. Keep test data and benchmark artifacts separate from credentials and trained model weights.
