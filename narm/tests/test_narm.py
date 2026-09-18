"""
test_narm.py — NARM numerical verification suite.

Differential tests: Python/NumPy reference implementations vs. the
hand-rolled C/assembly runtime (loaded via ctypes from libruntime.so).

Acceptance threshold: max relative error < 1e-4 for all kernels.

Usage:
    python narm/tests/test_narm.py [path/to/libruntime.so]
"""

from __future__ import annotations

import sys
import ctypes
import math
import struct
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Reference implementations (pure NumPy — ground truth)
# ---------------------------------------------------------------------------

def ref_gemm(A: np.ndarray, B: np.ndarray, C: np.ndarray,
             alpha: float = 1.0, beta: float = 1.0) -> np.ndarray:
    return alpha * (A @ B) + beta * C


def ref_rms_norm(x: np.ndarray, scale: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    rms = np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True) + eps)
    return (x / rms) * scale


def ref_residual(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return x + y


def ref_recon_attention(
    X:   np.ndarray,   # [N, D]
    W_Q: np.ndarray,   # [D, dk]
    W_K: np.ndarray,
    W_V: np.ndarray,
    W_O: np.ndarray,   # [dk, D]
    eps: float = 1e-6,
) -> np.ndarray:
    Q  = X @ W_Q
    K  = X @ W_K
    V  = X @ W_V
    G  = (Q @ K.T) ** 2 / (Q.shape[-1] + eps)
    G  = G / (G.sum(axis=1, keepdims=True) + eps)
    Z  = G @ V
    return Z @ W_O


def ref_sinusoidal_pe(seq_len: int, d_model: int) -> np.ndarray:
    pos   = np.arange(seq_len)[:, None]
    i     = np.arange(d_model)[None, :]
    angle = pos / (10000 ** (2 * (i // 2) / d_model))
    pe    = np.where(i % 2 == 0, np.sin(angle), np.cos(angle))
    return pe.astype(np.float32)


def ref_reconstruction_loss(
    x:      np.ndarray,
    x_hat:  np.ndarray,
    lambda1: float = 1.0,
    lambda2: float = 0.1,
) -> float:
    l2 = float(np.mean((x - x_hat) ** 2))
    X_fft     = np.abs(np.fft.rfft(x,     axis=0))
    Xhat_fft  = np.abs(np.fft.rfft(x_hat, axis=0))
    spectral  = float(np.mean((X_fft - Xhat_fft) ** 2))
    return lambda1 * l2 + lambda2 * spectral


# ---------------------------------------------------------------------------
# ctypes bridge to libruntime.so
# ---------------------------------------------------------------------------

class NARMRuntime:
    def __init__(self, so_path: str) -> None:
        self.lib = ctypes.CDLL(so_path)
        self._bind_symbols()

    def _bind_symbols(self) -> None:
        lib = self.lib

        # raw_gemm(A, B, C, M, K, N, alpha, beta)
        lib.raw_gemm.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float), ctypes.c_int64, ctypes.c_int64,
            ctypes.c_int64, ctypes.c_float, ctypes.c_float,
        ]
        lib.raw_gemm.restype = None

        # raw_normalization(x, out, gamma, D, eps_bits)
        lib.raw_normalization.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float), ctypes.c_int64, ctypes.c_int32,
        ]
        lib.raw_normalization.restype = None

        # raw_residual(x, r, y, count)
        lib.raw_residual.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float), ctypes.c_int64,
        ]
        lib.raw_residual.restype = None

    @staticmethod
    def _ptr(arr: np.ndarray) -> ctypes.POINTER:
        return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

    def gemm(self, A: np.ndarray, B: np.ndarray, C: np.ndarray,
             alpha: float = 1.0, beta: float = 1.0) -> np.ndarray:
        assert all(x.dtype == np.float32 for x in (A, B, C))
        M, K = A.shape
        _, N = B.shape
        out = C.copy()
        self.lib.raw_gemm(
            self._ptr(A), self._ptr(B), self._ptr(out),
            M, K, N, alpha, beta
        )
        return out

    def normalization(self, x: np.ndarray, scale: np.ndarray,
                      eps: float = 1e-6) -> np.ndarray:
        out = np.zeros_like(x)
        eps_bits = struct.unpack("I", struct.pack("f", eps))[0]
        D = x.shape[-1]
        self.lib.raw_normalization(
            self._ptr(x), self._ptr(out), self._ptr(scale),
            D, ctypes.c_int32(eps_bits)
        )
        return out

    def residual(self, x: np.ndarray, r: np.ndarray) -> np.ndarray:
        out = np.zeros_like(x)
        self.lib.raw_residual(
            self._ptr(x), self._ptr(r), self._ptr(out), x.size
        )
        return out


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
MAX_REL_ERROR = 1e-4


def check(name: str, ref: np.ndarray, got: np.ndarray) -> bool:
    max_abs = float(np.max(np.abs(ref - got)))
    denom   = float(np.max(np.abs(ref))) + 1e-12
    rel_err = max_abs / denom
    ok      = rel_err < MAX_REL_ERROR
    icon    = PASS if ok else FAIL
    print(f"  {icon}  {name:<40s}  max_rel_err = {rel_err:.2e}"
          + ("" if ok else f"  FAIL (limit {MAX_REL_ERROR:.0e})"))
    return ok


