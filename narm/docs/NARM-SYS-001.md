# NARM-SYS-001 Rev A
# Non-Autoregressive Reconstruction Machine (NARM)
# NASA-Style Systems Engineering Package
# Classification: Computational Systems Engineering

---

## 1. System Requirements

| ID | Requirement | Rationale | Verification | Status |
|----|-------------|-----------|--------------|--------|
| REQ-001 | System shall perform reconstruction of input X into X̂ without next-token prediction | Eliminate autoregressive assumption | Operator graph inspection + code audit | Defined |
| REQ-002 | System shall contain no logits, sampling, temperature, top-k/top-p, KV-cache generation loop, or causal LM head | Fundamental design change | Static analysis + acceptance test | Defined |
| REQ-003 | Primary objective: minimize reconstruction distance D(X, X̂) | Replaces cross-entropy next-token loss | Numerical verification suite | Defined |
| REQ-004 | No dependency on vLLM, transformers, torch inference runtime, or CUDA as execution backend | Independence mandate | Build + link audit | Defined |
| REQ-005 | Audio path shall implement mel → conv downsample → projection → reconstruction blocks → latent | Extracted from source audio encoder semantics | End-to-end numerical test | Defined |
| REQ-006 | All low-level compute shall use CUFF Checklist Assembly on x86-64 | Hardware-first execution | Assembly review + differential test | Defined |
| REQ-007 | Custom MLIR dialect `reconstruct` shall be the sole intermediate representation | Traceability and lowering control | Dialect verification rules | Defined |
| REQ-008 | Bidirectional traceability from every requirement to implementation and test | NASA systems-engineering practice | Traceability matrix | Defined |

---

## 2. System Architecture

```
INPUT REPRESENTATION (audio mel / text / spectral)
        ↓
FEATURE ENCODER (conv + projection)
        ↓
POSITIONAL REPRESENTATION (Fourier / relative)
        ↓
RECONSTRUCTION BLOCK × N
        ├── Normalize      (RMSNorm)
        ├── Project        (F = X W_F + b_F)
        ├── Kernel         (G = FF^T / ||F||_F + UV^T)
        ├── Value          (V = X W_V)
        ├── Aggregate      (Y = G V)
        ├── Residual       (+ X)
        └── Activate       (GELU / SiLU)
        ↓
MULTIMODAL FUSION (shared latent)
        ↓
RECONSTRUCTION DECODER
        ↓
OUTPUT REPRESENTATION (X̂)
```

No generate node. No sample node. No logits node. No KV-cache generation path.

---

## 3. Mathematical Specification

### 3.1 Primary Objective

```
L = λ₁ ‖X - X̂‖₂² + λ₂ L_spectral + λ₃ L_consistency + λ₄ R
```

where R is a regularization term (weight decay + orthogonal penalty).
λᵢ are explicit positive constants (default λ₁ = 1.0, λ₂ = 0.1, λ₃ = 0.01, λ₄ = 0.01).

### 3.2 RECON_ATTENTION Operator

Let X ∈ ℝ^{T × d}.

1. **Feature transform:** `F = X W_F + b_F`
2. **Kernel interaction** (normalized linear + residual low-rank correction):

   ```
   G = (F F^T) / (‖F‖_F + ε) + U V^T
   ```

   where U, V are low-rank factors (r ≪ d). Complexity O(T d² + T r d).

3. **Value:** `V_out = X W_V`
4. **Aggregate:** `Y = G V_out`
5. **Reconstruction:** `X̂ = Y W_R + X`  (residual, dimensionally verified)

**Rejected alternatives (documented):**
- Softmax attention: re-introduces probability simplex over sequence positions — not required for reconstruction.
- Pure RBF/Gaussian kernel: O(T²) memory, less hardware-friendly.
- Pure linear attention: retained as ablation baseline only.

### 3.3 RMSNorm

```
RMSNorm(x) = x / sqrt(1/d · Σ xᵢ² + ε) ⊙ γ
```

ε = 1e-6. No mean subtraction. Stable for residual paths.

### 3.4 Positional Representation (Fourier, deterministic)

```
PE(t, 2i)   = sin(t / 10000^{2i/d})
PE(t, 2i+1) = cos(t / 10000^{2i/d})
```

---

## 4. Complexity Analysis

| Component | FLOPs (approx) | Memory Traffic | Seq scaling |
|-----------|---------------|---------------|-------------|
| Softmax attention (rejected) | 2 T² d | High (T²) | Quadratic |
| RECON_ATTENTION (selected) | T d² + T r d | Linear in T | Linear |
| Conv downsample (audio) | O(T · C · K) | Moderate | Linear |
| N-block model (full) | N · T d² | O(N T d) | Linear |

Linear sequence-length scaling; suitable for long audio.

---

## 5. MLIR Dialect: `reconstruct`

See `narm/mlir/reconstruct.td` for full TableGen definition.

**Ops (minimal set):**

