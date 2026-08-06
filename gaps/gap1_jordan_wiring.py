"""
Gap 1: Wire JordanMoEGate into SparseActivation
Copy this into routing/sparse.py to replace the sigmoid gate.

This is a drop-in replacement for the gating_scores loop in
SparseActivation.compute().
"""

from __future__ import annotations
from .jordan_moe import JordanMoEGate, FixedPointSolver

# Add to SparseActivation.__init__:
# self._jordan_gate = JordanMoEGate(top_k=self.top_k)
# self._use_jordan = True  # set False to fall back to sigmoid

def jordan_gating_scores(
    self,
    signals: dict[str, float],
    expert_names: list[str],
    expert_mask: dict[str, bool],
    jordan_features: dict[str, float],
) -> dict[str, float]:
    """
    Replace the sigmoid gating loop with Jordan algebraic gating.

    Drop this method into SparseActivation and call it from compute()
    instead of the existing gating_scores loop.
    """
    # Build affinities from routing nodes
    affinities: dict[str, dict[str, float]] = {}
    for name in expert_names:
        node = self.routing_nodes.get(name)
        if node:
            affinities[name] = node.signal_affinity
        else:
            affinities[name] = {sig: 0.3 for sig in signals}

    # Run Jordan gate
    result = self._jordan_gate.gate(
        signals=signals,
        expert_names=expert_names,
        affinities=affinities,
        expert_mask=expert_mask,
    )

    # Scale by Jordan routing confidence
    routing_conf = jordan_features.get("routing_confidence", 1.0)
    scaled = {}
    for name in expert_names:
        w = result.weights.get(name, 0.0)
        scaled[name] = w * (0.5 + 0.5 * routing_conf)

    return scaled
