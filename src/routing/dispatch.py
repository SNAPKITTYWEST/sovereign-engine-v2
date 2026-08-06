"""
Stage 10 + 11: AgentDispatch + MergeOutput

AgentDispatch:
  Takes the sparse routing weights and fires the active experts.
  Each expert is an async callable: (input, context) -> output.
  Experts run concurrently (asyncio.gather).
  Timeout per expert — stalled experts are dropped, not waited on.

MergeOutput:
  Combines expert outputs using their routing weights.
  Strategy options:
    - weighted_concat:  concatenate with weight annotation
    - weighted_avg:     average numeric fields by weight
    - highest_weight:   return only the top-weighted output
    - ensemble_text:    join text outputs with weight-proportional prominence
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from .sparse import RoutingWeights


# ==========================================
# Expert type
# ==========================================

Expert = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


# ==========================================
# Dispatch
# ==========================================

@dataclass
class ExpertResult:
    expert_name: str
    weight: float
    output: dict[str, Any] | None
    success: bool
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class DispatchResult:
    expert_results: list[ExpertResult]
    active_count: int
    success_count: int
    failed_experts: list[str]
    routing_weights: RoutingWeights
    merged_output: dict[str, Any]


class AgentDispatch:
    """
    Stage 10: Fire active experts concurrently.
    """

    def __init__(
        self,
        experts: dict[str, Expert],
        timeout_ms: int = 30000,
        merge_strategy: str = "weighted_concat"
    ):
        self.experts = experts
        self.timeout_s = timeout_ms / 1000.0
        self.merge_strategy = merge_strategy
        self._merger = MergeOutput()

    async def dispatch(
        self,
        input_text: str,
        context: dict[str, Any],
        routing: RoutingWeights
    ) -> DispatchResult:

        active = routing.active_experts
        tasks = []

        for expert_name in active:
            weight = routing.weights.get(expert_name, 0.0)
            if weight < 1e-6:
                continue

            expert_fn = self.experts.get(expert_name)
            if expert_fn is None:
                continue

            task = self._run_expert(expert_name, weight, expert_fn, input_text, context)
            tasks.append(task)

        if not tasks:
            return DispatchResult(
                expert_results=[],
                active_count=0,
                success_count=0,
                failed_experts=[],
                routing_weights=routing,
                merged_output={"error": "No active experts after dispatch"}
            )

        results: list[ExpertResult] = await asyncio.gather(*tasks)

        failed = [r.expert_name for r in results if not r.success]
        succeeded = [r for r in results if r.success]

        merged = self._merger.merge(succeeded, self.merge_strategy)

        return DispatchResult(
            expert_results=results,
            active_count=len(tasks),
            success_count=len(succeeded),
            failed_experts=failed,
            routing_weights=routing,
            merged_output=merged
        )

    async def _run_expert(
        self,
        name: str,
        weight: float,
        fn: Expert,
        input_text: str,
        context: dict[str, Any]
    ) -> ExpertResult:
        import time
        t0 = time.monotonic()
        try:
            output = await asyncio.wait_for(
                fn(input_text, context),
                timeout=self.timeout_s
            )
            latency = (time.monotonic() - t0) * 1000
            return ExpertResult(
                expert_name=name,
                weight=weight,
                output=output,
                success=True,
                latency_ms=latency
            )
        except asyncio.TimeoutError:
            return ExpertResult(
                expert_name=name,
                weight=weight,
                output=None,
                success=False,
                error=f"Timeout after {self.timeout_s}s"
            )
        except Exception as e:
            return ExpertResult(
                expert_name=name,
                weight=weight,
                output=None,
                success=False,
                error=str(e)
            )


# ==========================================
# Merge Output
# ==========================================

class MergeOutput:
    """
    Stage 11: Combine expert outputs using routing weights.
    """

    def merge(
        self,
        results: list[ExpertResult],
        strategy: str = "weighted_concat"
    ) -> dict[str, Any]:

        if not results:
            return {"output": None, "experts": []}

        if strategy == "highest_weight":
            return self._highest_weight(results)
        elif strategy == "weighted_avg":
            return self._weighted_avg(results)
        elif strategy == "ensemble_text":
            return self._ensemble_text(results)
        else:
            return self._weighted_concat(results)

    def _weighted_concat(self, results: list[ExpertResult]) -> dict[str, Any]:
        """
        Return all outputs annotated with their weights.
        Agents downstream can decide how to use them.
        """
        total_weight = sum(r.weight for r in results)

        outputs = []
        for r in sorted(results, key=lambda x: x.weight, reverse=True):
            normalized_weight = r.weight / max(total_weight, 1e-6)
            outputs.append({
                "expert": r.expert_name,
                "weight": normalized_weight,
                "output": r.output,
                "latency_ms": r.latency_ms
            })

        # Primary output = highest weighted expert's output
        primary = results[0].output if results else {}

        return {
            "output": primary,
            "expert_outputs": outputs,
            "strategy": "weighted_concat",
            "expert_count": len(results)
        }

    def _highest_weight(self, results: list[ExpertResult]) -> dict[str, Any]:
        best = max(results, key=lambda r: r.weight)
        return {
            "output": best.output,
            "expert": best.expert_name,
            "weight": best.weight,
            "strategy": "highest_weight"
        }

    def _weighted_avg(self, results: list[ExpertResult]) -> dict[str, Any]:
        """
        Average numeric values across outputs, weighted by routing weight.
        Non-numeric keys taken from highest-weight expert.
        """
        total_weight = sum(r.weight for r in results) or 1.0
        merged: dict[str, Any] = {}

        # Collect all keys
        all_keys: set[str] = set()
        for r in results:
            if r.output:
                all_keys.update(r.output.keys())

        for key in all_keys:
            # Try weighted average of numeric values
            numeric_vals = []
            for r in results:
                if r.output and key in r.output:
                    val = r.output[key]
                    if isinstance(val, (int, float)):
                        numeric_vals.append((val, r.weight))

            if numeric_vals:
                merged[key] = sum(v * w for v, w in numeric_vals) / total_weight
            else:
                # Non-numeric: take from highest-weight expert
                best = max(results, key=lambda r: r.weight)
                if best.output and key in best.output:
                    merged[key] = best.output[key]

        merged["strategy"] = "weighted_avg"
        return merged

    def _ensemble_text(self, results: list[ExpertResult]) -> dict[str, Any]:
        """
        Join text outputs in weight order.
        Higher-weight experts appear first.
        """
        sorted_results = sorted(results, key=lambda r: r.weight, reverse=True)
        parts = []

        for r in sorted_results:
            if r.output:
                text = r.output.get("text") or r.output.get("content") or str(r.output)
                pct = int(r.weight * 100)
                parts.append(f"[{r.expert_name} {pct}%]: {text}")

        return {
            "output": "\n\n".join(parts),
            "strategy": "ensemble_text",
            "expert_count": len(results)
        }
