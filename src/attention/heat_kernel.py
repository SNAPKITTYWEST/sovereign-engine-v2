"""
heat_kernel.py — Heat Kernel Attention + UMTCPI-Heat Hybrid

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Heat kernel on Euclidean space solves the heat equation: ∂u/∂t = Δu

    H(x, y, t) = (1/4πt)^{d/2} exp(-‖x-y‖² / 4t)

Properties:
  - Positive:     H(x,y,t) > 0  for all x,y,t>0
  - Semigroup:    ∫H(x,z,s)H(z,y,t)dz = H(x,y,s+t)
  - Delta limit:  t→0 gives H(x,y,t)→δ(x-y)
  - t controls diffusion: small t = sharp local; large t = diffuse global

Temperature schedule:
  - Large t: high temperature → diffuse, global attention
  - Small t: low temperature → sharp, local attention
  This is DUAL to softmax temperature but does NOT normalize to sum=1.

Hybrid: UMTCPI-Heat = B_k · J_{k,j} · H_{k,j}(t_k) · w_k
  Theorem: hybrid weights do NOT sum to 1 (simplex broken).

Spectral variant: uses graph Laplacian eigenmodes for geometry-aware diffusion.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass
from typing import Optional
from scipy.spatial.distance import pdist, squareform
try:
    from scipy.linalg import eigh as _eigh
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# ---------------------------------------------------------------------------
# Heat kernel primitives
# ---------------------------------------------------------------------------

def heat_kernel_matrix(
    Q:   np.ndarray,    # (n, d)
    K:   np.ndarray,    # (m, d)
    t:   float | np.ndarray = 1.0,  # scalar or (n,) per-row temperature
) -> np.ndarray:
    """
    H_{ij} = (1/4πt_i)^{d/2} · exp(-‖Q_i - K_j‖² / 4t_i)

    t may be a scalar (uniform) or a (n,) array (adaptive per query).
    Returns (n, m) float matrix — NOT row-normalized (sum ≠ 1).
    """
    n, d = Q.shape
    m    = K.shape[0]

    # Pairwise squared distances (n, m)
    diff = Q[:, None, :] - K[None, :, :]    # (n, m, d)
    D2   = (diff ** 2).sum(axis=-1)          # (n, m)

    # Per-row temperature
    if np.isscalar(t):
        t_row = np.full(n, t, dtype=np.float64)
    else:
        t_row = np.asarray(t, dtype=np.float64)
        assert len(t_row) == n

    # Normalization factor (1/4πt)^{d/2}
    norm = ((1.0 / (4.0 * math.pi * t_row)) ** (d / 2.0))   # (n,)

    # Exponent -D² / 4t
    exp_arg = -D2 / (4.0 * t_row[:, None])                   # (n, m)

    return norm[:, None] * np.exp(exp_arg)    # (n, m)


def temperature_schedule(
    K:      int,
    t0:     float = 1.0,
    mode:   str   = "constant",
    t_min:  float = 0.05,
    t_max:  float = 5.0,
) -> np.ndarray:
    """
    Generate a temperature vector (K,).

    Modes:
      constant  — all tokens share t0
      linear    — linearly spaced from t_min to t_max
      cosine    — cosine annealing
      learned   — returns t0 * ones (caller tunes via gradient)
    """
    if mode == "constant":
        return np.full(K, t0, dtype=np.float64)
    elif mode == "linear":
        return np.linspace(t_min, t_max, K)
    elif mode == "cosine":
        idx = np.arange(K, dtype=np.float64)
        return t_min + 0.5 * (t_max - t_min) * (1 + np.cos(math.pi * idx / K))
    else:
        return np.full(K, t0, dtype=np.float64)


# ---------------------------------------------------------------------------
# Spectral heat kernel (graph Laplacian)
# ---------------------------------------------------------------------------

def spectral_heat_kernel(
    O:   np.ndarray,   # (K, d) token embeddings
    t:   float = 1.0,
) -> np.ndarray:
    """
    H^{spec}_{k,j}(t) = Σ_ℓ exp(-λ_ℓ t) u_ℓ(k) u_ℓ(j)

    Uses eigenmodes of the normalized graph Laplacian built from token
    embedding similarities. Adapts to intrinsic geometry of the sequence.
    """
    K = O.shape[0]

    # Similarity matrix W_{k,j} = exp(-‖O_k - O_j‖²)
    D2  = squareform(pdist(O, metric="euclidean")) ** 2
    W   = np.exp(-D2)
    deg = W.sum(axis=1)
    D_inv_sqrt = np.diag(1.0 / np.sqrt(deg + 1e-8))
    L_norm = np.eye(K) - D_inv_sqrt @ W @ D_inv_sqrt

    # Eigendecomposition
    if HAS_SCIPY:
        evals, evecs = _eigh(L_norm)
    else:
        evals, evecs = np.linalg.eigh(L_norm)

    evals = np.maximum(evals, 0.0)   # clamp numerical negatives

    # H^{spec}_{k,j} = Σ_ℓ exp(-λ_ℓ t) u_ℓ(k) u_ℓ(j)
    weights = np.exp(-evals * t)     # (K,)
    H_spec  = evecs @ np.diag(weights) @ evecs.T   # (K, K)
    return H_spec.astype(np.float32)


# ---------------------------------------------------------------------------
# UMTCPI-Heat hybrid (full four-layer kernel)
# ---------------------------------------------------------------------------

class HeatKernelAttention:
    """
    Full UMTCPI-Heat Hybrid Attention.

    Layered architecture (no softmax at any stage):
      1. Boolean gates    B̃_k  (AND ⊕ NAND)
      2. Jordan product   J_{k,j} = (Q_k K_j^T + K_j Q_k^T) / 2
      3. Heat kernel      H_{k,j}(t_k)
      4. Resonance exp    w_k = exp[-π/(4r) · Δ_k]

    Final weights: α_{k,j} = B̃_k · J_{k,j} · H_{k,j} · w_k
    Aggregation:   Z_k = Σ_j α_{k,j} · V_j    (NO division, NO softmax)

    Σ_j α_{k,j} ≠ 1  (simplex broken — proved in UMTCPI framework)
    """

    def __init__(
        self,
        d:     int   = 32,
        t0:    float = 1.0,
        r:     float = 2.0,
        alpha: float = 0.1,
        temp_mode: str = "constant",
        use_spectral: bool = False,
        seed:  int = 42,
    ) -> None:
        self.d     = d
        self.t0    = t0
        self.r     = r
        self.alpha = alpha
        self.temp_mode    = temp_mode
        self.use_spectral = use_spectral

        rng  = np.random.default_rng(seed)
        sc   = 1.0 / math.sqrt(d)
        self.W_Q = rng.normal(0, sc, (d, d)).astype(np.float32)
        self.W_K = rng.normal(0, sc, (d, d)).astype(np.float32)
        self.W_V = rng.normal(0, sc, (d, d)).astype(np.float32)

    # ------------------------------------------------------------------
    # Sub-components
    # ------------------------------------------------------------------

    def _boolean_gates(self, O: np.ndarray) -> np.ndarray:
        def sig(x): return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))
        K = len(O)
        B = np.zeros(K, dtype=np.float64)
        for k in range(K):
            prev = O[k-1].mean() if k > 0 else 0.0
            nxt  = O[(k+1) % K].mean()
            g_and  = float(sig(O[k].mean() + prev))
            g_nand = 1.0 - float(sig(O[k].mean() + nxt))
            B[k]   = float(sig(2.0 * (g_and - g_nand) ** 2 - 1.0))
        return B

    def _jordan_kernel(self, Q: np.ndarray, K_mat: np.ndarray) -> np.ndarray:
        K = Q.shape[0]
        J = np.zeros((K, K), dtype=np.float64)
        for k in range(K):
            for j in range(K):
                J[k, j] = float(Q[k] @ K_mat[j]) + self.alpha * float(Q[k] @ K_mat[k])
        return J

    def _magnitude_diff(self, O: np.ndarray) -> np.ndarray:
        K  = len(O)
        mg = np.linalg.norm(O, axis=1)
        d  = np.zeros(K, dtype=np.float64)
        for k in range(K):
            d[k] = (mg[(k+1) % K] - (mg[k-1] if k > 0 else 0.0))
        return d

    def _resonance_weights(self, delta: np.ndarray) -> np.ndarray:
        return np.exp(-(math.pi / (4.0 * self.r)) * delta)

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------

    def forward(
        self, O: np.ndarray
    ) -> dict:
        """
        O : (K, d) token sequence.
        Returns dict with output, weights, and component breakdown.
        """
        K = O.shape[0]

        Q   = O @ self.W_Q
        Km  = O @ self.W_K
        V   = O @ self.W_V

        # Component 1: Boolean gates (K,)
        B = self._boolean_gates(O)

        # Component 2: Jordan kernel (K, K)
        J = self._jordan_kernel(Q, Km)

        # Component 3: Heat kernel (K, K)
        t_vec = temperature_schedule(K, self.t0, self.temp_mode)
        if self.use_spectral:
            H = spectral_heat_kernel(O, self.t0)
        else:
            H = heat_kernel_matrix(Q, Km, t=t_vec)

        # Component 4: Resonance exponential (K,)
        delta = self._magnitude_diff(O)
        w     = self._resonance_weights(delta)

        # Combine: α_{k,j} = B̃_k · J_{k,j} · H_{k,j} · w_k
        alpha = (B[:, None] * J * H) * w[:, None]   # (K, K)

        # Non-normalized aggregation
        Z = alpha @ V     # (K, d)

        return {
            "output":         Z,
            "weights":        alpha,
            "sum_weights":    alpha.sum(axis=1),    # PROVES ≠ 1
            "bool_gates":     B,
            "jordan_kernel":  J,
            "heat_kernel":    H,
            "resonance":      w,
            "temperatures":   t_vec,
        }


# ---------------------------------------------------------------------------
# Standalone SGAM-style heat attention (no UMTCPI components)
# ---------------------------------------------------------------------------

class PureHeatAttention:
    """
    Pure heat kernel attention — SGAM with RBF kernel using heat kernel formula.
    Simplest non-softmax attention: G_{ij} = H(Q_i, K_j, t)
    """

    def __init__(self, d_model: int, t: float = 1.0, normalize: bool = False) -> None:
        self.d_model   = d_model
        self.t         = t
        self.normalize = normalize
        rng = np.random.default_rng(42)
        sc  = 1.0 / math.sqrt(d_model)
        self.W_Q   = rng.normal(0, sc, (d_model, d_model)).astype(np.float32)
        self.W_K   = rng.normal(0, sc, (d_model, d_model)).astype(np.float32)
        self.W_V   = rng.normal(0, sc, (d_model, d_model)).astype(np.float32)

    def forward(self, x: np.ndarray) -> np.ndarray:
        Q = x @ self.W_Q
        K = x @ self.W_K
        V = x @ self.W_V
        G = heat_kernel_matrix(Q, K, t=self.t)
        if self.normalize:
            G = G / (G.sum(axis=-1, keepdims=True) + 1e-6)
        return G @ V
