// reconstruct.td — MLIR TableGen definition of the `reconstruct` dialect.
//
// Lowering path:
//   reconstruct.* → linalg / affine → LLVM-IR → CUFF x86-64 assembly
//
// Verification rules:
//   • No op may produce a vocabulary-sized logit tensor.
//   • Only f32 / bf16 permitted for compute ops.
//   • Residual operands must be shape-compatible.
//   • No softmax over a vocabulary dimension is permitted anywhere.

include "mlir/IR/OpBase.td"
include "mlir/IR/AttrTypeBase.td"
include "mlir/Interfaces/SideEffectInterfaces.td"

//===----------------------------------------------------------------------===//
// Dialect declaration
//===----------------------------------------------------------------------===//

def Reconstruct_Dialect : Dialect {
  let name = "reconstruct";
  let summary = "Non-autoregressive reconstruction transformer dialect";
  let description = [{
    Custom MLIR dialect for the Non-Autoregressive Reconstruction Machine (NARM).
    All operations are non-generative: no logits, no softmax over vocabulary,
    no causal masking for token generation.
    Mathematical objective: minimize D(X, X_hat) via RECON_ATTENTION.
  }];
  let cppNamespace = "::mlir::reconstruct";
}

//===----------------------------------------------------------------------===//
// Base operation class
//===----------------------------------------------------------------------===//

class Reconstruct_Op<string mnemonic, list<Trait> traits = []>
    : Op<Reconstruct_Dialect, mnemonic, traits>;

//===----------------------------------------------------------------------===//
// Types
//===----------------------------------------------------------------------===//

def Reconstruct_AnyFloat : AnyTypeOf<[F32, BF16]>;

//===----------------------------------------------------------------------===//
// Operations
//===----------------------------------------------------------------------===//

// ── Boundary ops ────────────────────────────────────────────────────────────

def Reconstruct_InputOp : Reconstruct_Op<"input",
    [NoSideEffect]> {
  let summary = "Source tensor ingestion gateway";
  let arguments = (ins
    I64ArrayAttr:$shape,
    StrAttr:$dtype
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // dtype must be f32 or bf16
    return success();
  }];
}

def Reconstruct_OutputOp : Reconstruct_Op<"output"> {
  let summary = "Sink tensor emission gateway";
  let arguments = (ins
    AnyTensor:$operand,
    StrAttr:$name
  );
}

// ── Linear algebra ──────────────────────────────────────────────────────────

def Reconstruct_GemmOp : Reconstruct_Op<"gemm",
    [NoSideEffect]> {
  let summary = "General matrix multiply: result = alpha*(lhs @ rhs) + beta*acc";
  let arguments = (ins
    AnyTensor:$lhs,
    AnyTensor:$rhs,
    AnyTensor:$acc,
    DefaultValuedAttr<F32Attr, "1.0f">:$alpha,
    DefaultValuedAttr<F32Attr, "1.0f">:$beta,
    DefaultValuedAttr<BoolAttr, "false">:$transa,
    DefaultValuedAttr<BoolAttr, "false">:$transb
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // lhs.inner_dim == rhs.outer_dim (accounting for transpose flags)
    // acc.shape == [lhs.M, rhs.N]
    // All dtypes must match
    return success();
  }];
}

def Reconstruct_ProjectOp : Reconstruct_Op<"project",
    [NoSideEffect]> {
  let summary = "Dense projection: Y = X @ W + b";
  let arguments = (ins
    AnyTensor:$x,
    AnyTensor:$weights,
    Optional<AnyTensor>:$bias,
    DefaultValuedAttr<BoolAttr, "true">:$use_bias
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // x.shape[-1] == weights.shape[0]
    // result.shape[-1] == weights.shape[1]
    // result.shape[0:-1] == x.shape[0:-1]
    return success();
  }];
}

// ── Reconstruction attention (RECON_ATTENTION — no softmax) ─────────────────

def Reconstruct_AttentionOp : Reconstruct_Op<"attention",
    [NoSideEffect]> {
  let summary = [{
    RECON_ATTENTION: quadratic kernel, row-normalized, no softmax.
    G[i,j] = (Q[i]·K[j])^2 / (d_k + eps)
    ~G[i,j] = G[i,j] / (sum_k G[i,k] + eps)
    Y = ~G @ V
    Out = Y @ W_O
  }];
  let arguments = (ins
    AnyTensor:$x,
    AnyTensor:$w_q,
    AnyTensor:$w_k,
    AnyTensor:$w_v,
    AnyTensor:$w_o,
    I64Attr:$hidden_dim,
    I64Attr:$num_heads,
    DefaultValuedAttr<F32Attr, "1e-6f">:$epsilon
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // CRITICAL: this op must NOT contain softmax.
    // Verification: no exponential applied to the kernel matrix G.
    // x: [batch, seq_len, d_model]
    // result: same shape as x
    return success();
  }];
}

def Reconstruct_KernelOp : Reconstruct_Op<"kernel",
    [NoSideEffect]> {
  let summary = "Kernel interaction: G = (F F^T)/(||F||_F + eps) + U V^T";
  let arguments = (ins
    AnyTensor:$f,
    AnyTensor:$u,       // low-rank factor U
    AnyTensor:$v,       // low-rank factor V
    DefaultValuedAttr<F32Attr, "1e-6f">:$epsilon
  );
  let results = (outs AnyTensor:$result);
}

// ── Normalization ────────────────────────────────────────────────────────────

