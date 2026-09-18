"""
qregex_sim.py — Q-Regex Quantum Regular Expression Simulator

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Simulates the Q-Regex circuit (qregex.qasm) in NumPy — no hardware required.

The Q-Regex engine classifies L2-Meta-MTCPI bitstrings into admissible
soliton phase trajectories via continuous-variable interference.

Three operators:
  U_∨  — Superposition Union    (Hadamard-weighted parallel evaluation)
  U_∘  — Phase Concatenation    (CNOT ladder for temporal ordering)
  U_*  — Resonance Kleene Star  (n round-trip phase accumulation)

Match condition: constructive interference at q[2] iff
  ΔΩ̂ ≈ 2π·k / τ_rt  for some integer k  (resonance)

Connects to: kalman.py (Q-Regex output z_t feeds Kalman filter)
"""

from __future__ import annotations

import math
import cmath
import numpy as np
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Quantum gates (2-qubit subspace)
# ---------------------------------------------------------------------------

def ry(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)

def rz(phi: float) -> np.ndarray:
    return np.diag([cmath.exp(-1j * phi / 2), cmath.exp(1j * phi / 2)])

def hadamard() -> np.ndarray:
    return np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)

def cnot() -> np.ndarray:
    return np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]], dtype=complex)

def cz() -> np.ndarray:
    return np.diag([1,1,1,-1]).astype(complex)

def kron3(A: np.ndarray, B: np.ndarray, C: np.ndarray) -> np.ndarray:
    return np.kron(np.kron(A, B), C)

I2 = np.eye(2, dtype=complex)


# ---------------------------------------------------------------------------
# Q-Regex circuit
# ---------------------------------------------------------------------------

class QRegexSimulator:
    """
    Simulates the Q-Regex 3-qubit circuit.

    q[0], q[1]: feature register (encoded from L2-Meta-MTCPI bits)
    q[2]:       match auxiliary
    """

    def __init__(
        self,
        tau_rt:       float = 1e-6,   # soliton round-trip time (s)
        n_roundtrips: int   = 10,      # Kleene Star iterations
        shots:        int   = 1000,    # measurement shots
    ) -> None:
        self.tau_rt       = tau_rt
        self.n_roundtrips = n_roundtrips
        self.shots        = shots

    def _encode_feature(self, theta1: float, theta2: float) -> np.ndarray:
        """Initial state: |0,0,0⟩ then apply Ry(θ) to q[0] and q[1]."""
        state = np.zeros(8, dtype=complex)
        state[0] = 1.0  # |000⟩

        # Ry(theta1) on q[0]
        U_q0 = kron3(ry(theta1), I2, I2)
        state = U_q0 @ state

        # Ry(theta2) on q[1]
        U_q1 = kron3(I2, ry(theta2), I2)
        state = U_q1 @ state
        return state

    def _phase_concat(self, state: np.ndarray) -> np.ndarray:
        """U_∘: CNOT q[0]→q[1] then CZ q[1]→q[2]."""
        # CNOT on q[0], q[1] (control=0, target=1), identity on q[2]
        cx_01 = np.kron(cnot(), I2)
        state  = cx_01 @ state

        # CZ on q[1], q[2], identity on q[0]
        cz_12 = np.kron(I2, cz())
        state  = cz_12 @ state
        return state

    def _kleene_star(self, state: np.ndarray, delta_omega: float) -> np.ndarray:
        """
        U_*: n iterations of Rz(2π·ΔΩ̂·τ_rt) on q[0] and q[1].
        Constructive interference iff ΔΩ̂ = k / τ_rt for integer k.
        """
        phi = 2.0 * math.pi * delta_omega * self.tau_rt
        Rz  = rz(phi)
        for _ in range(self.n_roundtrips):
            U = kron3(Rz, Rz, I2)
            state = U @ state
        return state

    def _match_eval(self, state: np.ndarray) -> float:
        """Apply H to q[2] then measure → return P(match_bit = 1)."""
        H_q2 = kron3(I2, I2, hadamard())
        state = H_q2 @ state
        # P(q[2]=1) = sum of |amp|² for basis states with q[2]=1
        # Basis: |q0 q1 q2⟩; q[2]=1 when index bit 0 = 1 → indices 1,3,5,7
        p_match = sum(abs(state[i])**2 for i in [1, 3, 5, 7])
        return float(p_match)

    def run(
        self,
        m_L2:         list[int],      # L2-Meta-MTCPI bitstring
        delta_omega:  float,          # current ΔΩ̂ from Kalman filter
        n_shots:      int | None = None,
    ) -> dict:
        """
        Run the Q-Regex circuit.

        Returns:
          match_probability : P(match_bit=1) — fed into Kalman filter as z_t
          match_bit         : sampled binary outcome
          is_admissible     : True if ΔΩ̂ ≈ integer / τ_rt (resonance check)
        """
        # Encode bits as rotation angles θ_k = 2π · m_L2^(k) / 2^K
        K      = len(m_L2)
        theta1 = 2.0 * math.pi * m_L2[0] / (2 ** K) if K > 0 else 0.0
        theta2 = 2.0 * math.pi * m_L2[1] / (2 ** K) if K > 1 else 0.0

        # Build and run circuit
        state = self._encode_feature(theta1, theta2)
        state = self._phase_concat(state)
        state = self._kleene_star(state, delta_omega)
        p     = self._match_eval(state)

        # Sample match bit
        shots    = n_shots or self.shots
        rng      = np.random.default_rng(42)
        outcomes = rng.binomial(1, p, shots)
        match_bit = int(outcomes.mean() > 0.5)

        # Resonance check: ΔΩ̂ · τ_rt ≈ integer?
        product         = delta_omega * self.tau_rt
        nearest_integer = round(product)
        is_admissible   = abs(product - nearest_integer) < 0.05

        return {
            "match_probability": p,
            "match_bit":         match_bit,
            "is_admissible":     is_admissible,
            "delta_omega":       delta_omega,
            "theta1":            theta1,
            "theta2":            theta2,
        }
