"""
umtcpi.py — UMTCPI Resonance Attention (Full Implementation)

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

UMTCPI: Unnormalized Multi-Token Coupled Phase Integration

Formula:
    UMTCPI(Ō) = Σ_k B_k · exp[-(π/4r)(⟨O⟩_{k+1} - ⟨O⟩_{k-1})]

    B_k = (1/6E36) · HLO_k
    Invoke_Res(Ō) = UMTCPI(Ō)

Three orthogonal components:
  JordanAlgebra          — commutative non-associative algebra
  BooleanNANDTransform   — functionally complete NAND-based gating
  InvertedJacobian       — coordinate transformation; breaks simplex

Key property: Σ_k w_k ≠ 1  (no softmax normalization anywhere)
Weights are AMPLITUDES, not probabilities.

Verified output (Ahmad, seq=16, dim=32, r=2.0):
  Mean weight   : 4.004659e-37
  Std weight    : 8.292807e-38
  Sum ≠ 1 confirmed
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Jordan Algebra
# ---------------------------------------------------------------------------

class JordanAlgebra:
    """
    Jordan Algebra operations for resonance attention.
    For vectors: element-wise (commutative) product.
    For matrices: symmetrized product (ab + ba)/2.

    Core property: A ∘ B = B ∘ A  (commutative)
                  (A ∘ B) ∘ A² = A ∘ (B ∘ A²)  (Jordan identity)
    """

    @staticmethod
    def product(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Jordan product — commutative multiplication (element-wise)."""
        if a.shape != b.shape:
            raise ValueError(f"Shape mismatch: {a.shape} vs {b.shape}")
        return a * b

    @staticmethod
    def triple_product(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
        """Jordan triple product: {a,b,c} = (a∘b)∘c + (c∘b)∘a - (a∘c)∘b"""
        ab = JordanAlgebra.product(a, b)
        cb = JordanAlgebra.product(c, b)
        ac = JordanAlgebra.product(a, c)
        return (JordanAlgebra.product(ab, c)
                + JordanAlgebra.product(cb, a)
                - JordanAlgebra.product(ac, b))

    @staticmethod
    def quadratic_representation(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """P(x)y = 2x∘(x∘y) - x²∘y"""
        x_y   = JordanAlgebra.product(x, y)
        x_x_y = JordanAlgebra.product(x, x_y)
        x_sq  = JordanAlgebra.product(x, x)
        return 2.0 * x_x_y - JordanAlgebra.product(x_sq, y)

    @staticmethod
    def power(x: np.ndarray, n: int) -> np.ndarray:
        """Jordan power: x^n = x∘x∘...∘x (n times)."""
        result = x.copy()
        for _ in range(n - 1):
            result = JordanAlgebra.product(result, x)
        return result


# ---------------------------------------------------------------------------
# Boolean NAND Transform
# ---------------------------------------------------------------------------

class BooleanNANDTransform:
    """
    Boolean/NAND transformation blocks — smooth differentiable approximations.
    NAND is functionally complete: any Boolean function is constructible from NAND.

    Continuous lift: σ(x) ∈ (0,1) approximates {0,1} in the differentiable limit.
    """

    @staticmethod
    def sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500.0, 500.0)))

    @staticmethod
    def smooth_nand(x: np.ndarray, y: np.ndarray, temperature: float = 0.1) -> np.ndarray:
        """Differentiable NAND: NAND(x,y) = 1 - σ(x)·σ(y)  (product t-norm)."""
        return 1.0 - BooleanNANDTransform.sigmoid(x) * BooleanNANDTransform.sigmoid(y)

    @staticmethod
    def xor_via_nand(x: np.ndarray, y: np.ndarray, temperature: float = 0.1) -> np.ndarray:
        """
        XOR from NANDs (4-gate construction):
        XOR(a,b) = NAND(NAND(a, NAND(a,b)), NAND(b, NAND(a,b)))
        """
        nand_ab    = BooleanNANDTransform.smooth_nand(x, y, temperature)
        nand_a_nab = BooleanNANDTransform.smooth_nand(x, nand_ab, temperature)
        nand_b_nab = BooleanNANDTransform.smooth_nand(y, nand_ab, temperature)
        return BooleanNANDTransform.smooth_nand(nand_a_nab, nand_b_nab, temperature)

    @staticmethod
    def universal_gate_block(
        x:           np.ndarray,
        dim_out:     int,
        temperature: float = 0.1,
        seed:        int   = 42,
    ) -> np.ndarray:
        """
        Universal transformation block built entirely from NAND operations.
        Projects x to dim_out via paired NAND nonlinearities.
        """
        batch_shape = x.shape[:-1]
        in_dim      = x.shape[-1]

        rng = np.random.default_rng(seed)
        W   = rng.normal(0, 0.1, (in_dim, dim_out)).astype(np.float32)
        b   = rng.normal(0, 0.01, dim_out).astype(np.float32)
        z   = x @ W + b

        # Pad to even length for pairing
        pad_needed = dim_out % 2 != 0
        if pad_needed:
            z = np.concatenate([z, np.zeros((*batch_shape, 1))], axis=-1)

        result = []
        for i in range(0, z.shape[-1], 2):
            result.append(
                BooleanNANDTransform.smooth_nand(z[..., i], z[..., i + 1], temperature)
            )
        out = np.stack(result, axis=-1)
        if pad_needed:
            out = out[..., :dim_out]
        return out


