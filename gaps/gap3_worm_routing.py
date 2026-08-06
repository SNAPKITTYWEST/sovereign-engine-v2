"""
Gap 3: WORM-seal every routing decision.
Add this to routing/pipeline.py RoutingPipeline class.
"""

import json
import os
from pathlib import Path


def _init_routing_ledger(self) -> None:
    """
    Add to RoutingPipeline.__init__() after all stage setup.
    """
    try:
        from ..core.evidence import WORMLedger
        from ..core.crypto import generate_signing_key

        ledger_path = Path(os.environ.get(
            "SOVEREIGN_ROUTING_LEDGER", "routing_worm.jsonl"
        ))
        self._routing_ledger = WORMLedger(ledger_path, generate_signing_key())
        self._tick = 0
    except Exception:
        self._routing_ledger = None
        self._tick = 0


def _seal_routing_decision(self, trace) -> None:
    """
    Add to end of route_with_trace() before return.
    """
    if not self._routing_ledger:
        return

    try:
        from ..core.crypto import hash_content

        event = {
            "tick": self._tick,
            "input_hash": hash_content(trace.input_text.encode()),
            "intent": trace.parse.intent,
            "confidence": round(trace.parse.confidence, 6),
            "active_experts": trace.routing.active_experts,
            "weights": {
                k: round(v, 6)
                for k, v in trace.routing.weights.items()
                if v > 0
            },
            "nand_suppressed": trace.routing.nand_suppressed,
            "payload_blocked": trace.parse.payload_blocked,
            "stability_score": round(
                trace.jordan.routing_features.get("stability_score", 0), 6
            ),
            "spectral_radius": round(
                trace.jordan.routing_features.get("spectral_radius", 0), 6
            ),
            "dead_experts": trace.jacobian.dead_experts,
            "blocked_experts": [
                r.expert for r in trace.constraints.per_expert
                if not r.allowed
            ],
        }

        self._routing_ledger.append(
            "routing_decision",
            json.dumps(event).encode(),
            {"tick": self._tick}
        )
        self._tick += 1

    except Exception:
        pass  # never let ledger failure break routing