| Op | Semantics |
|----|-----------|
| `reconstruct.input` | Source tensor ingestion |
| `reconstruct.output` | Sink tensor emission |
| `reconstruct.project` | Linear projection W + b |
| `reconstruct.kernel` | G computation (kernel interaction) |
| `reconstruct.attention` | Full RECON_ATTENTION block |
| `reconstruct.normalize` | RMSNorm |
| `reconstruct.residual` | Element-wise add (residual path) |
| `reconstruct.activation` | GELU / SiLU |
| `reconstruct.conv` | 1-D conv (audio downsample) |
| `reconstruct.gemm` | General matrix multiply |
| `reconstruct.position` | Fourier positional encoding |
| `reconstruct.fuse` | Multimodal fusion |
| `reconstruct.reconstruct` | Final decoder head |

**Verification rules:**
- Result rank and dimensions must match operand constraints.
- Only f32 / bf16 permitted for compute ops.
- No op may produce a vocabulary-sized logit tensor.
- Residual operands must be shape-compatible.

**Lowering path:**
```
reconstruct.* → linalg / affine loops → CUFF Checklist Assembly (narm_kernels.asm)
```

---

## 6. CUFF Checklist (mandatory before kernel acceptance)

```
[ ] Input pointers validated
[ ] Output pointers validated
[ ] Dimensions validated
[ ] Strides validated
[ ] Dtype validated
[ ] Alignment validated
[ ] Bounds validated
[ ] No invalid memory access
[ ] Accumulator initialized
[ ] Accumulator precision verified
[ ] Matrix dimensions verified
[ ] Reduction dimension verified
[ ] Residual dimensions verified
[ ] Normalization epsilon verified
[ ] Reconstruction equation verified
[ ] Positional representation verified
[ ] No next-token prediction
[ ] No causal generation
[ ] No hidden softmax
[ ] No vLLM dependency
[ ] No Transformers dependency
[ ] No GPU dependency
[ ] ABI verified
[ ] Register allocation verified
[ ] Stack alignment verified
[ ] All labels resolved
[ ] All memory accesses bounded
[ ] Numerical error bounds recorded
[ ] Reference implementation comparison completed
```

See `narm/kernels/narm_kernels.asm` for KERN-001 through KERN-007.

---

## 7. Hand-Rolled Runtime (C ABI)

See `narm/runtime/narm.h` + `narm/runtime/narm.c`.

- **Tensor descriptor:** `{void* data, int64_t* shape, int64_t* stride, int rank, dtype_t dtype, int64_t nbytes}`
- **Memory manager:** simple arena + free-list (deterministic, no GC)
- **Op registry:** function-pointer table keyed by op enum
- **Execution graph:** static DAG — topological order, single-threaded or OpenMP sections
- **No** continuous batching, paged attention, or KV-cache for generation

**Graph (no generation nodes):**
```
INPUT → FEATURE_ENCODER → POSITION →
RECON_BLOCK_1 → … → RECON_BLOCK_N →
FUSION → DECODER → OUTPUT
```

---

## 8. Training Objective (explicit coefficients)

```
L = 1.0 · ‖X - X̂‖₂² + 0.1 · L_spectral + 0.01 · ‖W‖_F²
```

Spectral term = L2 distance on log-magnitude STFT (audio modality only). All coefficients explicit.

---

## 9. Verification / Traceability Matrix

| Requirement | Design Element | Implementation | Test | Status |
|-------------|---------------|----------------|------|--------|
| REQ-001 | Reconstruction objective | L2 loss + residual path | Numerical reconstruction error | Open |
| REQ-002 | No token prediction | Operator graph audit | Static analysis | Open |
| REQ-003 | D(X, X̂) minimized | RECON_ATTENTION + loss | test_reconstruction_error | Open |
| REQ-004 | No external runtime | narm.c arena + registry | Build/link audit | Open |
| REQ-005 | Audio path | raw_conv2d + raw_position_encoding | test_audio_latent_shape | Open |
| REQ-006 | CUFF Assembly | narm_kernels.asm | Differential vs NumPy reference | Open |
| REQ-007 | Custom MLIR | reconstruct.td | Dialect verifier | Open |
| REQ-008 | Traceability | This document | Matrix completeness review | Open |

---

## 10. Acceptance Criteria (all must pass)

- [ ] No vLLM / Transformers / PyTorch inference / CUDA runtime dependency
- [ ] No next-token logits or generation loop anywhere in the graph
- [ ] Custom MLIR dialect present and lowerable
- [ ] Hand-rolled runtime executes the static DAG
- [ ] Assembly kernels pass CUFF checklist
- [ ] Audio path produces latent of correct shape
- [ ] End-to-end reconstruction error is finite and decreases under gradient steps on synthetic data
- [ ] Traceability matrix complete

---

## 11. Identified Failure Modes

| Mode | Location | Mitigation |
|------|----------|-----------|
| Accumulator overflow/underflow | raw_gemm inner loop | Pre-scale inputs; check fp32 range |
| Residual dimension mismatch | RECON_ATTENTION step 5 | Static shape assertion in dialect verifier |
| Incorrect ε in RMSNorm | raw_normalization | Test ε = 1e-6 explicitly; compare to reference |
| Alignment fault | Any raw_* kernel | Enforce 64-byte alignment in arena allocator |
| Shape errors on variable-length audio | Feature encoder | cu_seqlens mask propagation test |
| Numerical drift in long sequences | RECON_BLOCK chain | Gradient-norm monitoring; residual scaling |

---

*End of NARM-SYS-001 Rev A*
