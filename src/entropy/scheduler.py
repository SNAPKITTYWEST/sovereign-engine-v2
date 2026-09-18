"""
FrustrationCoolingScheduler — T(F) = T₀ + (1-T₀)·exp(-α·F)

Source: github.com/SNAPKITTYWEST/sovereign-entropy-theorem

The Sovereign Entropy Theorem (proved in lean/EntropyBound.lean) guarantees:
  With T₀ ≤ 0.1 and α ≥ 2.34:  H < 0.20 nats for all F ≥ 1.

Schedule:
  F = 0 → T = 1.00  (no frustration yet — full uncertainty allowed)
  F = 1 → T ≈ 0.22  (one violation — near the bound already)
  F → ∞ → T → T₀   (fully frustrated — temperature floor)
"""

from __future__ import annotations

import math
from .constants import T0_DEFAULT, ALPHA_DEFAULT, H_MAX


class FrustrationCoolingScheduler:
    def __init__(
        self,
        T0:    float = T0_DEFAULT,
        alpha: float = ALPHA_DEFAULT,
        d:     float = 1.0,
    ) -> None:
        self.T0    = T0
        self.alpha = alpha
        self.d     = d
        self._F    = 0

    def temperature(self, F: int | None = None) -> float:
        """T(F) = T₀ + (1-T₀)·exp(-α·F)"""
        if F is None:
            F = self._F
        return self.T0 + (1.0 - self.T0) * math.exp(-self.alpha * F)

    def entropy_upper_bound(self, F: int | None = None) -> float:
        """Theoretical H upper bound at given F (binary case, K=2)."""
        T = self.temperature(F)
        s = math.exp(self.d / T)
        return math.log(s + 1) - s * math.log(s) / (s + 1)

    def step(self, frustrated: bool = False) -> float:
        if frustrated:
            self._F += 1
        return self.temperature()

    def reset(self) -> None:
        self._F = 0

    @property
    def frustration(self) -> int:
        return self._F

    def schedule_table(self, F_max: int = 10) -> list[dict]:
        rows = []
        for F in range(F_max + 1):
            T = self.temperature(F)
            s = math.exp(self.d / T)
            H = math.log(s + 1) - s * math.log(s) / (s + 1)
            rows.append({
                "F": F, "T": round(T, 6), "s": round(s, 2),
                "H_nats": round(H, 6), "H_bound_ok": H < H_MAX,
            })
        return rows
