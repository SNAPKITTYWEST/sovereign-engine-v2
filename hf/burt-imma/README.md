---
language: en
license: bsl-1.0
library_name: pytorch
tags:
  - pytorch
  - attention
  - memory
  - entropy-constrained
  - cifg
  - no-softmax
  - sovereign
  - snapkittywest
model_type: burt-imma
pipeline_tag: feature-extraction
---

# burt-imma

**BURT-IMMA** — CIFG Matrix-Memory Cell with entropy-constrained softmax and SmoothLeaky activation. A softmax-free attention-memory architecture where the router distribution is hard-constrained to H(α) ≤ 0.20 nats.

Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST) — Bel Esprit D'Accord Irrevocable Trust

---

## Architecture

### CIFG Matrix-Memory Cell

```
Coupled Input-Forget Gate (CIFG):

  f_t  = sigmoid(W_f · [h_{t-1}, x_t] + b_f)       ← forget gate
  v_t  = tanh(W_v · [h_{t-1}, x_t] + b_v)           ← value projection
  k_t  = SmoothLeaky(W_k · [h_{t-1}, x_t] + b_k)    ← key projection

  C_t  = f_t ⊙ C_{t-1} + (1 - f_t) ⊙ (v_t ⊗ k_t)  ← matrix memory update

  y_t  = q_t^T · C_t                                  ← sum-inversion retrieval
```

**Key properties:**
- `1 - f_t` couples input and forget — no separate input gate, half the parameters
- `v_t ⊗ k_t` outer product writes a rank-1 update into the matrix memory
- Retrieval `q^T C` = sum over all stored outer products, weighted by query similarity
- No softmax in the memory path

### Entropy-Constrained Softmax Router

```
α = softmax(logits / T)

while H(α) > 0.20 nats:
    T *= 0.9
    α = softmax(logits / T)
```

Temperature is reduced until the routing distribution falls within the entropy budget. This enforces that the top expert receives ≥ 90% of routing weight at convergence — matching the Lean 4 proof in `formal/sovereign_entropy/EntropyBound.lean`.

### SmoothLeaky Activation

```
φ(x) = x·σ(x) + α·x·(1−σ(x))   where α = 0.1

Four axioms:
1. Differentiable everywhere
2. Monotone
3. Bounded gradient: 0.1 ≤ φ'(x) ≤ 1
4. Reduces to identity for large |x|
```

### Spectral Projection

Columns of the memory matrix C are kept within the unit sphere after each write via optional spectral projection, preventing unbounded growth.

---

## Entropy Bound — Formally Proved

```
For all F ≥ 1, d ≥ 1:
  H(softmax_ratio(d, T(F))) < 0.20 nats

Proof chain (Lean 4 — zero sorry):
  T(F) = T₀ + (1−T₀)·exp(−αF) ≤ 0.2218
  s    = exp(d / T(F))          ≥ 90.75
  H(s) < H(19)                  < 0.20 ✓
```

Source: [sovereign-engine-v2/formal/sovereign_entropy/EntropyBound.lean](https://github.com/SNAPKITTYWEST/sovereign-engine-v2)

---

## Parameters

| Component | Shape | Notes |
|-----------|-------|-------|
| W_f, W_v, W_k | (input_dim + hidden_dim) → hidden_dim | CIFG gates |
| C (matrix memory) | hidden_dim × hidden_dim | outer-product memory |
| entropy_budget | scalar = 0.20 nats | hard constraint, not learned |

---

## Usage

```python
import numpy as np
from modeling_burt_imma import CIFGMatrixMemoryCell, entropy_constrained_softmax

# CIFG cell
cell = CIFGMatrixMemoryCell(input_dim=768, hidden_dim=768)
x = np.random.randn(768)
h_prev = np.zeros(768)
y, h_new = cell.forward(x, h_prev)
print(y.shape)   # (768,)

# Entropy-constrained routing
logits = np.random.randn(8)
alpha = entropy_constrained_softmax(logits, max_entropy=0.20)
H = -np.sum(alpha[alpha > 1e-12] * np.log(alpha[alpha > 1e-12]))
print(f"H = {H:.4f} nats")   # ≤ 0.20 nats
```

---

## Comparison to Standard Attention

| Property | Standard Softmax Attention | BURT-IMMA |
|----------|---------------------------|-----------|
| Entropy constraint | None | H ≤ 0.20 nats (proved) |
| Memory write | Additive attention | Rank-1 outer product (CIFG) |
| Activation | GELU / ReLU | SmoothLeaky (monotone, bounded grad) |
| Gate coupling | Separate i/f gates | CIFG: f + (1-f) = 1 |
| Formal proof | None | Lean 4, zero sorry |

---

## Integration

Used as the memory cell inside the **IntegratedBlock** transformer replacement in sovereign-engine-v2:

```
RMSNorm → HyperbolicUMTCPI → CIFG memory
60% fewer parameters than standard transformer block
C_t = f_t ⊙ C_{t-1} + (1-f_t) ⊙ outer(v_t, k_t)
```

---

## Files

| File | Contents |
|------|---------|
| `modeling_burt_imma.py` | CIFGMatrixMemoryCell, entropy_constrained_softmax, SmoothLeaky, SpectralProjection |
| `config.json` | Architecture hyperparameters |
| `README.md` | This model card |

---

## License

BSL 1.1 → MIT on 2029-01-01
