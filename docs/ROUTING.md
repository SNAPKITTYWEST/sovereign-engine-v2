# Routing technical guide

The repository contains three separate routing paths:

| Path | Input and responsibility |
|---|---|
| [Engine pipeline](../src/routing/pipeline.py) | Task text → expert weights → asynchronous dispatch |
| [Python research router](../research/sparse-routing/) | Synthetic graph, edge costs, Jacobian rank → verified topology adaptation |
| [Bash reference router](../src/routing/sparse-latency-routing/) | XML model → shell-based invariant checks and routing |

## Engine pipeline

`route_with_trace(text, context)` returns a `PipelineTrace`; `route(text, context)` returns its dispatch result. The eleven named stages are regex parsing, AST building, symbolic graph construction, Jordan transformation, Jacobian analysis, constraint evaluation, sparse activation, expert scoring, NAND conflict filtering, dispatch, and merge.

### Local example: asynchronous experts

Save as `routing_example.py` in the repository root and run `python routing_example.py`:

```python
import asyncio
from src.routing.pipeline import RoutingPipeline

async def coder(text, context):
    return {"answer": "code route", "input": text}

async def general(text, context):
    return {"answer": "general route", "input": text}

async def main():
    pipeline = RoutingPipeline(
        experts={"coder": coder, "general": general},
        top_k=2,
        expert_timeout_ms=1000,
    )
    trace = await pipeline.route_with_trace("Write a Python function", {})
    print(trace.summary())
    assert trace.dispatch.active_count > 0
    assert trace.dispatch.success_count == trace.dispatch.active_count
    assert not trace.dispatch.failed_experts

asyncio.run(main())
```

An expert must accept `(text, context)` and return an awaitable producing a dictionary. A synchronous lambda returning a dictionary does not satisfy the dispatcher contract. Expert context includes the parsed task and routing weights.

## Tuning and diagnostics

- `top_k` controls sparse expert selection.
- `expert_timeout_ms` controls the per-expert dispatcher timeout, not the entire agent task.
- `merge_strategy` selects the merger; inspect [dispatch.py](../src/routing/dispatch.py) for `weighted_concat`, `weighted_avg`, `highest_weight`, and `ensemble_text`.
- `add_nand_conflict(a, b)` registers a conflict between two expert names.
- `add_constraint(constraint)` appends a rule to [ConstraintEval](../src/routing/constraints.py); inspect that rule interface before passing a callback.

Inspect `trace.summary()` for intent, confidence, blocked/dead experts, active weights, and failures. Zero successes does not prove the provider failed: the selected callback may be invalid or timed out.

## Research experiment

Read the [research report](../research/sparse-routing/docs/report.md) for the graph model, rank estimator, proposal/verification/commit sequence, and limitations. Its simulated route cost is not the engine pipeline's latency or model throughput. Reproduction commands and timing metadata are in [Testing](TESTING.md).
