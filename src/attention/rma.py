"""
rma.py — Riemannian Manifold Attention (RMA)

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Attention as an intrinsic geometric operation on a Riemannian manifold (M, g).
Queries and keys are points on M; values lie in corresponding tangent spaces.
Geodesic distance measures compatibility. Aggregation uses parallel transport.
No softmax is used.

Supported geometries (model spaces):
  euclidean  : R^n, flat metric, geodesic = straight line
  sphere     : S^{n-1}, round metric, geodesic = great circle arc
  hyperbolic : H^n, Poincaré ball model, geodesic = circular arc

Euclidean Recovery Theorem:
  For M = R^m with flat g: RMA reduces exactly to SGAM with Euclidean distance.

All RMA kernels are deterministic — no softmax, no probability distribution.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass
from typing import Optional, Literal


# ---------------------------------------------------------------------------
# Geodesic distances for model spaces
# ---------------------------------------------------------------------------

def geodesic_euclidean(q: np.ndarray, k: np.ndarray) -> float:
    return float(np.linalg.norm(q - k))


def geodesic_sphere(q: np.ndarray, k: np.ndarray) -> float:
    """
    Geodesic distance on S^{n-1}: arccos(q·k / (‖q‖‖k‖))
    Points are projected to the sphere before computing distance.
    """
    qn = q / (np.linalg.norm(q) + 1e-8)
    kn = k / (np.linalg.norm(k) + 1e-8)
    cos = float(np.clip(qn @ kn, -1.0, 1.0))
    return float(math.acos(cos))


def geodesic_hyperbolic(q: np.ndarray, k: np.ndarray) -> float:
    """
    Geodesic distance in Poincaré ball model:
    d_H(q,k) = 2 arctanh(‖(-q) ⊕ k‖)

    Möbius addition: (-q) ⊕ k = ((1+2⟨-q,k⟩+‖k‖²)(-q) + (1-‖-q‖²)k)
                                  / (1 + 2⟨-q,k⟩ + ‖q‖²‖k‖²)
    """
    # Project into unit ball
    q = q / max(1.0, np.linalg.norm(q) + 1e-8) * 0.999
    k = k / max(1.0, np.linalg.norm(k) + 1e-8) * 0.999
    q_neg = -q
    qn2   = float(q_neg @ q_neg)
    kn2   = float(k @ k)
    qk    = float(q_neg @ k)
    denom = 1.0 + 2.0 * qk + qn2 * kn2
    num   = (1.0 + 2.0 * qk + kn2) * q_neg + (1.0 - qn2) * k
    mob   = num / (denom + 1e-8)
    mob_norm = float(np.clip(np.linalg.norm(mob), 0.0, 0.9999))
    return float(2.0 * math.atanh(mob_norm))


# ---------------------------------------------------------------------------
# Parallel transport (flat approximation, closed-form for model spaces)
# ---------------------------------------------------------------------------

def transport_euclidean(v: np.ndarray, src: np.ndarray, tgt: np.ndarray) -> np.ndarray:
    """Euclidean: PT is the identity map."""
    return v.copy()


def transport_sphere(v: np.ndarray, src: np.ndarray, tgt: np.ndarray) -> np.ndarray:
    """
    Parallel transport on S^{n-1} along the geodesic from src to tgt.
    Approximation via first-order Schild's ladder.
    """
    src = src / (np.linalg.norm(src) + 1e-8)
    tgt = tgt / (np.linalg.norm(tgt) + 1e-8)
    cos_d = float(np.clip(src @ tgt, -1.0, 1.0))
    if abs(cos_d - 1.0) < 1e-6:
        return v.copy()
    log_src_tgt = tgt - cos_d * src
    log_norm = np.linalg.norm(log_src_tgt) + 1e-8
    u = log_src_tgt / log_norm
    v_transported = v - (v @ u) * u - (v @ src) * src + (v @ src) * tgt
    return v_transported


# ---------------------------------------------------------------------------
# Riemannian geometric kernels
# ---------------------------------------------------------------------------

def riemannian_kernel(
    D:    np.ndarray,
    kind: str = "rbf",
    **params,
) -> np.ndarray:
    """Deterministic kernel on Riemannian geodesic distances."""
    eps = params.get("eps", 1e-6)
    if kind == "rbf":
        sigma = params.get("sigma", 1.0)
        return np.exp(-(D ** 2) / (2.0 * sigma ** 2))
    elif kind == "inv":
        alpha = params.get("alpha", 1.0)
        return 1.0 / (D ** alpha + eps)
    elif kind == "compact":
        r = params.get("r", math.pi / 2)   # π/2 natural radius for sphere
        p = params.get("p", 2.0)
        return np.maximum(0.0, 1.0 - D / r) ** p
    elif kind == "heat":
        # Heat kernel on manifold (approximated by Euclidean heat kernel)
        sigma2 = params.get("sigma2", 1.0)
        return np.exp(-(D ** 2) / (4.0 * sigma2))
    else:
        raise ValueError(f"Unknown Riemannian kernel: {kind!r}")


# ---------------------------------------------------------------------------
# Multi-manifold attention
# ---------------------------------------------------------------------------

@dataclass
class ManifoldSpec:
    geometry:  Literal["euclidean", "sphere", "hyperbolic"] = "euclidean"
    kernel:    str   = "rbf"
    normalize: bool  = True
    sigma:     float = 1.0
    radius:    Optional[float] = None


class RiemannianManifoldAttention:
    """
    Multi-head Riemannian Manifold Attention.

    Each head operates on its own model space (Euclidean / Sphere / Hyperbolic).
    No softmax. Parallel transport aligns tangent vectors before aggregation.

    Euclidean Recovery: when geometry="euclidean", reduces exactly to SGAM.
    """

    GEODESIC = {
        "euclidean":  geodesic_euclidean,
        "sphere":     geodesic_sphere,
        "hyperbolic": geodesic_hyperbolic,
    }
    TRANSPORT = {
        "euclidean":  transport_euclidean,
        "sphere":     transport_sphere,
        "hyperbolic": transport_euclidean,   # first-order fallback
    }

    def __init__(
        self,
        d_model:  int,
        n_heads:  int = 4,
        head_specs: Optional[list[ManifoldSpec]] = None,
        seed:     int = 42,
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

        if head_specs is None:
            # Default: mixed geometry across heads
            specs = [ManifoldSpec("euclidean"), ManifoldSpec("sphere"),
                     ManifoldSpec("hyperbolic"), ManifoldSpec("euclidean", "compact")]
            head_specs = [specs[h % len(specs)] for h in range(n_heads)]
        self.head_specs = head_specs

    def _pairwise_geodesic(
        self,
        Q:   np.ndarray,   # (seq, d_head)
        K:   np.ndarray,
        geo: str,
    ) -> np.ndarray:
        seq_q, seq_k = Q.shape[0], K.shape[0]
        D = np.zeros((seq_q, seq_k), dtype=np.float32)
        fn = self.GEODESIC[geo]
        for i in range(seq_q):
            for j in range(seq_k):
                D[i, j] = fn(Q[i], K[j])
        return D

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        x : (seq, d_model)
        Returns: (seq, d_model)
        """
        seq = x.shape[0]
        head_outputs = []

        for h, spec in enumerate(self.head_specs):
            Q = x @ self.W_Q[h]    # (seq, d_head)
            K = x @ self.W_K[h]
            V = x @ self.W_V[h]

            # Geodesic distance matrix
            D = self._pairwise_geodesic(Q, K, spec.geometry)

            # Hard locality
            if spec.radius is not None:
                D = np.where(D > spec.radius, np.inf, D)

            # Kernel
            G = riemannian_kernel(D, kind=spec.kernel, sigma=spec.sigma)
            G = np.where(np.isfinite(G), G, 0.0)

            if spec.normalize:
                G = G / (G.sum(axis=-1, keepdims=True) + 1e-6)

            # Parallel transport and aggregate
            transport_fn = self.TRANSPORT[spec.geometry]
            Z = np.zeros((seq, self.d_head), dtype=np.float32)
            for i in range(seq):
                for j in range(seq):
                    vt = transport_fn(V[j], K[j], Q[i])
                    Z[i] += G[i, j] * vt

            head_outputs.append(Z)

        Y = np.concatenate(head_outputs, axis=-1)    # (seq, n_heads * d_head)
        return Y @ self.W_out                        # (seq, d_model)
