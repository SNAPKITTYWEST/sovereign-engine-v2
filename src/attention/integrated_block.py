"""
integrated_block.py — RMSNorm + Hyperbolic UMTCPI + CIFG Memory

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Complete transformer-style block replacing every standard component:

    Standard            →  Integrated
    ─────────────────────────────────
    LayerNorm           →  RMSNorm        (50% fewer params, 15-20% faster)
    Multi-Head Softmax  →  Hyperbolic UMTCPI (no softmax, curvature-aware)
    FFN (4×hidden)      →  CIFG Memory    (dynamic outer-product associative memory)
    Total: ~12×dim²        →  ~5×dim²    (60% parameter reduction)

Architecture:
    O → RMSNorm → HyperbolicUMTCPI → Residual
      → RMSNorm → CIFGMemory → Residual → W_out → Output

Core principle:
    "Resonance couples; the memory associates."
    Weights are amplitudes, not probabilities. Sum ≠ 1 everywhere.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# RMSNorm
# ---------------------------------------------------------------------------

def rmsnorm(x: np.ndarray, gamma: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """
    RMSNorm(x) = x / sqrt(mean(x²) + ε) · γ

    Drops mean subtraction entirely — transformer pre-activations
    are already approximately zero-mean, so RMS is sufficient.
    """
    rms = np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True) + eps)
    return (x / rms) * gamma


class RMSNorm:
    def __init__(self, dim: int, eps: float = 1e-6) -> None:
        self.dim   = dim
        self.eps   = eps
        self.gamma = np.ones(dim, dtype=np.float32)

    def forward(self, x: np.ndarray) -> np.ndarray:
        return rmsnorm(x, self.gamma, self.eps)


# ---------------------------------------------------------------------------
# Hyperbolic distance (Poincaré ball)
# ---------------------------------------------------------------------------

def poincare_distance(
    x: np.ndarray,
    y: np.ndarray,
    c: float = 1.0,
) -> float:
    """
    d_H(x,y) = (1/√c) · arccosh(1 + 2c‖x-y‖² / ((1-c‖x‖²)(1-c‖y‖²)))

    c > 0: curvature (c=1 → unit ball)
    Points are projected into the open ball ‖x‖ < 1/√c before computation.
    """
    scale = 1.0 / math.sqrt(c)
    # Project into open ball
    xn = np.linalg.norm(x)
    yn = np.linalg.norm(y)
    lim = scale * 0.999
    if xn >= lim: x = x / xn * lim
    if yn >= lim: y = y / yn * lim

    num   = 2.0 * c * float(np.sum((x - y) ** 2))
    denom = (1.0 - c * float(x @ x)) * (1.0 - c * float(y @ y))
    arg   = 1.0 + num / max(denom, 1e-8)
    arg   = max(arg, 1.0 + 1e-7)   # arccosh needs arg ≥ 1
    return scale * math.acosh(arg)


# ---------------------------------------------------------------------------
# Hyperbolic UMTCPI
# ---------------------------------------------------------------------------

def hyperbolic_umtcpi(
    O:   np.ndarray,   # (K, d)
    r:   float = 2.0,
    c:   float = 1.0,  # curvature parameter (negative curvature = richer hierarchy)
) -> dict:
    """
    Hyperbolic UMTCPI:

        UMTCPI_H(Ō) = Σ_k B_k · exp[-π/(4r) · d_H(O_{k+1}, O_{k-1})]

    Uses Poincaré distance instead of Euclidean magnitude difference.
    This amplifies separation near the boundary of the Poincaré ball,
    giving richer hierarchical structure to the resonance weights.

    Σ_k w_k ≠ 1  (simplex broken — proved for Euclidean case, holds here too)
    """
    K, d = O.shape

    def sig(v): return 1.0 / (1.0 + np.exp(-np.clip(v, -20, 20)))

    # Boolean gates
    B = np.zeros(K, dtype=np.float64)
    for k in range(K):
        prev  = O[k-1].mean() if k > 0 else 0.0
        nxt   = O[(k+1) % K].mean()
        g_and = float(sig(np.array(O[k].mean() + prev)))
        g_nand = 1.0 - float(sig(np.array(O[k].mean() + nxt)))
        B[k]  = float(sig(np.array(2.0 * (g_and - g_nand) ** 2 - 1.0)))

    # Hyperbolic magnitude differences
    w = np.zeros(K, dtype=np.float64)
    for k in range(K):
        prev_vec = O[k-1] if k > 0 else np.zeros(d)
        nxt_vec  = O[(k+1) % K]
        hd       = poincare_distance(nxt_vec, prev_vec, c=c)
        w[k]     = B[k] * math.exp(-(math.pi / (4.0 * r)) * hd)

    return {
        "weights":     w,
        "sum_weights": float(w.sum()),
        "bool_gates":  B,
        "hyperbolic_diameter": max(
            poincare_distance(O[i], O[j], c=c)
            for i in range(min(K, 4)) for j in range(min(K, 4)) if i != j
        ) if K > 1 else 0.0,
    }


# ---------------------------------------------------------------------------
# CIFG Matrix Memory (replaces FFN)
# ---------------------------------------------------------------------------

class CIFGMemory:
    """
    Coupled Input-Forget Gate (CIFG) matrix memory.

    C_t = f_t ⊙ C_{t-1} + (1 − f_t) ⊙ outer(v_t, k_t)

    Replaces static FFN W₂·GELU(W₁·x) with dynamic associative memory.
    Output: q_t @ C_t  (sum-inversion retrieval)

    Parameters: W_f, W_v, W_k, W_q  (4 × d² = 4d² total, vs FFN 8d²)
    """

    def __init__(self, dim: int, seed: int = 42) -> None:
        self.dim = dim
        self.C   = np.zeros((dim, dim), dtype=np.float32)
        rng  = np.random.default_rng(seed)
        sc   = 1.0 / math.sqrt(dim)
        self.W_f = rng.normal(0, sc, (dim, dim)).astype(np.float32)
        self.W_v = rng.normal(0, sc, (dim, dim)).astype(np.float32)
        self.W_k = rng.normal(0, sc, (dim, dim)).astype(np.float32)
        self.W_q = rng.normal(0, sc, (dim, dim)).astype(np.float32)

    def reset(self) -> None:
        self.C[:] = 0.0

    def step(self, x: np.ndarray) -> np.ndarray:
        """One CIFG step. x: (dim,)"""
        def sig(v): return 1.0 / (1.0 + np.exp(-np.clip(v, -20, 20)))
        f = sig(self.W_f @ x)          # (dim,) ∈ [0,1]
        v = np.tanh(self.W_v @ x)      # (dim,)
        k = np.tanh(self.W_k @ x)      # (dim,)
        outer = np.outer(v, k)         # (dim, dim)
        self.C = f[:, None] * self.C + (1.0 - f)[:, None] * outer
        q   = self.W_q @ x
        return q @ self.C              # (dim,)

    def forward(self, O: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        O: (K, dim)  sequence.
        Returns (output (K, dim), final memory matrix (dim, dim))
        """
        self.reset()
        out = np.zeros_like(O)
        for t in range(len(O)):
            out[t] = self.step(O[t])
        return out, self.C.copy()

    def memory_stats(self) -> dict:
        """Rank, norms, and sparsity of the current memory matrix."""
        C = self.C
        sv = np.linalg.svd(C, compute_uv=False)
        return {
            "rank":          int(np.linalg.matrix_rank(C)),
            "frobenius_norm":float(np.linalg.norm(C, "fro")),
            "spectral_norm": float(sv[0]),
            "trace":         float(np.trace(C)),
            "sparsity":      float(np.mean(np.abs(C) < 1e-6)),
        }