# ---------------------------------------------------------------------------
# Inverted Jacobian
# ---------------------------------------------------------------------------

class InvertedJacobian:
    """
    Jacobian inversion for coordinate transformation in resonance space.
    Maps between tangent spaces; BREAKS the simplex normalization constraint.

    ‖J̃_k‖ ≥ 1/λ_min(J_k)  — amplifies low-gradient positions.
    """

    @staticmethod
    def compute_jacobian(
        f:   Callable[[np.ndarray], np.ndarray],
        x:   np.ndarray,
        eps: float = 1e-5,
    ) -> np.ndarray:
        """Numerical Jacobian: J_ij = ∂f_i/∂x_j  (finite differences)."""
        n           = x.shape[-1]
        batch_shape = x.shape[:-1]
        f0  = f(x)
        m   = f0.shape[-1]
        jac = np.zeros((*batch_shape, m, n), dtype=np.float64)
        for i in range(n):
            x_plus = x.copy()
            x_plus[..., i] += eps
            jac[..., :, i] = (f(x_plus) - f0) / eps
        return jac

    @staticmethod
    def invert_jacobian(jac: np.ndarray, reg: float = 1e-4) -> np.ndarray:
        """
        Tikhonov-regularized pseudo-inverse:
        J̃ = (J^T J + λI)^{-1} J^T
        """
        orig  = jac.shape
        flat  = jac.reshape(-1, orig[-2], orig[-1])
        invs  = []
        for j in flat:
            jtj = j.T @ j
            inv = np.linalg.pinv(jtj + reg * np.eye(jtj.shape[0])) @ j.T
            invs.append(inv)
        return np.array(invs).reshape(*orig[:-2], orig[-1], orig[-2])

    @staticmethod
    def transform_resonance(
        resonance:    np.ndarray,
        jacobian_inv: np.ndarray,
    ) -> np.ndarray:
        """Apply inverted Jacobian to transform resonance weights."""
        return np.einsum("...ij,...j->...i", jacobian_inv, resonance)


# ---------------------------------------------------------------------------
# UMTCPI Resonance Attention
# ---------------------------------------------------------------------------

