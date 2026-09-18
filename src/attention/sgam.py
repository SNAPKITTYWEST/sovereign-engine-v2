"""
sgam.py — Spatial Geometric Attention Mechanism (SGAM)

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Deterministic attention from geometric kernels — no softmax.

    A(Q, K, V) = G(Q, K) · V

    G_{ij} = K(q_i, k_j)     (geometric kernel, not exponentiated dot product)

Kernel options (all deterministic):
  inv_sq   : (D² + ε)^-α
  inv      : (D^α + ε)^-1
  compact  : (1 - D/r)_+^p   (compact support)
  rbf      : exp(-D²/2σ²)    (un-normalized RBF — no row softmax)
  cosine   : c(q,k)^β  where c = cosine similarity
  angular  : (π - arccos(c)) / π

Multi-head: each head can use a different kernel / radius / geometry.

Normalization (optional): geometric partition-of-unity G / row_sum(G).
This is NOT softmax — it is scale-invariant normalization only.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Literal, Dict, Any


# ---------------------------------------------------------------------------
# Pairwise distances
# ---------------------------------------------------------------------------

def pairwise_euclidean(Q: np.ndarray, K: np.ndarray) -> np.ndarray:
    """(n, d) × (m, d) → (n, m) Euclidean distances."""
    diff = Q[:, None, :] - K[None, :, :]   # (n, m, d)
    return np.sqrt((diff ** 2).sum(axis=-1) + 1e-12)


def pairwise_cosine(Q: np.ndarray, K: np.ndarray) -> np.ndarray:
    """(n, d) × (m, d) → (n, m) cosine similarities in [-1, 1]."""
    qn = Q / (np.linalg.norm(Q, axis=-1, keepdims=True) + 1e-8)
    kn = K / (np.linalg.norm(K, axis=-1, keepdims=True) + 1e-8)
    return qn @ kn.T


# ---------------------------------------------------------------------------
# Geometric kernel
# ---------------------------------------------------------------------------

def geometric_kernel(
    D:    np.ndarray,
    kind: str = "inv_sq",
    **params: Any,
) -> np.ndarray:
    """
    Deterministic geometric kernel — no softmax, no exponential normalization.

    D   : (n, m) distance (or similarity) matrix
    kind: one of inv_sq | inv | compact | rbf | cosine | angular
    """
    eps = params.get("eps", 1e-6)
    if kind == "inv_sq":
        alpha = params.get("alpha", 2.0)
        return 1.0 / (D ** alpha + eps)
    elif kind == "inv":
        alpha = params.get("alpha", 1.0)
        return 1.0 / (D ** alpha + eps)
    elif kind == "compact":
        r = params.get("r", 1.0)
        p = params.get("p", 2.0)
        return np.maximum(0.0, 1.0 - D / r) ** p
    elif kind == "rbf":
        sigma = params.get("sigma", 1.0)
        return np.exp(-(D ** 2) / (2.0 * sigma ** 2))
    elif kind == "cosine":
        beta = params.get("beta", 1.0)
        return np.maximum(0.0, D) ** beta     # D is similarity here
    elif kind == "angular":
        # D = arccos(cosine) ∈ [0, π]; convert to [0, 1] similarity
        return (math.pi - D) / math.pi
    else:
        raise ValueError(f"Unknown kernel kind: {kind!r}")


# ---------------------------------------------------------------------------
# Core SGAM operator (NumPy)
# ---------------------------------------------------------------------------

def sgam(
    Q: np.ndarray,            # (n, d)
    K: np.ndarray,            # (m, d)
    V: np.ndarray,            # (m, d_v)
    kernel:    str   = "inv_sq",
    radius:    Optional[float] = None,
    normalize: bool  = True,
    **kernel_params: Any,
) -> np.ndarray:
    """
    Spatial Geometric Attention.

    1. Compute pairwise distances D
    2. Apply hard locality mask (optional)
    3. Evaluate kernel G = K(D)
    4. Optional partition-of-unity normalization (NOT softmax)
    5. Aggregate Y = G V
    """
    # Distance matrix
    if kernel in ("cosine",):
        D = pairwise_cosine(Q, K)      # (n, m) similarities
    elif kernel == "angular":
        cos = pairwise_cosine(Q, K)
        D   = np.arccos(np.clip(cos, -1.0, 1.0))
    else:
        D = pairwise_euclidean(Q, K)   # (n, m) Euclidean distances

    # Hard locality mask
    if radius is not None:
        mask = D > radius
        D    = np.where(mask, np.inf, D)

    # Geometric kernel
    G = geometric_kernel(D, kind=kernel, **kernel_params)

    # Mask out inf → 0
    G = np.where(np.isfinite(G), G, 0.0)

    # Geometric normalization (partition-of-unity, NOT softmax)
    if normalize:
        row_sum = G.sum(axis=-1, keepdims=True) + 1e-6
        G       = G / row_sum

    # Aggregate
    return G @ V     # (n, d_v)


# ---------------------------------------------------------------------------
# Multi-head SGAM
# ---------------------------------------------------------------------------

@dataclass
class SGAMHeadConfig:
    kernel: str             = "inv_sq"
    radius: Optional[float] = None
    normalize: bool         = True
    kernel_params: Dict[str, Any] = field(default_factory=dict)


class SpatialGeometricAttention:
    """
    Multi-head Spatial Geometric Attention.

    Each head can use a different kernel geometry.
    No softmax anywhere.
    """

    def __init__(
        self,
        d_model:     int,
        n_heads:     int = 4,
        head_configs: Optional[list[SGAMHeadConfig]] = None,
        seed:        int = 42,
    ) -> None:
        assert d_model % n_heads == 0
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head  = d_model // n_heads

        rng   = np.random.default_rng(seed)
        sc    = 1.0 / math.sqrt(d_model)
        self.W_Q   = rng.normal(0, sc, (n_heads, d_model, self.d_head)).astype(np.float32)
        self.W_K   = rng.normal(0, sc, (n_heads, d_model, self.d_head)).astype(np.float32)
        self.W_V   = rng.normal(0, sc, (n_heads, d_model, self.d_head)).astype(np.float32)
        self.W_out = rng.normal(0, sc, (n_heads * self.d_head, d_model)).astype(np.float32)

        # Default: heads use different kernels
        defaults = [
            SGAMHeadConfig("inv_sq",  None,  True),
            SGAMHeadConfig("compact", 2.0,   True,  {"r": 2.0, "p": 3.0}),
            SGAMHeadConfig("rbf",     None,  False, {"sigma": 1.0}),
            SGAMHeadConfig("cosine",  None,  True,  {"beta": 1.5}),
        ]
        if head_configs is None:
            head_configs = [defaults[h % len(defaults)] for h in range(n_heads)]
        self.head_configs = head_configs

    def forward(
        self,
        x: np.ndarray,        # (seq, d_model)
        mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Returns (seq, d_model)."""
        seq = x.shape[0]
        head_outputs = []

        for h in range(self.n_heads):
            Q = x @ self.W_Q[h]    # (seq, d_head)
            K = x @ self.W_K[h]
            V = x @ self.W_V[h]

            cfg = self.head_configs[h]
            y_h = sgam(Q, K, V,
                       kernel    = cfg.kernel,
                       radius    = cfg.radius,
                       normalize = cfg.normalize,
                       **cfg.kernel_params)          # (seq, d_head)
            head_outputs.append(y_h)

        # Concatenate all heads → project back to d_model
        Y = np.concatenate(head_outputs, axis=-1)   # (seq, n_heads*d_head)
        return Y @ self.W_out                        # (seq, d_model)
