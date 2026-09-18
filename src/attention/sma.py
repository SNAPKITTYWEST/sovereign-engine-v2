"""
sma.py — Symplectic Manifold Attention (SMA)

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Attention as an intrinsic operation on a symplectic manifold (M, ω)
where ω is a closed, non-degenerate 2-form.

A compatible almost-complex structure J induces the metric g(X,Y) = ω(X,JY).
Query-key interaction is measured by geodesic distance in this compatible metric.
Aggregation uses parallel transport; no softmax is used.

In Darboux coordinates: ω = Σᵢ dqⁱ ∧ dpᵢ
Compatible metric: g(X,Y) = ω(X,JY)  where J² = -I, ω(JX,JY) = ω(X,Y)

Symplectic invariants used as kernel inputs:
  - Geodesic distance d_g(q, k) under compatible metric g
  - Poisson bracket {f_q, f_k} = ω(X_{f_q}, X_{f_k})
  - Symplectic capacity of minimal ball containing both points

No softmax. Geometric (partition-of-unity) normalization is optional.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Symplectic form (Darboux canonical form on R^{2n})
# ---------------------------------------------------------------------------

def canonical_omega(dim2n: int) -> np.ndarray:
    """
    Canonical symplectic form ω on R^{2n}.
    ω = Σᵢ dqⁱ ∧ dpᵢ  represented as the matrix:
        [ 0   I_n ]
        [-I_n  0  ]
    """
    n = dim2n // 2
    Z = np.zeros((n, n), dtype=np.float32)
    I = np.eye(n, dtype=np.float32)
    return np.block([[Z, I], [-I, Z]])


def canonical_J(dim2n: int) -> np.ndarray:
    """
    Standard compatible almost-complex structure J on R^{2n}:
        J = [ 0  -I_n ]
            [ I_n  0  ]
    Satisfies J² = -I, ω(JX,JY) = ω(X,Y).
    """
    n = dim2n // 2
    Z = np.zeros((n, n), dtype=np.float32)
    I = np.eye(n, dtype=np.float32)
    return np.block([[Z, -I], [I, Z]])


def compatible_metric(omega: np.ndarray, J: np.ndarray) -> np.ndarray:
    """
    g(X,Y) = ω(X,JY)
    As a matrix: g = ω @ J
    """
    return omega @ J


# ---------------------------------------------------------------------------
# Geodesic distance under compatible metric
# ---------------------------------------------------------------------------

def symplectic_distance(
    q: np.ndarray,
    k: np.ndarray,
    g: np.ndarray,
) -> float:
    """
    Geodesic distance between two points in the flat symplectic manifold
    (R^{2n}, g) where g is the compatible metric matrix.

    For flat space: d_g(q, k) = sqrt((q-k)^T g (q-k))  (Mahalanobis-like)
    """
    diff = q - k
    return float(np.sqrt(max(0.0, diff @ g @ diff)))


def poisson_bracket(
    q: np.ndarray,
    k: np.ndarray,
    omega: np.ndarray,
) -> float:
    """
    Symplectic pairing ω(q, k) as a proxy for the Poisson bracket.
    In Darboux coords: {f,g} = ω(X_f, X_g), approximated here as q^T ω k.
    """
    return float(q @ omega @ k)


# ---------------------------------------------------------------------------
# Symplectic geometric kernels
# ---------------------------------------------------------------------------

def symplectic_kernel(
    D: np.ndarray,    # (n, m) geodesic distances
    kind: str = "rbf",
    **params,
) -> np.ndarray:
    """Deterministic kernel on symplectic distances — no softmax."""
    eps = params.get("eps", 1e-6)
    if kind == "rbf":
        sigma = params.get("sigma", 1.0)
        return np.exp(-(D ** 2) / (2.0 * sigma ** 2))
    elif kind == "inv":
        alpha = params.get("alpha", 1.0)
        return 1.0 / (D ** alpha + eps)
    elif kind == "compact":
        r = params.get("r", 2.0)
        p = params.get("p", 2.0)
        return np.maximum(0.0, 1.0 - D / r) ** p
    else:
        raise ValueError(f"Unknown kernel: {kind!r}")


# ---------------------------------------------------------------------------
# Parallel transport (flat approximation)
# ---------------------------------------------------------------------------

def parallel_transport_flat(
    v:      np.ndarray,    # tangent vector at source
    source: np.ndarray,    # source point
    target: np.ndarray,    # target point
    g:      np.ndarray,    # metric matrix
) -> np.ndarray:
    """
    Parallel transport along straight-line geodesic in flat (R^{2n}, g).
    In flat space, parallel transport is the identity map, so v is returned
    unchanged. In curved generalizations, integrate the PT ODE.
    """
    # Flat case: PT = identity
    return v.copy()


# ---------------------------------------------------------------------------
# Core SMA operator
# ---------------------------------------------------------------------------

class SymplecticManifoldAttention:
    """
    Symplectic Manifold Attention.

    Queries and keys are embedded into R^{2n} (the flat symplectic space).
    Compatibility is measured by geodesic distance under g = ω J.
    Values are tangent vectors transported to the query tangent space.
    No softmax is used.

    Parameters
    ----------
    d_model : original feature dimension (projected to dim2n = 2n)
    dim2n   : symplectic manifold dimension (must be even)
    kernel  : geometric kernel type
    normalize : apply partition-of-unity row normalization
    """

    def __init__(
        self,
        d_model:   int,
        dim2n:     int = 64,
        kernel:    str = "rbf",
        normalize: bool = False,
        seed:      int  = 42,
        **kernel_params,
    ) -> None:
        assert dim2n % 2 == 0, "Symplectic manifold dim must be even"
        self.d_model      = d_model
        self.dim2n        = dim2n
        self.kernel       = kernel
        self.normalize    = normalize
        self.kernel_params = kernel_params

        # Canonical symplectic structures
        self.omega = canonical_omega(dim2n)   # (2n, 2n) symplectic form
        self.J     = canonical_J(dim2n)       # (2n, 2n) complex structure
        self.g     = compatible_metric(self.omega, self.J)  # compatible metric

        # Learnable projections
        rng  = np.random.default_rng(seed)
        sc   = 1.0 / math.sqrt(d_model)
        self.W_Q   = rng.normal(0, sc, (d_model, dim2n)).astype(np.float32)
        self.W_K   = rng.normal(0, sc, (d_model, dim2n)).astype(np.float32)
        self.W_V   = rng.normal(0, sc, (d_model, dim2n)).astype(np.float32)
        self.W_out = rng.normal(0, sc, (dim2n, d_model)).astype(np.float32)

    def forward(
        self,
        x: np.ndarray,    # (seq, d_model)
        return_weights: bool = False,
    ) -> np.ndarray | tuple:
        seq = x.shape[0]

        # Project into symplectic manifold
        Q = x @ self.W_Q    # (seq, 2n) — points on M
        K = x @ self.W_K    # (seq, 2n)
        V = x @ self.W_V    # (seq, 2n) — tangent vectors at K

        # Pairwise geodesic distances under compatible metric g
        D = np.zeros((seq, seq), dtype=np.float32)
        for i in range(seq):
            for j in range(seq):
                D[i, j] = symplectic_distance(Q[i], K[j], self.g)

        # Geometric kernel (no softmax)
        G = symplectic_kernel(D, kind=self.kernel, **self.kernel_params)

        # Optional partition-of-unity normalization
        if self.normalize:
            G = G / (G.sum(axis=-1, keepdims=True) + 1e-6)

        # Parallel transport and aggregate
        Z = np.zeros((seq, self.dim2n), dtype=np.float32)
        for i in range(seq):
            for j in range(seq):
                v_transported = parallel_transport_flat(V[j], K[j], Q[i], self.g)
                Z[i] += G[i, j] * v_transported

        out = Z @ self.W_out     # (seq, d_model)

        if return_weights:
            return out, G
        return out

    def symplectic_summary(self) -> dict:
        """Return symplectic structural constants."""
        return {
            "dim2n":       self.dim2n,
            "omega_rank":  int(np.linalg.matrix_rank(self.omega)),
            "J_squared":   np.allclose(self.J @ self.J, -np.eye(self.dim2n), atol=1e-5),
            "g_positive":  bool(np.all(np.linalg.eigvalsh(self.g) > 0)),
            "kernel":      self.kernel,
        }
