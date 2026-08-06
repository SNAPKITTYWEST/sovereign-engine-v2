"""
Routing Trace Collector for C IDE Bridge
Part of SOVEREIGN PYTHON LLM ENGINE

Exposes routing decisions to the C frontend via HTTP.
The C IDE polls this endpoint to display live routing state.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from collections import deque
from typing import Any
import json
import time


@dataclass
class RoutingTrace:
    """Single routing decision trace."""
    timestamp: str
    input_text: str           # first 64 chars
    intent: str               # classified intent
    active_experts: list[str] # which experts fired
    weights: dict[str, float] # expert -> weight
    jordan_stable: bool       # did Jordan fixed-point converge?
    spectral_gap: float       # eigenvalue separation
    worm_sealed: bool         # was decision WORM-sealed?
    ere_passed: bool          # did ERE gates pass?
    latency_ms: float         # routing latency
    qra_glyph: str           # QRA glyph classification (Pi/Gamma/Delta/Lambda/Omega/Psi)
    provider: str             # which provider was selected

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, handling nested types."""
        return asdict(self)


class TraceCollector:
    """
    Ring buffer of recent routing traces.
    C IDE polls GET /routing/traces to get latest N.
    """

    def __init__(self, max_traces: int = 100):
        self._traces: deque[RoutingTrace] = deque(maxlen=max_traces)
        self._total_count = 0
        self._expert_usage = {}
        self._glyph_distribution = {}
        self._provider_counts = {}

    def record(self, trace: RoutingTrace) -> None:
        """Record a routing trace and update statistics."""
        self._traces.append(trace)
        self._total_count += 1

        # Update expert usage counts
        for expert in trace.active_experts:
            self._expert_usage[expert] = self._expert_usage.get(expert, 0) + 1

        # Update glyph distribution
        self._glyph_distribution[trace.qra_glyph] = \
            self._glyph_distribution.get(trace.qra_glyph, 0) + 1

        # Update provider counts
        self._provider_counts[trace.provider] = \
            self._provider_counts.get(trace.provider, 0) + 1

    def get_latest(self, n: int = 10) -> list[dict[str, Any]]:
        """Return the last N traces as dicts."""
        traces = list(self._traces)[-n:]
        return [t.to_dict() for t in traces]

    def get_all(self) -> list[dict[str, Any]]:
        """Return all traces as dicts."""
        return [t.to_dict() for t in self._traces]

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate routing statistics."""
        if not self._traces:
            return {
                "total_routed": 0,
                "avg_latency_ms": 0.0,
                "expert_usage": {},
                "glyph_distribution": {},
                "provider_counts": {},
                "jordan_stable_rate": 0.0,
                "ere_pass_rate": 0.0,
                "worm_seal_rate": 0.0,
                "avg_spectral_gap": 0.0
            }

        latencies = [t.latency_ms for t in self._traces]
        jordan_stable_count = sum(1 for t in self._traces if t.jordan_stable)
        ere_pass_count = sum(1 for t in self._traces if t.ere_passed)
        worm_seal_count = sum(1 for t in self._traces if t.worm_sealed)
        spectral_gaps = [t.spectral_gap for t in self._traces]

        return {
            "total_routed": self._total_count,
            "buffer_size": len(self._traces),
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "min_latency_ms": min(latencies) if latencies else 0.0,
            "max_latency_ms": max(latencies) if latencies else 0.0,
            "expert_usage": self._expert_usage,
            "glyph_distribution": self._glyph_distribution,
            "provider_counts": self._provider_counts,
            "jordan_stable_rate": jordan_stable_count / len(self._traces) if self._traces else 0.0,
            "ere_pass_rate": ere_pass_count / len(self._traces) if self._traces else 0.0,
            "worm_seal_rate": worm_seal_count / len(self._traces) if self._traces else 0.0,
            "avg_spectral_gap": sum(spectral_gaps) / len(spectral_gaps) if spectral_gaps else 0.0
        }

    def get_intent_distribution(self) -> dict[str, int]:
        """Return count of each intent type observed."""
        intent_counts = {}
        for trace in self._traces:
            intent_counts[trace.intent] = intent_counts.get(trace.intent, 0) + 1
        return intent_counts

    def clear(self) -> None:
        """Clear all traces and reset statistics."""
        self._traces.clear()
        self._total_count = 0
        self._expert_usage.clear()
        self._glyph_distribution.clear()
        self._provider_counts.clear()


class DryRunRouter:
    """
    Simulates routing decision without actually executing.
    Used by POST /routing/test endpoint.
    """

    def __init__(self, collector: TraceCollector):
        self.collector = collector

    def route_simulation(self, text: str, intent: str = "query") -> dict[str, Any]:
        """
        Simulate where text would route.
        Returns what the routing would be without executing.
        """
        # Placeholder simulation logic
        # In real implementation, this would call the actual routing logic
        # but without executing the inference

        return {
            "text": text[:64],
            "predicted_intent": intent,
            "would_route_to": "multi-provider",
            "reason": "Simulated dry run - no actual routing performed",
            "recommended_providers": ["ollama", "openrouter"],
            "estimated_latency_ms": 45.0
        }