# ---------------------------------------------------------------------------
# Full integrated block
# ---------------------------------------------------------------------------

@dataclass
class BlockConfig:
    dim:           int   = 32
    r:             float = 2.0
    curvature:     float = 1.0   # c for Poincaré ball; 1.0 = unit ball
    memory_dim:    int   = 32
    eps:           float = 1e-6
    seed:          int   = 42


class HyperbolicCIFGUMTCPI:
    """
    Full transformer-style block:

        O → RMSNorm → HyperbolicUMTCPI → Residual
          → RMSNorm → CIFGMemory → Residual → W_out → Output
    """

    def __init__(self, cfg: Optional[BlockConfig] = None, **kwargs) -> None:
        if cfg is None:
            cfg = BlockConfig(**kwargs)
        self.cfg      = cfg
        self.norm1    = RMSNorm(cfg.dim, cfg.eps)
        self.norm2    = RMSNorm(cfg.dim, cfg.eps)
        self.memory   = CIFGMemory(cfg.memory_dim, seed=cfg.seed)

        rng  = np.random.default_rng(cfg.seed)
        sc   = 1.0 / math.sqrt(cfg.dim)
        self.W_out = rng.normal(0, sc, (cfg.dim, cfg.dim)).astype(np.float32)

    def forward(self, O: np.ndarray) -> dict:
        """
        O: (K, dim)
        Returns dict with output + diagnostics.
        """
        # ── Arm 1: RMSNorm → Hyperbolic UMTCPI → Residual ────────────
        x1   = self.norm1.forward(O)
        attn = hyperbolic_umtcpi(x1, r=self.cfg.r, c=self.cfg.curvature)
        w    = attn["weights"][:, None]    # (K, 1)
        # Weighted blend of token vectors + residual
        attn_out = x1 * w                  # (K, dim) — each token scaled by resonance weight
        O2  = O + attn_out / max(len(O), 1)

        # ── Arm 2: RMSNorm → CIFG Memory → Residual ──────────────────
        x2        = self.norm2.forward(O2)
        mem_out, C = self.memory.forward(x2)
        O3        = O2 + mem_out

        # ── Output projection ─────────────────────────────────────────
        out = O3 @ self.W_out

        return {
            "output":        out,
            "attn_result":   attn,
            "memory_matrix": C,
            "memory_stats":  self.memory.memory_stats(),
            "norm1_out":     x1,
            "norm2_out":     x2,
        }


def integrated_block(
    O:          np.ndarray,
    dim:        int   = 32,
    r:          float = 2.0,
    curvature:  float = 1.0,
    hyperbolic: bool  = True,
) -> dict:
    """One-shot convenience wrapper."""
    cfg = BlockConfig(dim=dim, r=r, curvature=curvature, memory_dim=dim)
    blk = HyperbolicCIFGUMTCPI(cfg)
    return blk.forward(O)
