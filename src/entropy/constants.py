"""
Sovereign constants — θ = 89/2462 and derived bounds.

Source: github.com/SNAPKITTYWEST/sovereign-entropy-theorem

θ appears in:
  1. QuantumAP: phase coupling of the NC torus T²_θ
  2. Free energy: optimal T₀ for maximum extraction per cycle
  3. Fixed point: dF/dT₀ = 0 for the free energy functional

Continued fraction: [0; 27, 1, 1, 1, 2, 1, 1, 2, 1, 1, 2, ...]

The entropy bound H ≤ 0.20 nats is formally proved in Lean 4 in
formal/sovereign_entropy/EntropyBound.lean. It appears identically in:
  - BURT-IMMA router (entropy_constrained_softmax)
  - bert-agent Invariants.lean INV-5
  - QRA router (zero-entropy tensor)
  - Resonance UMO coherence gate (ε < 0.21)
  - sovereign-engine-v2 routing pipeline
  - quantumap hallucination detector
  - FORGE output integrity membrane

Not a coincidence — a design decision. One bound, entire sovereign stack.
"""

THETA_NUM     = 89
THETA_DEN     = 2462
THETA         = THETA_NUM / THETA_DEN   # 0.036163...

T0_DEFAULT    = 0.1      # Base temperature (≤ THETA satisfies H < 0.20)
ALPHA_DEFAULT = 2.0      # Cooling rate (≥ 2.34 guarantees H < 0.20)
H_MAX         = 0.20     # Entropy bound (nats) — formally proved
THRESHOLD     = 512.0    # MetaSum threshold (N_ACTIVE / 2)
T_UPPER_BOUND = 0.2218   # T(F) ≤ 0.2218 for all F ≥ 1
S_LOWER_BOUND = 90.75    # exp(d/T) ≥ 90.75 when T ≤ T_UPPER_BOUND, d ≥ 1
D_MIN         = 1.0      # Minimum logit difference for bound to hold