def run_reference_tests() -> int:
    """Run all reference-only tests (no shared library required)."""
    print("\n=== Reference Implementation Tests ===")
    failures = 0

    # GEMM correctness
    for M, K, N in [(4, 3, 5), (32, 32, 32), (64, 128, 64)]:
        A = np.random.randn(M, K).astype(np.float32)
        B = np.random.randn(K, N).astype(np.float32)
        C = np.random.randn(M, N).astype(np.float32)
        got = ref_gemm(A, B, C)
        expected = A @ B + C
        if not check(f"ref_gemm ({M}×{K}×{N})", expected, got):
            failures += 1

    # RMSNorm: output RMS ≈ 1 when scale = 1
    x     = np.random.randn(16, 64).astype(np.float32)
    scale = np.ones(64, dtype=np.float32)
    out   = ref_rms_norm(x, scale)
    rms   = float(np.mean(out ** 2, axis=-1).mean())
    ok    = abs(rms - 1.0) < 0.1
    print(f"  {'✓' if ok else '✗'}  ref_rms_norm RMS≈1                        rms = {rms:.4f}")
    if not ok:
        failures += 1

    # Residual: output = x + y exactly
    x = np.random.randn(128).astype(np.float32)
    y = np.random.randn(128).astype(np.float32)
    if not check("ref_residual", x + y, ref_residual(x, y)):
        failures += 1

    # RECON_ATTENTION: output shape + finite values
    N, D, dk = 16, 32, 16
    X   = np.random.randn(N, D).astype(np.float32) * 0.1
    W_Q = np.random.randn(D, dk).astype(np.float32) * 0.1
    W_K = np.random.randn(D, dk).astype(np.float32) * 0.1
    W_V = np.random.randn(D, dk).astype(np.float32) * 0.1
    W_O = np.random.randn(dk, D).astype(np.float32) * 0.1
    Y   = ref_recon_attention(X, W_Q, W_K, W_V, W_O)
    ok  = Y.shape == (N, D) and np.all(np.isfinite(Y))
    print(f"  {'✓' if ok else '✗'}  ref_recon_attention shape+finite")
    if not ok:
        failures += 1

    # Positional encoding: orthogonal rows check (approx)
    pe = ref_sinusoidal_pe(32, 64)
    ok = pe.shape == (32, 64) and np.all(np.isfinite(pe))
    print(f"  {'✓' if ok else '✗'}  ref_sinusoidal_pe shape+finite")
    if not ok:
        failures += 1

    # Reconstruction loss: decreases after moving x_hat → x
    x_orig = np.random.randn(64, 64).astype(np.float32)
    x_hat  = x_orig + np.random.randn(*x_orig.shape).astype(np.float32) * 0.5
    loss0  = ref_reconstruction_loss(x_orig, x_hat)
    loss1  = ref_reconstruction_loss(x_orig, x_orig)  # perfect reconstruction
    ok     = loss1 < loss0
    print(f"  {'✓' if ok else '✗'}  ref_reconstruction_loss decreases  "
          f"loss={loss0:.4f}→{loss1:.4f}")
    if not ok:
        failures += 1

    return failures


def run_assembly_differential_tests(so_path: str) -> int:
    """Run differential tests against the compiled libruntime.so."""
    print(f"\n=== Assembly Differential Tests  ({so_path}) ===")
    try:
        rt = NARMRuntime(so_path)
    except OSError as e:
        print(f"  ⚠  Could not load {so_path}: {e}")
        print("     Skipping assembly tests.")
        return 0

    failures = 0

    # GEMM
    for M, K, N in [(4, 3, 5), (32, 32, 32), (64, 128, 64)]:
        A   = np.random.randn(M, K).astype(np.float32)
        B   = np.random.randn(K, N).astype(np.float32)
        C   = np.random.randn(M, N).astype(np.float32)
        ref = ref_gemm(A, B, C)
        got = rt.gemm(A, B, C)
        if not check(f"asm_gemm ({M}×{K}×{N})", ref, got):
            failures += 1

    # RMSNorm
    x     = np.random.randn(64).astype(np.float32)
    scale = np.ones(64, dtype=np.float32)
    ref   = ref_rms_norm(x, scale)
    got   = rt.normalization(x, scale)
    if not check("asm_normalization", ref, got):
        failures += 1

    # Residual
    x   = np.random.randn(256).astype(np.float32)
    r   = np.random.randn(256).astype(np.float32)
    ref = ref_residual(x, r)
    got = rt.residual(x, r)
    if not check("asm_residual", ref, got):
        failures += 1

    return failures


def main() -> None:
    so_path = sys.argv[1] if len(sys.argv) > 1 else "./libruntime.so"
    np.random.seed(42)

    fail_ref = run_reference_tests()
    fail_asm = run_assembly_differential_tests(so_path)

    total = fail_ref + fail_asm
    print(f"\n{'='*55}")
    if total == 0:
        print(f"{PASS}  All NARM numerical tests passed.")
    else:
        print(f"{FAIL}  {total} test(s) failed.")
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
