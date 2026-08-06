"""
Stage 5: JacobianLens

Computes routing sensitivity: how much does each input signal
affect each expert's routing weight?

∂routing_weight_k / ∂signal_j

This is computed numerically via finite differences over the
signal vector. No neural network required — we differentiate
the routing weight function directly.

Result tells you:
  - Which signals are most influential for each expert
  - Which experts are sensitive vs robust to input variation
  - Dead routing paths (zero Jacobian across all signals)
"""

from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class JacobianAnalysis:
    # J[expert_idx][signal_idx] = ∂weight_k/∂signal_j
    matrix: list[list[float]]
    expert_names: list[str]
    signal_names: list[str]

    # Per-expert sensitivity (Frobenius norm of each row)
    expert_sensitivity: dict[str, float]

    # Per-signal influence (Frobenius norm of each column)
    signal_influence: dict[str, float]

    # Dead paths: experts with near-zero sensitivity to all signals
    dead_experts: list[str]

    # Condition number (max singular value / min singular value)
    # High condition = routing is ill-conditioned (brittle)
    condition_number: float


class JacobianLens:
    """
    Stage 5: Numerical Jacobian of the routing weight function.

    Takes routing weights as a function of signal vector,
    computes ∂w_k/∂s_j for all experts k and signals j.
    """

    EPSILON = 1e-4

    def analyze(
        self,
        routing_fn,                    # callable: signals dict -> weights dict
        signals: dict[str, float],
        expert_names: list[str]
    ) -> JacobianAnalysis:
        """
        Args:
            routing_fn:   function(signals) -> {expert_name: weight}
            signals:      current signal vector
            expert_names: list of expert names to track
        """
        signal_names = list(signals.keys())
        n_experts = len(expert_names)
        n_signals = len(signal_names)

        # Base weights
        base_weights = routing_fn(signals)

        # Build Jacobian via finite differences
        # J[k][j] = (f_k(s + ε*e_j) - f_k(s)) / ε
        J: list[list[float]] = [[0.0] * n_signals for _ in range(n_experts)]

        for j, sig_name in enumerate(signal_names):
            # Perturb signal j
            perturbed = dict(signals)
            perturbed[sig_name] = perturbed[sig_name] + self.EPSILON

            perturbed_weights = routing_fn(perturbed)

            for k, expert in enumerate(expert_names):
                base_w = base_weights.get(expert, 0.0)
                pert_w = perturbed_weights.get(expert, 0.0)
                J[k][j] = (pert_w - base_w) / self.EPSILON

        # Expert sensitivity: L2 norm of each row
        expert_sensitivity: dict[str, float] = {}
        for k, expert in enumerate(expert_names):
            norm = math.sqrt(sum(J[k][j] ** 2 for j in range(n_signals)))
            expert_sensitivity[expert] = norm

        # Signal influence: L2 norm of each column
        signal_influence: dict[str, float] = {}
        for j, sig_name in enumerate(signal_names):
            norm = math.sqrt(sum(J[k][j] ** 2 for k in range(n_experts)))
            signal_influence[sig_name] = norm

        # Dead experts: sensitivity < threshold
        DEAD_THRESHOLD = 1e-5
        dead_experts = [
            expert for expert, sens in expert_sensitivity.items()
            if sens < DEAD_THRESHOLD
        ]

        # Condition number via power iteration approximation
        condition_number = self._approx_condition_number(J, n_experts, n_signals)

        return JacobianAnalysis(
            matrix=J,
            expert_names=expert_names,
            signal_names=signal_names,
            expert_sensitivity=expert_sensitivity,
            signal_influence=signal_influence,
            dead_experts=dead_experts,
            condition_number=condition_number
        )

    def _approx_condition_number(
        self,
        J: list[list[float]],
        n_rows: int,
        n_cols: int
    ) -> float:
        """
        Approximate condition number via ratio of max/min row norms.
        Not exact (true cond uses singular values) but sufficient for routing.
        """
        row_norms = [
            math.sqrt(sum(J[k][j] ** 2 for j in range(n_cols)))
            for k in range(n_rows)
        ]

        max_norm = max(row_norms) if row_norms else 0.0
        min_norm = min(r for r in row_norms if r > 1e-10) if any(r > 1e-10 for r in row_norms) else 1.0

        if min_norm == 0.0:
            return float('inf')

        return max_norm / min_norm

    def top_signals_for_expert(
        self,
        analysis: JacobianAnalysis,
        expert: str,
        top_k: int = 3
    ) -> list[tuple[str, float]]:
        """Return top-k most influential signals for a given expert."""
        k = analysis.expert_names.index(expert)
        row = analysis.matrix[k]
        ranked = sorted(
            zip(analysis.signal_names, row),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        return ranked[:top_k]