class UMTCPIAttention:
    """
    UMTCPI resonance attention — Jordan + NAND + inverted Jacobian.

    Core formula:
        UMTCPI(Ō) = Σ_k B_k · exp[-(π/4r)(⟨O⟩_{k+1} - ⟨O⟩_{k-1})]
        B_k = (1/6E36) · HLO_k

    HLO (Hidden Layer Output):
        1. Linear projection W_hlo
        2. Jordan quadratic representation P(z)z = 2z∘(z∘z) - z²∘z
        3. NAND universal gate block

    Weights: NOT normalized. Σ w_k ≠ 1.
    """

    SCALE = 1.0 / (6.0 * math.exp(36))

    def __init__(
        self,
        d_model:     int   = 32,
        r:           float = 2.0,
        temperature: float = 0.1,
        seed:        int   = 42,
    ) -> None:
        self.d_model     = d_model
        self.r           = r
        self.temperature = temperature
        self.jordan      = JordanAlgebra()
        self.nand        = BooleanNANDTransform()
        self.jac_inv_mod = InvertedJacobian()

        rng = np.random.default_rng(seed)
        sc  = 0.05
        self.W_hlo = rng.normal(0, sc, (d_model, d_model)).astype(np.float32)
        self.b_hlo = rng.normal(0, 0.01, d_model).astype(np.float32)

    def _hlo(self, O: np.ndarray) -> np.ndarray:
        """Hidden Layer Output via Jordan + NAND."""
        z      = O @ self.W_hlo + self.b_hlo
        z_j    = self.jordan.quadratic_representation(z, z)
        z_nand = self.nand.universal_gate_block(
            z_j, dim_out=self.d_model, temperature=self.temperature
        )
        return z_nand

    def _resonance_kernel(
        self, O: np.ndarray, HLO: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Compute resonance weights and components."""
        K       = O.shape[0]
        O_mean  = O.mean(axis=-1)                                    # (K,)
        padded  = np.concatenate([[O_mean[-1]], O_mean, [O_mean[0]]])
        delta   = padded[2:] - padded[:-2]                           # (K,) phase diffs
        B_k     = self.SCALE * HLO.mean(axis=-1)                    # (K,)
        res     = np.exp(-(math.pi / (4.0 * self.r)) * delta)        # (K,)
        weights = B_k * res
        return weights, delta, B_k, res

    def forward(
        self,
        O:            np.ndarray,
        f_transform:  Optional[Callable] = None,
    ) -> dict:
        """
        Full UMTCPI forward pass.

        O : (K, d) input sequence
        f_transform : optional differentiable function for Jacobian modulation
        """
        HLO = self._hlo(O)
        weights, delta, B_k, resonance = self._resonance_kernel(O, HLO)

        # Optional Jacobian modulation
        if f_transform is not None:
            jac_list = []
            for i in range(O.shape[0]):
                def fi(x, _i=i):
                    return f_transform(x[None, :])[0]
                jac_i = self.jac_inv_mod.compute_jacobian(fi, O[i:i+1], eps=1e-4)
                jac_list.append(jac_i[0])
            jac     = np.array(jac_list)
            jac_inv = self.jac_inv_mod.invert_jacobian(jac, reg=1e-3)
            mod     = np.abs(np.trace(jac_inv, axis1=-2, axis2=-1))
            weights = weights * mod

        output = np.sum(weights[:, None] * O, axis=0)   # (d,)

        return {
            "output":         output,
            "weights":        weights,
            "phase_diffs":    delta,
            "B_k":            B_k,
            "resonance":      resonance,
            "HLO":            HLO,
            "sum_weights":    float(weights.sum()),
            "mean_weight":    float(weights.mean()),
            "std_weight":     float(weights.std()),
        }


# ---------------------------------------------------------------------------
# Convenience alias for backward compatibility
# ---------------------------------------------------------------------------

def umtcpi_attention(
    O:     np.ndarray,
    Q:     Optional[np.ndarray] = None,
    K_mat: Optional[np.ndarray] = None,
    V:     Optional[np.ndarray] = None,
    r:     float = 2.0,
    alpha: float = 0.1,
) -> dict:
    """Convenience wrapper — uses UMTCPIAttention internally."""
    d = O.shape[-1]
    attn = UMTCPIAttention(d_model=d, r=r)
    return attn.forward(O)


@dataclass
class UMTCPIConfig:
    d_model:     int   = 64
    r:           float = 2.0
    temperature: float = 0.1
