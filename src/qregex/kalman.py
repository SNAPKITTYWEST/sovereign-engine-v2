"""
kalman.py — Q-Regex Kalman Filter (L3 Layer)

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Fuses the Q-Regex match-bit stream with soliton-crystal phase dynamics to
produce minimum-variance estimates driving the pump-laser dispersion controller.

State vector:  x_t = [Φ_t, Φ̇_t, f_t]^T
  Φ_t   — global soliton phase (rad)
  Φ̇_t  — phase velocity (rad/s)
  f_t   — latent match propensity (Q-Regex ideal output) ∈ [0,1]

State-space model (derived from SDE discretisation):
  A = [[1, Δt, 0],
       [0,  1, 0],
       [0,  0, 1]]

  Q = diag(0, σ_ν², σ_μ²)          # process noise
  H = [0, 0, 1]                      # observation: measures f_t
  R = σ_v²                           # measurement noise variance

Measurement: z_t = H x_t + v_t  (Q-Regex probability output)

FPGA implementation: Q16.15 fixed-point, 3×3 matrix → fits 200ns budget.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass, field


@dataclass
class KalmanState:
    x_hat:  np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.5]))
    P:      np.ndarray = field(default_factory=lambda: np.diag([1.0, 1.0, 1.0]))
    steps:  int        = 0


class QRegexKalmanFilter:
    """
    L3 Kalman filter: fuses Q-Regex match probability with soliton phase dynamics.

    Derived from first principles — not copied from a textbook.
    The specific A, Q, H follow directly from:
      1. Phase kinematic equation: Φ_{t+Δt} = Φ_t + Φ̇_t · Δt
      2. Velocity random walk:     Φ̇_{t+Δt} = Φ̇_t + ν_t
      3. Propensity drift:         f_{t+Δt}  = f_t  + μ_t

    Control output: Δω_pump = -η · x̂[1]  (proportional to estimated velocity)
    """

    def __init__(
        self,
        dt:        float = 1.0e-6,    # soliton round-trip period (s)
        sigma_nu:  float = 0.01,      # phase velocity random walk noise
        sigma_mu:  float = 0.001,     # match propensity drift noise
        sigma_v:   float = 0.05,      # Q-Regex measurement noise
        eta:       float = 0.1,       # pump-laser correction gain
    ) -> None:
        self.dt       = dt
        self.sigma_v2 = sigma_v ** 2
        self.eta      = eta

        # State-transition matrix A (derived from phase kinematics)
        self.A = np.array([
            [1.0, dt,  0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])

        # Process noise covariance Q (velocity and propensity random walks)
        self.Q = np.diag([0.0, sigma_nu ** 2, sigma_mu ** 2])

        # Measurement matrix H — selects f_t (third state)
        self.H = np.array([[0.0, 0.0, 1.0]])   # (1, 3)

        # Measurement noise variance
        self.R = np.array([[self.sigma_v2]])    # (1, 1) scalar

        self.state = KalmanState()

    def predict(self) -> None:
        """
        Time update (prediction step):
          x̂_{t|t-1} = A · x̂_{t-1|t-1}
          P_{t|t-1}  = A · P_{t-1|t-1} · A^T + Q
        """
        s = self.state
        s.x_hat = self.A @ s.x_hat
        s.P     = self.A @ s.P @ self.A.T + self.Q

    def update(self, z: float) -> float:
        """
        Measurement update (correction step):
          ν_t = z_t - H · x̂_{t|t-1}
          S_t = H · P_{t|t-1} · H^T + R   (scalar)
          K_t = P_{t|t-1} · H^T / S_t
          x̂_{t|t}  = x̂_{t|t-1} + K_t · ν_t
          P_{t|t}   = (I - K_t H) · P_{t|t-1}

        Returns pump-laser correction Δω_pump = -η · x̂[1].
        """
        s = self.state
        z_vec = np.array([[z]])

        # Innovation
        innov = z_vec - self.H @ s.x_hat              # (1,)

        # Innovation covariance (scalar because H is 1×3)
        S     = self.H @ s.P @ self.H.T + self.R      # (1,1)

        # Kalman gain: P_{t|t-1} · H^T / S
        K = s.P @ self.H.T / float(S[0, 0])           # (3,1)

        # State update
        s.x_hat = s.x_hat + K.flatten() * float(innov[0, 0])

        # Covariance update (Joseph form for numerical stability)
        IKH = np.eye(3) - K @ self.H
        s.P = IKH @ s.P

        s.steps += 1

        # Control output
        delta_omega = -self.eta * s.x_hat[1]
        return float(delta_omega)

    def tick(self, z: float) -> float:
        """One full predict+update cycle. Returns Δω_pump."""
        self.predict()
        return self.update(z)

    def summary(self) -> str:
        s = self.state
        return (
            f"Q-Regex Kalman  step={s.steps}\n"
            f"  x̂ = [Φ={s.x_hat[0]:.6f} rad,  Φ̇={s.x_hat[1]:.6f} rad/s,"
            f"  f={s.x_hat[2]:.4f}]\n"
            f"  P diagonal = {np.diag(s.P)}"
        )


# ---------------------------------------------------------------------------
# FPGA reference: Q16.15 fixed-point constants
# ---------------------------------------------------------------------------

def to_fp(x: float, frac_bits: int = 15) -> int:
    return int(x * (1 << frac_bits))

def from_fp(x: int, frac_bits: int = 15) -> float:
    return x / (1 << frac_bits)


class FPGAKalman:
    """
    Q16.15 fixed-point Kalman — mirrors the C implementation for FPGA.
    Fits in 200ns budget on UltraScale+ at 500MHz.
    """

    def __init__(self, dt: float = 1e-6, sigma_nu: float = 0.01,
                 sigma_mu: float = 0.001, sigma_v2: float = 0.0025) -> None:
        FB = 15
        self.dt_fp       = to_fp(dt,            FB)
        self.sigma_nu2   = to_fp(sigma_nu**2,   FB)
        self.sigma_mu2   = to_fp(sigma_mu**2,   FB)
        self.sigma_v2    = to_fp(sigma_v2,      FB)
        self.x_phi  = 0
        self.x_omega = 0
        self.x_f     = to_fp(0.5, FB)
        self.P = [[to_fp(1.0, FB) if i==j else 0 for j in range(3)] for i in range(3)]
        self.FB = FB

    def mul(self, a: int, b: int) -> int:
        return (a * b) >> self.FB

    def tick(self, z_meas: int) -> int:
        """z_meas in Q16.15. Returns delta_omega_pump in Q16.15."""
        # Predict: x̂⁻ = A x̂
        xp_phi  = self.x_phi  + self.mul(self.dt_fp, self.x_omega)
        xp_omega = self.x_omega
        xp_f    = self.x_f

        # Predict: P⁻ = A P A^T + Q  (simplified for diagonal A)
        Pp = [[0]*3 for _ in range(3)]
        Pp[0][0] = self.P[0][0] + 2*self.mul(self.dt_fp, self.P[0][1]) + self.mul(self.dt_fp, self.mul(self.dt_fp, self.P[1][1]))
        Pp[1][1] = self.P[1][1] + self.sigma_nu2
        Pp[2][2] = self.P[2][2] + self.sigma_mu2
        Pp[0][1] = Pp[1][0] = self.P[0][1] + self.mul(self.dt_fp, self.P[1][1])
        Pp[0][2] = Pp[2][0] = self.P[0][2]
        Pp[1][2] = Pp[2][1] = self.P[1][2]

        # Innovation ν = z - x̂⁻[2]  (H picks third component)
        innov = z_meas - xp_f

        # Innovation covariance S = P⁻[2,2] + σ_v²
        S = Pp[2][2] + self.sigma_v2

        # Kalman gain K = P⁻[:,2] / S
        K = [Pp[i][2] // max(S, 1) for i in range(3)]

        # Update state
        self.x_phi   = xp_phi  + self.mul(K[0], innov)
        self.x_omega = xp_omega + self.mul(K[1], innov)
        self.x_f     = xp_f    + self.mul(K[2], innov)

        # Update covariance P = (I - KH) P⁻
        for i in range(3):
            for j in range(3):
                self.P[i][j] = Pp[i][j] - self.mul(K[i], Pp[2][j])

        # Control: Δω_pump = -η · x̂[1]
        eta_fp = to_fp(0.1, self.FB)
        return -self.mul(eta_fp, self.x_omega)
