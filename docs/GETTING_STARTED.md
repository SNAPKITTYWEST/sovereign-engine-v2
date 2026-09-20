# Getting started

This guide starts with routing code that does not need AWS, an API key, a model download, or a desktop build. Use Python 3.11+ and Git.

## 1. Clone and create an environment

```bash
git clone https://github.com/SNAPKITTYWEST/sovereign-engine-v2.git
cd sovereign-engine-v2
python -m venv .venv
```

Activate it using your shell:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux/macOS
source .venv/bin/activate
```

If activation is unavailable, invoke `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on POSIX instead of `python`. Check the selected environment:

```bash
python -c "import sys; print(sys.executable); print(sys.version)"
python -m pip install numpy scipy pytest hypothesis
```

These four packages support the independent research router. They are not the full engine dependencies.

## 2. Run the reference tests

```bash
cd research/sparse-routing
python -m pytest tests/ -q
cd ../..
```

The recorded run passed 57 tests. See [validation](VALIDATION.md) for scope. A missing `sparse_routing` import usually means the command was run from the wrong directory.

## 3. Collect benchmark results

From the repository root:

```bash
python scripts/benchmark_sparse_routing.py --trials 10 --output docs/benchmarks/sparse-routing-local.json
```

The command prints timing summaries and writes individual trials and environment metadata. It compares structural outputs with the original fixture and permits a `1e-12` route-cost tolerance. It does not overwrite the historical experiment file. See the [benchmark explanation](../README.md#benchmarks).

## 4. Try the engine routing API

Follow the asynchronous expert example in [Routing](ROUTING.md). Unlike the research experiment, it exercises `src.routing.RoutingPipeline`. Both are provider-free, but they solve different routing problems.

## 5. Choose an integration

- [Tools](TOOLS.md): a small registered function with schema validation.
- [Machine runtime](MACHINE_CODE.md): a stack program with a known arithmetic result.
- [Ollama](LOCAL_TRAINING_OLLAMA.md): direct model inference against a running local service.
- [IDE](IDE.md): Windows native client or Electron desktop sources.

For the larger Python engine, install the repository requirements in a separate environment if you want to avoid adding the ML stack to this small test environment:

```bash
python -m pip install -r requirements.txt
```

The root runner selects Bedrock. It is not the recommended first success path: synchronous expert callbacks and agent/continuity interface mismatches remain in the current wiring. See [deployment readiness](PRODUCTION_HARDENING.md) before trying full orchestration. Installing the package alone does not install every runtime dependency.

## When something fails

Capture the command, current directory, Python executable/version, and traceback. Use [Testing and troubleshooting](TESTING.md) to distinguish environment failures from known integration gaps.
