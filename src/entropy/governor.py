"""
EntropyGovernor — HuggingFace LogitsProcessor

Source: github.com/SNAPKITTYWEST/sovereign-entropy-theorem

Drop-in LogitsProcessor that enforces the Sovereign Entropy Bound:
  H < 0.20 nats (formally proved in lean/EntropyBound.lean, Agda, CUDA-Q)

Operation per token step:
  1. Compute H of the current logit distribution
  2. Track frustration F = count of steps where H was too high
  3. Apply T(F) = T₀ + (1-T₀)·exp(-α·F) dynamic temperature
  4. Hard halt (collapse to argmax) when H ≥ H_max after scaling
  5. Issue WORM-sealed receipt on finalize()

External names:  verify / halt / seal
Internal names:  ERE gate / Dream Cycle trigger / WORM receipt
"""

from __future__ import annotations

import math
import time
from typing import Optional

try:
    import torch
    from transformers import LogitsProcessor
    HAS_TRANSFORMERS = True
except Exception:
    HAS_TRANSFORMERS = False

from .constants import T0_DEFAULT, ALPHA_DEFAULT, H_MAX, THETA
from .worm import worm_seal, WORMChain


def _entropy_nats(logits) -> float:
    if HAS_TRANSFORMERS:
        import torch.nn.functional as F
        probs     = F.softmax(logits.float(), dim=-1)
        log_probs = probs.log()
        return float(-torch.sum(probs * log_probs, dim=-1).mean())
    max_l = max(logits)
    exp_l = [math.exp(x - max_l) for x in logits]
    Z     = sum(exp_l)
    probs = [e / Z for e in exp_l]
    return -sum(p * math.log(p) for p in probs if p > 0)


def _apply_temperature(logits, T: float):
    if HAS_TRANSFORMERS:
        return logits / T
    return [x / T for x in logits]


class EntropyGovernor:
    """
    Enforces H < 0.20 nats at every token step via dynamic temperature.

    Use as a HuggingFace logits_processor=[gov] argument, or call
    directly with (input_ids, scores) at each step.

    Parameters
    ----------
    max_entropy : float   H_max in nats. Default 0.20.
    T0          : float   Base temperature. Default 0.1.
    alpha       : float   Cooling rate. Default 2.0.
    hard_halt   : bool    Collapse to argmax on violation (True) or just cool (False).
    """

    def __init__(
        self,
        max_entropy: float = H_MAX,
        T0:          float = T0_DEFAULT,
        alpha:       float = ALPHA_DEFAULT,
        theta:       float = THETA,
        hard_halt:   bool  = True,
    ) -> None:
        self.max_entropy = max_entropy
        self.T0          = T0
        self.alpha       = alpha
        self.theta       = theta
        self.hard_halt   = hard_halt

        self._step             = 0
        self.frustration       = 0
        self.halted_at:        list[int]   = []
        self.entropy_trace:    list[float] = []
        self.temperature_trace:list[float] = []
        self.receipt:          Optional[str] = None
        self._chain            = WORMChain()
        self._start_ts         = time.time()

    def temperature(self, F: int) -> float:
        """T(F) = T₀ + (1-T₀)·exp(-α·F)"""
        return self.T0 + (1.0 - self.T0) * math.exp(-self.alpha * F)

    def __call__(self, input_ids, scores):
        """HuggingFace generate() hook — called at every token step."""
        if not HAS_TRANSFORMERS:
            raise RuntimeError("transformers not installed")
        import torch

        T           = self.temperature(self.frustration)
        scores_sc   = scores / T
        H           = _entropy_nats(scores_sc)

        self.temperature_trace.append(T)
        self.entropy_trace.append(H)

        if H >= self.max_entropy:
            self.frustration += 1
            self.halted_at.append(self._step)
            self._chain.append({"step": self._step, "H": round(H, 6),
                                 "T": round(T, 6), "F": self.frustration,
                                 "action": "HALT"})
            if self.hard_halt:
                argmax = torch.argmax(scores_sc, dim=-1, keepdim=True)
                new    = torch.full_like(scores_sc, float("-inf"))
                new.scatter_(1, argmax, 0.0)
                self._step += 1
                return new
        else:
            self._chain.append({"step": self._step, "H": round(H, 6),
                                 "T": round(T, 6), "F": self.frustration,
                                 "action": "PASS"})

        self._step += 1
        return scores_sc

    def step_numpy(self, logits: list[float]) -> tuple[list[float], str]:
        """
        Pure-Python / NumPy alternative for use without torch.

        Returns (scaled_logits, action) where action ∈ {"PASS","HALT"}.
        """
        T  = self.temperature(self.frustration)
        sc = [x / T for x in logits]
        H  = _entropy_nats(sc)

        self.temperature_trace.append(T)
        self.entropy_trace.append(H)

        if H >= self.max_entropy:
            self.frustration += 1
            self.halted_at.append(self._step)
            self._chain.append({"step": self._step, "H": round(H, 6),
                                 "T": round(T, 6), "F": self.frustration,
                                 "action": "HALT"})
            if self.hard_halt:
                max_idx = sc.index(max(sc))
                sc = [0.0 if i == max_idx else float("-inf")
                      for i in range(len(sc))]
            self._step += 1
            return sc, "HALT"

        self._chain.append({"step": self._step, "H": round(H, 6),
                             "T": round(T, 6), "F": self.frustration,
                             "action": "PASS"})
        self._step += 1
        return sc, "PASS"

    def finalize(self) -> str:
        summary = {
            "steps":       self._step,
            "frustration": self.frustration,
            "halts":       len(self.halted_at),
            "max_H":       round(max(self.entropy_trace) if self.entropy_trace else 0, 6),
            "min_T":       round(min(self.temperature_trace) if self.temperature_trace else self.T0, 6),
            "elapsed_s":   round(time.time() - self._start_ts, 3),
            "bound_H":     self.max_entropy,
            "T0":          self.T0,
            "alpha":       self.alpha,
            "theta":       self.theta,
        }
        self.receipt = worm_seal(summary)
        return self.receipt

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.receipt is None:
            self.finalize()

    def summary(self) -> dict:
        return {
            "steps":           self._step,
            "frustration":     self.frustration,
            "halted_at":       self.halted_at,
            "max_entropy_seen":max(self.entropy_trace) if self.entropy_trace else None,
            "min_temperature": min(self.temperature_trace) if self.temperature_trace else None,
            "receipt":         self.receipt or self.finalize(),
        }


if HAS_TRANSFORMERS:
    EntropyGovernor.__bases__ = (LogitsProcessor,)
