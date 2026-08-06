"""
Stage 7 + 8 + 9: SparseActivation + RoutingNodes + NANDFilter

SparseActivation:
  Computes routing weights using a softmax over signal projections,
  then applies top-k sparsity gate.
  Only top-k experts receive non-zero weight.

RoutingNodes:
  Per-expert gating functions. Each expert has:
    - A signal affinity vector (which signals it responds to)
    - A threshold (minimum signal strength to activate)
    - A temperature (sharpness of its gating curve)

  Gating output = sigmoid((dot(affinity, signals) - threshold) / temperature)

NANDFilter:
  Conflict resolution via NAND logic.
  If expert A and expert B are both active AND their combination
  is flagged as conflicting, at least one must be suppressed.

  NAND(A, B) = NOT(A AND B)
  → If both active + conflict registered → suppress lower-weight one.

Combined output: sparse routing weight vector.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field


# ==========================================
# Routing Nodes
# ==========================================

@dataclass
class RoutingNode:
    expert_name: str
    signal_affinity: dict[str, float]   # signal_name -> affinity weight
    threshold: float = 0.1              # minimum activation
    temperature: float = 1.0            # gating sharpness
    max_weight: float = 1.0             # ceiling on this expert's weight

    def gate(self, signals: dict[str, float]) -> float:
        """
        Compute gating score for this expert given signals.
        Returns value in [0, max_weight].
        """
        # Dot product of affinity and signals
        dot = sum(
            self.signal_affinity.get(sig, 0.0) * val
            for sig, val in signals.items()
        )

        # Sigmoid gating: σ((dot - threshold) / temperature)
        x = (dot - self.threshold) / max(self.temperature, 1e-6)
        gate_val = 1.0 / (1.0 + math.exp(-x))

        return min(gate_val, self.max_weight)


def build_default_routing_nodes(expert_names: list[str]) -> dict[str, RoutingNode]:
    """
    Build default routing nodes.
    Each expert gets affinity based on its name keywords.
    """
    nodes: dict[str, RoutingNode] = {}

    for name in expert_names:
        name_lower = name.lower()

        # Infer affinity from expert name
        affinity: dict[str, float] = {}

        if any(k in name_lower for k in ("code", "coder", "dev", "engineer", "impl")):
            affinity["code_signal"] = 0.9
            affinity["language_signal"] = 0.7
            affinity["entity_signal"] = 0.3

        if any(k in name_lower for k in ("query", "search", "retrieve", "rag", "lookup")):
            affinity["query_signal"] = 0.9
            affinity["entity_signal"] = 0.5

        if any(k in name_lower for k in ("reason", "logic", "math", "proof", "formal")):
            affinity["operator_signal"] = 0.8
            affinity["constraint_signal"] = 0.6
            affinity["code_signal"] = 0.4

        if any(k in name_lower for k in ("constraint", "guard", "safety", "valid")):
            affinity["constraint_signal"] = 0.9
            affinity["operator_signal"] = 0.5

        if any(k in name_lower for k in ("chat", "converse", "respond", "general")):
            affinity["query_signal"] = 0.5
            affinity["code_signal"] = 0.3

        # Default affinity if name gives no hints
        if not affinity:
            affinity = {sig: 0.3 for sig in [
                "code_signal", "query_signal", "constraint_signal",
                "operator_signal", "language_signal", "entity_signal"
            ]}

        nodes[name] = RoutingNode(
            expert_name=name,
            signal_affinity=affinity,
            threshold=0.1,
            temperature=0.5
        )

    return nodes


# ==========================================
# NAND Filter
# ==========================================

@dataclass
class NANDConflict:
    expert_a: str
    expert_b: str
    reason: str


class NANDFilter:
    """
    Stage 9: Conflict resolution.
    NAND(A, B) = if both active + conflict → suppress lower weight.
    """

    def __init__(self):
        self._conflicts: list[NANDConflict] = []

    def register_conflict(self, a: str, b: str, reason: str = "") -> None:
        self._conflicts.append(NANDConflict(a, b, reason))

    def apply(self, weights: dict[str, float]) -> dict[str, float]:
        """
        Apply NAND filtering.
        For each conflict pair where both are active:
          suppress the one with lower weight (set to 0).
        """
        result = dict(weights)

        for conflict in self._conflicts:
            wa = result.get(conflict.expert_a, 0.0)
            wb = result.get(conflict.expert_b, 0.0)

            # Both active?
            if wa > 1e-6 and wb > 1e-6:
                # NAND: suppress lower weight
                if wa <= wb:
                    result[conflict.expert_a] = 0.0
                else:
                    result[conflict.expert_b] = 0.0

        return result


# ==========================================
# Sparse Activation + Routing Weights
# ==========================================

@dataclass
class RoutingWeights:
    weights: dict[str, float]       # expert_name -> weight (sum to 1.0)
    active_experts: list[str]       # experts with weight > 0
    top_k: int
    raw_scores: dict[str, float]    # before normalization
    gating_scores: dict[str, float] # from routing nodes
    nand_suppressed: list[str]      # experts zeroed by NAND


class SparseActivation:
    """
    Stage 7: Compute sparse routing weights.

    Algorithm:
    1. Each RoutingNode produces a gating score per expert
    2. Multiply by constraint mask (blocked = 0)
    3. Apply top-k sparsity: zero out all but top-k scores
    4. Apply NAND filter: resolve conflicts
    5. Softmax normalize surviving scores
    """

    def __init__(
        self,
        top_k: int = 2,
        routing_nodes: dict[str, RoutingNode] | None = None,
        nand_filter: NANDFilter | None = None
    ):
        self.top_k = top_k
        self.routing_nodes = routing_nodes or {}
        self.nand_filter = nand_filter or NANDFilter()

    def compute(
        self,
        signals: dict[str, float],
        expert_names: list[str],
        expert_mask: dict[str, bool],       # from ConstraintEval
        jordan_features: dict[str, float]   # from JordanResult
    ) -> RoutingWeights:

        # Ensure routing nodes exist for all experts
        for name in expert_names:
            if name not in self.routing_nodes:
                self.routing_nodes[name] = build_default_routing_nodes([name])[name]

        # Step 1: Gating scores from routing nodes
        gating_scores: dict[str, float] = {}
        for name in expert_names:
            node = self.routing_nodes[name]
            score = node.gate(signals)

            # Scale by Jordan routing confidence (stable graph = more confident)
            routing_conf = jordan_features.get("routing_confidence", 1.0)
            score = score * (0.5 + 0.5 * routing_conf)

            gating_scores[name] = score

        # Step 2: Apply constraint mask
        masked: dict[str, float] = {
            name: (score if expert_mask.get(name, True) else 0.0)
            for name, score in gating_scores.items()
        }

        # Step 3: Top-k sparsity
        sorted_experts = sorted(masked.items(), key=lambda x: x[1], reverse=True)
        sparse: dict[str, float] = {}
        for i, (name, score) in enumerate(sorted_experts):
            sparse[name] = score if i < self.top_k else 0.0

        # Step 4: NAND filter
        after_nand = self.nand_filter.apply(sparse)
        nand_suppressed = [
            name for name in expert_names
            if sparse.get(name, 0.0) > 0 and after_nand.get(name, 0.0) == 0.0
        ]

        # Step 5: Softmax normalize
        active = {name: w for name, w in after_nand.items() if w > 1e-6}
        normalized = self._softmax(active)

        # Zero out everything not in normalized
        final_weights: dict[str, float] = {name: 0.0 for name in expert_names}
        final_weights.update(normalized)

        return RoutingWeights(
            weights=final_weights,
            active_experts=list(normalized.keys()),
            top_k=self.top_k,
            raw_scores=gating_scores,
            gating_scores=gating_scores,
            nand_suppressed=nand_suppressed
        )

    def _softmax(self, scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}

        vals = list(scores.values())
        max_val = max(vals)

        exp_vals = {name: math.exp(v - max_val) for name, v in scores.items()}
        total = sum(exp_vals.values())

        if total == 0:
            return {}

        return {name: v / total for name, v in exp_vals.items()}