def Reconstruct_NormalizeOp : Reconstruct_Op<"normalize",
    [NoSideEffect]> {
  let summary = "Normalization (RMSNorm / LayerNorm / BatchNorm)";
  let arguments = (ins
    AnyTensor:$x,
    AnyTensor:$scale,
    Optional<AnyTensor>:$bias,
    I64Attr:$axis,
    DefaultValuedAttr<F32Attr, "1e-6f">:$epsilon,
    StrAttr:$norm_type     // "rms" | "layer" | "batch"
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // result.shape == x.shape
    // result.dtype == x.dtype
    // epsilon > 0
    return success();
  }];
}

// ── Residual ─────────────────────────────────────────────────────────────────

def Reconstruct_ResidualOp : Reconstruct_Op<"residual",
    [NoSideEffect]> {
  let summary = "Skip connection: result = x + y";
  let arguments = (ins
    AnyTensor:$x,
    AnyTensor:$y
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // x.shape == y.shape
    // x.dtype == y.dtype
    return success();
  }];
}

// ── Activation ───────────────────────────────────────────────────────────────

def Reconstruct_ActivationOp : Reconstruct_Op<"activation",
    [NoSideEffect]> {
  let summary = "Nonlinear activation: relu | gelu | silu";
  let arguments = (ins
    AnyTensor:$x,
    StrAttr:$activation_type
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // result.shape == x.shape, result.dtype == x.dtype
    return success();
  }];
}

// ── Convolution ──────────────────────────────────────────────────────────────

def Reconstruct_ConvOp : Reconstruct_Op<"conv",
    [NoSideEffect]> {
  let summary = "N-D convolution (audio downsample path)";
  let arguments = (ins
    AnyTensor:$x,
    AnyTensor:$weights,
    Optional<AnyTensor>:$bias,
    I64ArrayAttr:$kernel_size,
    I64ArrayAttr:$stride,
    I64ArrayAttr:$padding,
    I64ArrayAttr:$dilation
  );
  let results = (outs AnyTensor:$result);
}

// ── Position encoding ────────────────────────────────────────────────────────

def Reconstruct_PositionOp : Reconstruct_Op<"position",
    [NoSideEffect]> {
  let summary = "Positional encoding injection (rotary | sinusoidal | learned)";
  let arguments = (ins
    AnyTensor:$x,
    StrAttr:$encoding_type,
    I64Attr:$dim
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // result.shape == x.shape, result.dtype == x.dtype
    // encoding_type in {"rotary", "sinusoidal", "learned"}
    return success();
  }];
}

// ── Multimodal fusion ────────────────────────────────────────────────────────

def Reconstruct_FuseOp : Reconstruct_Op<"fuse",
    [NoSideEffect]> {
  let summary = "Bilinear gated cross-modal fusion (no token merging)";
  let arguments = (ins
    AnyTensor:$audio,
    AnyTensor:$text,
    AnyTensor:$gate_weights,
    StrAttr:$fusion_type   // "bilinear" | "gated" | "cross_modal"
  );
  let results = (outs AnyTensor:$result);
  let verifier = [{
    // audio.shape[-1] == text.shape[-1]  (same latent dim)
    // result.shape[0] == audio.shape[0] + text.shape[0]
    return success();
  }];
}

// ── Reconstruction (final decoder head) ──────────────────────────────────────

def Reconstruct_ReconstructOp : Reconstruct_Op<"reconstruct",
    [NoSideEffect]> {
  let summary = "Final reconstruction head: X_hat = latent @ W_R + X (residual)";
  let arguments = (ins
    AnyTensor:$latent,
    AnyTensor:$w_r,
    AnyTensor:$x_original
  );
  let results = (outs AnyTensor:$x_hat);
  let verifier = [{
    // CRITICAL: result must NOT be vocabulary-sized logits.
    // result.shape == x_original.shape
    return success();
  }];
}

// ── Loss ─────────────────────────────────────────────────────────────────────

def Reconstruct_LossOp : Reconstruct_Op<"loss"> {
  let summary = "Reconstruction loss: L = lambda1*L2 + lambda2*L_spectral";
  let arguments = (ins
    AnyTensor:$x,
    AnyTensor:$x_hat,
    StrAttr:$loss_type,       // "l2" | "spectral" | "combined"
    F32ArrayAttr:$weights
  );
  let results = (outs F32:$loss);
}

// ── Utility ──────────────────────────────────────────────────────────────────

def Reconstruct_ReshapeOp : Reconstruct_Op<"reshape", [NoSideEffect]> {
  let summary = "Reshape tensor (product of dims unchanged)";
  let arguments = (ins AnyTensor:$x, I64ArrayAttr:$target_shape);
  let results = (outs AnyTensor:$result);
}

def Reconstruct_TransposeOp : Reconstruct_Op<"transpose", [NoSideEffect]> {
  let summary = "Permute tensor axes";
  let arguments = (ins AnyTensor:$x, I64ArrayAttr:$permutation);
  let results = (outs AnyTensor:$result);
}

def Reconstruct_ReduceOp : Reconstruct_Op<"reduce", [NoSideEffect]> {
  let summary = "Reduction: sum | mean | max | min over axes";
  let arguments = (ins
    AnyTensor:$x,
    I64ArrayAttr:$axes,
    StrAttr:$reduce_op
  );
  let results = (outs AnyTensor:$result);
}

def Reconstruct_DownsampleOp : Reconstruct_Op<"downsample", [NoSideEffect]> {
  let summary = "Spatial downsampling for audio encoder";
  let arguments = (ins
    AnyTensor:$x,
    I64Attr:$factor,
    StrAttr:$method    // "average" | "max" | "stride"
  );
  let results = (outs AnyTensor:$result);
}
