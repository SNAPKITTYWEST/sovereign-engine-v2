# Sparse Routing, Jacobian Rank, and Recursive Tensor Adaptation

A Python reference implementation and formal research report for a
deterministic sparse-routing framework in which measurable structural and
performance signals (latency, Jacobian rank, sparsity) can drive explicitly
constrained topology adaptation.

This is a companion, independent Python implementation to a separate Bash
reference engine; the two are cross-validated against the same canonical
5-node/5-edge topology (see `docs/report.md`, Section 9).

**Read `docs/report.md` first.** It is the primary deliverable: the full
research report (25 sections) that defines every term used here
mathematically or operationally, states what is FORMALLY DEFINED vs.
MECHANICALLY CHECKED vs. NUMERICALLY TESTED vs. EMPIRICALLY MEASURED vs.
HEURISTIC/HYPOTHESIS, and reports the controlled experiment's real,
measured results. This README only covers how to run the code.

## Requirements

- Python 3.11+ (developed and tested on 3.11)
- `numpy`, `scipy`, `pytest`, `hypothesis`

Install:

```bash
pip install --break-system-packages numpy scipy pytest hypothesis
```

(No `requirements.txt` is bundled since the project has no other
dependencies; the four packages above are the complete list.)

## Layout

```
sparse_routing/          the package (8 modules, see report Section 12)
  model/graph.py            Node, Edge, SparseGraph (I1-I3, I6)
  tensor/node.py             TensorNode, recursion bound (I4, I5)
  rank/jacobian.py           finite-difference Jacobian, exact/numerical/structural rank, I7
  routing/dijkstra.py        deterministic shortest paths
  routing/latency.py         LatencyState, RoutingState
  adaptation/engine.py       observe/measure/estimate/propose/verify/commit (I9)
  parser/                    lexer -> AST -> validated model (report Section 10)
  serialization/state.py     canonical payload, SHA-256 state hash (I8)
  verification/invariants.py aggregate I1-I9 checker

spec/network.xsd          canonical XML schema
spec/network.xml           canonical example instance (matches the Python model field-for-field)
tests/                     pytest suite, 57 tests incl. 5 Hypothesis property tests
experiments/run_experiment.py   controlled experiment (static vs latency-aware vs rank-informed)
experiments/results.json        real, measured output of the experiment (not hand-typed)
docs/report.md             the research report -- start here
```

The package is run in place (no `setup.py`/`pyproject.toml` is bundled);
every command below is run from this directory with `PYTHONPATH=.`.

## Reproduction instructions

All three steps below are exactly how the numbers quoted in `docs/report.md`
were produced. Re-running them is expected to reproduce the schema
validation result, all 57 test outcomes, and the experiment's *simulated*
columns exactly; the experiment's two *measured* columns
(`runtime_seconds`, `peak_memory_bytes`) will vary slightly run to run and
machine to machine, since they depend on real wall-clock execution, not on
the deterministic model (see `docs/report.md` Section 20).

1. Validate the canonical XML against its schema:

   ```bash
   xmllint --noout --schema spec/network.xsd spec/network.xml
   # expected output: "spec/network.xml validates"
   ```

2. Run the test suite:

   ```bash
   PYTHONPATH=. python3 -m pytest tests/ -v
   # expected: 57 passed
   ```

3. Run the controlled experiment:

   ```bash
   PYTHONPATH=. python3 experiments/run_experiment.py
   # writes experiments/results.json and prints a per-strategy summary
   ```

## Known limitations

See `docs/report.md` Section 21 for the full discussion (Jacobian cost,
numerical rank instability, latency measurement noise, sparse graph search
complexity, recursive tensor overhead, Python performance overhead,
simulated-vs-physical latency, and heuristic-vs-formal criteria). One
finding is highlighted here because it directly bears on the project's
central claim: in the controlled experiment, RANK-INFORMED routing
produces a *higher* summed route cost than LATENCY-AWARE routing over the
8-timestep run (5.0791 vs. 5.0508) because an edge pruned on a genuine,
verified rank-deficiency signal at one timestep turns out, several
timesteps later, to have been on the timestep-local latency-optimal path.
This is reported as direct evidence that Jacobian rank is a *routing
signal*, not an optimization guarantee -- consistent with the report's
non-negotiable framing (Section 23) and not smoothed over.
