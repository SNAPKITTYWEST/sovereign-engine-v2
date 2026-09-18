"""
Test examples for routing trace endpoints.
Demonstrates how to use the new Gap 5 HTTP endpoints.
"""

import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bridge.routing_trace import TraceCollector, RoutingTrace


def test_trace_collector():
    """Test TraceCollector basic functionality."""
    print("=== Testing TraceCollector ===\n")

    collector = TraceCollector(max_traces=100)

    # Create some sample traces
    for i in range(5):
        trace = RoutingTrace(
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_text=f"Query {i}: What is the sovereign engine?" [:64],
            intent="query",
            active_experts=["embeddings", "semantic_router"],
            weights={"ollama": 0.6, "openrouter": 0.4},
            jordan_stable=True,
            spectral_gap=0.85 + (i * 0.01),
            worm_sealed=True,
            ere_passed=True if i % 2 == 0 else False,
            latency_ms=45.2 + (i * 5),
            qra_glyph=["Pi", "Gamma", "Delta", "Lambda", "Omega"][i % 5],
            provider="ollama" if i % 2 == 0 else "openrouter"
        )
        collector.record(trace)
        print(f"Recorded trace {i+1}: {trace.intent} -> {trace.provider}")

    print("\n--- Latest traces ---")
    latest = collector.get_latest(3)
    for trace in latest:
        print(json.dumps(trace, indent=2))

    print("\n--- Statistics ---")
    stats = collector.get_stats()
    print(json.dumps(stats, indent=2))

    print("\n--- Intent Distribution ---")
    intent_dist = collector.get_intent_distribution()
    print(json.dumps(intent_dist, indent=2))


async def test_http_endpoints_simulation():
    """
    Simulate what the HTTP endpoints would return.
    (Requires the HTTPBridge to be running on http://127.0.0.1:19000)
    """
    print("\n=== Simulating HTTP Endpoint Responses ===\n")

    collector = TraceCollector(max_traces=10)

    # Add some sample data
    for i in range(8):
        trace = RoutingTrace(
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_text=f"Sample text {i}" [:64],
            intent=["query", "command", "feedback"][i % 3],
            active_experts=["embeddings", "classifier"],
            weights={"expert_a": 0.7, "expert_b": 0.3},
            jordan_stable=i % 3 != 0,
            spectral_gap=0.82,
            worm_sealed=True,
            ere_passed=i % 2 == 0,
            latency_ms=42 + (i * 3),
            qra_glyph=["Pi", "Gamma", "Delta"][i % 3],
            provider=["ollama", "openrouter"][i % 2]
        )
        collector.record(trace)

    # Simulate GET /routing/traces
    print("GET /routing/traces?limit=5")
    traces_response = {
        "traces": collector.get_latest(5),
        "count": 5,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    print(json.dumps(traces_response, indent=2))

    # Simulate GET /routing/stats
    print("\n\nGET /routing/stats")
    stats_response = {
        "stats": collector.get_stats(),
        "intent_distribution": collector.get_intent_distribution(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    print(json.dumps(stats_response, indent=2))

    # Simulate POST /routing/test
    print("\n\nPOST /routing/test")
    test_response = {
        "input": "Show me the latest proofs",
        "intent": "query",
        "would_route_to": "multi-provider",
        "estimated_latency_ms": 45.0,
        "reason": "Simulated routing - no actual inference performed",
        "recommended_providers": ["ollama", "openrouter"],
        "simulation_latency_ms": 0.8
    }
    print(json.dumps(test_response, indent=2))


if __name__ == "__main__":
    print("Routing Trace Endpoint Tests\n")
    test_trace_collector()
    asyncio.run(test_http_endpoints_simulation())
    print("\n=== All tests completed ===")
