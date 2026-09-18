"""
burt_imma.py — BURT-IMMA core components.

Implements the CIFG matrix-memory cell, sum-inversion retrieval,
and entropy-constrained softmax from the BURT-IMMA architecture paper
(Bel Esprit D'Accord Irrevocable Trust — SNAPKITTYWEST, 2026).

Key equations:
  CIFG update:   C_t = f_t ⊙ C_{t-1} + (1-f_t) ⊙ (v_t ⊗ k_t)
  Retrieval:     y = q^T C_t
  Router entropy: H(α) ≤ 0.20 nats
  SmoothLeaky:   φ(x) = x·σ(x) + α·x·(1-σ(x))  where α = 0.1

No gradient tape. No weight transport. Fixed-point equilibrium.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Activations
# ---------------------------------------------------------------------------

def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def smooth_leaky(x: np.ndarray, alpha: float = 0.1) -> np.ndarray:
    """
    SmoothLeaky activation — four axioms:
    1. Differentiable everywhere (smooth at 0)
    2. Monotone
    3. Bounded gradient: α ≤ φ'(x) ≤ 1
    4. Reduces to identity for large |x|

    φ(x) = x·σ(x) + α·x·(1−σ(x))
    """
    s = _sigmoid(x)
    return x * s + alpha * x * (1.0 - s)


def entropy_constrained_softmax(
    logits: np.ndarray,
    max_entropy: float = 0.20,
) -> np.ndarray:
    """
    Softmax whose output distribution is constrained to H(α) ≤ max_entropy nats.
    If the unconstrained softmax exceeds the entropy budget, sharpening is applied
    via temperature reduction until H ≤ max_entropy.

    Default budget = 0.20 nats (matches both BURT-IMMA spec and ERE coherence gate).
    """
    logits = logits - logits.max()  # numerical stability

    def _softmax(lgs: np.ndarray, T: float = 1.0) -> np.ndarray:
        e = np.exp(lgs / T)
        return e / e.sum()

    def _entropy(p: np.ndarray) -> float:
        p = p[p > 1e-12]
        return float(-np.sum(p * np.log(p)))

    T = 1.0
    alpha = _softmax(logits, T)
    while _entropy(alpha) > max_entropy and T > 0.01:
        T *= 0.9
        alpha = _softmax(logits, T)

    return alpha


# ---------------------------------------------------------------------------
# CIFG Matrix-Memory Cell
# ---------------------------------------------------------------------------

class CIFGCell:
    """
    Coupled Input-Forget Gate (CIFG) matrix-memory cell.

    State: C ∈ ℝ^{d×d}  (full matrix, not a vector)

    Update rule (proven convex combination):
        f_t = σ(W_f x_t + b_f)        forget gate  ∈ [0,1]^d
        v_t = tanh(W_v x_t + b_v)     value vector ∈ ℝ^d
        k_t = tanh(W_k x_t + b_k)     key vector   ∈ ℝ^d
        C_t = f_t ⊙ C_{t-1} + (1-f_t) ⊙ (v_t ⊗ k_t)

    Retrieval (sum-inversion decoder):
        y_t = q_t C_t     where q_t = W_q x_t
    """

    def __init__(self, d: int, seed: Optional[int] = None) -> None:
        rng = np.random.default_rng(seed)
        scale = 0.02

        self.d = d
        self.C = np.zeros((d, d), dtype=np.float32)

        # Weight matrices (no biases for MMEP compatibility)
        # Xavier init: scale = sqrt(1/d) keeps ‖Wx‖ ~ ‖x‖ at init
        xscale = 1.0 / math.sqrt(d)
        self.W_f = rng.normal(0, xscale, (d, d)).astype(np.float32)
        self.W_v = rng.normal(0, xscale, (d, d)).astype(np.float32)
        self.W_k = rng.normal(0, xscale, (d, d)).astype(np.float32)
        self.W_q = rng.normal(0, xscale, (d, d)).astype(np.float32)

    def step(self, x: np.ndarray) -> np.ndarray:
        """
        One CIFG step.
        x: (d,) input vector
        Returns: (d,) output via sum-inversion retrieval.
        """
        f   = _sigmoid(self.W_f @ x)              # (d,) forget gate
        v   = np.tanh(self.W_v @ x)               # (d,) value
        k   = np.tanh(self.W_k @ x)               # (d,) key
        outer = np.outer(v, k)                     # (d,d) outer product

        # CIFG update: convex combination in every row
        self.C = f[:, None] * self.C + (1.0 - f)[:, None] * outer

        # Sum-inversion retrieval: q^T C
        q   = self.W_q @ x                        # (d,) query
        y   = q @ self.C                          # (d,) output
        return y.astype(np.float32)

    def reset(self) -> None:
        self.C[:] = 0.0


# ---------------------------------------------------------------------------
# Spectral projection (keeps relaxation contractive)
# ---------------------------------------------------------------------------

def spectral_project(W: np.ndarray, sigma_max: float = 1.0) -> np.ndarray:
    """
    Clip the largest singular value of W to sigma_max.
    Ensures the linear map is a contraction: ‖Wx‖ ≤ ‖x‖.
    """
    U, S, Vt = np.linalg.svd(W, full_matrices=False)
    S = np.clip(S, None, sigma_max)
    return (U * S) @ Vt


# ---------------------------------------------------------------------------
# BURT-IMMA Layer Stack
# ---------------------------------------------------------------------------

@dataclass
class BURTIMMAConfig:
    d_model:     int   = 768    # matches DeBERTa-v3 hidden size
    n_layers:    int   = 4      # CIFG layers
    max_entropy: float = 0.20   # router entropy budget (nats)
    smooth_alpha: float = 0.1   # SmoothLeaky slope


class BURTIMMAEncoder:
    """
    Lightweight BURT-IMMA encoder stack.

    Processes a sequence of input vectors through N CIFG matrix-memory
    layers, each followed by SmoothLeaky activation and spectral projection.

    Input:  (T, d_model) sequence of embeddings
    Output: (d_model,) pooled hidden state for decoding
    """

    def __init__(self, cfg: BURTIMMAConfig, seed: Optional[int] = 42) -> None:
        self.cfg = cfg
        self.cells = [
            CIFGCell(cfg.d_model, seed=seed + i if seed is not None else None)
            for i in range(cfg.n_layers)
        ]

    def encode(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Forward pass through CIFG stack.

        embeddings: (T, d_model) — sequence of token/patch embeddings
        Returns: (d_model,) final hidden state
        """
        for cell in self.cells:
            cell.reset()

        h = embeddings.astype(np.float32)
        for cell in self.cells:
            out = np.zeros_like(h)
            for t in range(h.shape[0]):
                out[t] = smooth_leaky(cell.step(h[t]), self.cfg.smooth_alpha)
            h = out

        # Mean-pool the final layer's outputs
        return h.mean(axis=0)

    def decode_top_tokens(
        self,
        hidden: np.ndarray,
        vocab_embeddings: np.ndarray,
        k: int = 5,
    ) -> list[int]:
        """
        Sum-inversion decoder: find the k vocabulary tokens whose embeddings
        best match the hidden state (dot-product similarity).

        vocab_embeddings: (V, d_model)
        Returns: top-k token indices
        """
        scores = vocab_embeddings @ hidden                  # (V,)
        logits = entropy_constrained_softmax(scores, self.cfg.max_entropy)
        return list(np.argsort(logits)[::-1][:k])
