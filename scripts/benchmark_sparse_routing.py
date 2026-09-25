"""Repeat the existing synthetic experiment; preserve its historical results.json."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import platform
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "sparse-routing"))

from experiments.run_experiment import run_static, run_latency_aware, run_rank_informed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")

    historical = json.loads(
        (ROOT / "research/sparse-routing/experiments/results.json").read_text()
    )
    measured_fields = {"runtime_seconds", "peak_memory_bytes", "per_timestep_route_cost"}

    def deterministic(result):
        return {k: v for k, v in result.items() if k not in measured_fields}

    functions = [run_static, run_latency_aware, run_rank_informed]
    for function in functions:
        function()  # One unrecorded warmup per strategy.
    trials = {function.__name__: [] for function in functions}
    # Fixed order in every trial, matching the original experiment.
    for _ in range(args.trials):
        for function, expected in zip(functions, historical["results"]):
            result = asdict(function())
            costs = result["per_timestep_route_cost"]
            expected_costs = expected["per_timestep_route_cost"]
            costs_match = len(costs) == len(expected_costs) and all(
                math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
                for a, b in zip(costs, expected_costs)
            )
            if deterministic(result) != deterministic(expected) or not costs_match:
                raise RuntimeError(f"Model outputs changed: {result['strategy']}")
            trials[function.__name__].append(result)

    summaries = []
    for records in trials.values():
        times = [r["runtime_seconds"] * 1000 for r in records]
        memories = [r["peak_memory_bytes"] for r in records]
        summaries.append({
            "strategy": records[0]["strategy"],
            "median_runtime_ms": statistics.median(times),
            "min_runtime_ms": min(times),
            "max_runtime_ms": max(times),
            "median_peak_traced_bytes": statistics.median(memories),
        })
    payload = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "dependencies": {name: importlib.metadata.version(name)
                         for name in ("numpy", "scipy", "pytest", "hypothesis")},
        "trials_per_strategy": args.trials,
        "warmups_per_strategy": 1,
        "strategy_order": ["static", "latency_aware", "rank_informed"],
        "measurement": "Existing perf_counter and tracemalloc instrumentation; complete eight-step strategy, excluding imports. Peak traced allocation is not RSS. Fixed order; no CPU affinity or thread limits imposed.",
        "deterministic_outputs_match_historical": True,
        "route_cost_comparison": "math.isclose with relative and absolute tolerance 1e-12; all other model fields compared exactly",
        "summary": summaries,
        "trials": trials,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
