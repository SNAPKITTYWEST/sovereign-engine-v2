/*
 * ops.h — Operator registry and execution graph for the NARM runtime.
 * Static DAG scheduler. No vLLM, no PyTorch, no CUDA.
 *
 * Execution graph (no generation nodes):
 *   INPUT → FEATURE_ENCODER → POSITION →
 *   RECON_BLOCK_1 → … → RECON_BLOCK_N →
 *   FUSION → DECODER → OUTPUT
 */

#ifndef NARM_OPS_H
#define NARM_OPS_H

#include <stdint.h>
#include <string.h>
#include <math.h>
#include "tensor.h"

/* ---------------------------------------------------------------------------
 * Op enum (matches reconstruct.td ops)
 * -------------------------------------------------------------------------*/

typedef enum {
    OP_INPUT           = 0,
    OP_OUTPUT          = 1,
    OP_GEMM            = 2,
    OP_PROJECT         = 3,
    OP_RECON_ATTENTION = 4,
    OP_KERNEL          = 5,
    OP_NORMALIZE       = 6,
    OP_RESIDUAL        = 7,
    OP_ACTIVATION      = 8,
    OP_CONV            = 9,
    OP_POSITION        = 10,
    OP_FUSE            = 11,
    OP_RECONSTRUCT     = 12,
    OP_LOSS            = 13,
    OP_RESHAPE         = 14,
    OP_TRANSPOSE       = 15,
    OP_REDUCE          = 16,
    OP_DOWNSAMPLE      = 17,
    OP_COUNT           = 18,
} narm_op_t;

/* ---------------------------------------------------------------------------
 * Op argument bundle (union of all possible arguments)
 * -------------------------------------------------------------------------*/

typedef struct {
    narm_tensor_t *inputs[8];
    narm_tensor_t *outputs[4];
    uint32_t       n_inputs;
    uint32_t       n_outputs;

    /* Op-specific parameters */
    float   alpha;        /* GEMM alpha */
    float   beta;         /* GEMM beta */
    float   epsilon;      /* normalization epsilon */
    float   lambda1;      /* loss weight L2 */
    float   lambda2;      /* loss weight spectral */
    int64_t hidden_dim;
    int64_t num_heads;
    char    str_param[32]; /* norm_type / activation_type / encoding_type */
} narm_op_args_t;

typedef int (*narm_op_fn_t)(narm_op_args_t *args);

/* ---------------------------------------------------------------------------
 * Assembly kernel declarations (implemented in narm_kernels.asm)
 * -------------------------------------------------------------------------*/

extern void raw_gemm_f32_avx512(
    float *A, float *B, float *C,
    int64_t M, int64_t K, int64_t N,
    float alpha, float beta);

extern void raw_normalization_rms_f32(
    float *x, float *scale, float *out,
    int64_t N, int64_t D, float epsilon);

extern void raw_residual_f32(
    float *x, float *y, float *out, int64_t numel);

extern void raw_recon_attention_f32(
    float *X, float *W_Q, float *W_K, float *W_V, float *W_O,
    float *out, int64_t batch, int64_t seq, int64_t d_model,
    int64_t d_k, float epsilon);

extern void raw_position_encoding_f32(
    float *x, float *out,
    int64_t N, int64_t D);

extern void raw_conv1d_f32(
    float *x, float *w, float *b, float *out,
    int64_t batch, int64_t in_len, int64_t in_ch,
    int64_t out_ch, int64_t kernel, int64_t stride, int64_t pad);

extern void raw_reconstruction_loss_f32(
    float *x, float *x_hat, float *loss_out,
    int64_t numel, float lambda1, float lambda2);

/* ---------------------------------------------------------------------------
 * Op implementations
 * -------------------------------------------------------------------------*/

static int op_gemm(narm_op_args_t *a) {
    narm_tensor_t *A   = a->inputs[0];
    narm_tensor_t *B   = a->inputs[1];
    narm_tensor_t *acc = a->inputs[2];
    narm_tensor_t *out = a->outputs[0];

    if (A->shape.rank < 2 || B->shape.rank < 2) return -1;

    int64_t M = A->shape.dims[A->shape.rank - 2];
    int64_t K = A->shape.dims[A->shape.rank - 1];
    int64_t N = B->shape.dims[B->shape.rank - 1];

    if (K != B->shape.dims[B->shape.rank - 2]) return -2;

    *out = *acc;
    raw_gemm_f32_avx512(
        (float *)A->data, (float *)B->data, (float *)out->data,
        M, K, N, a->alpha, a->beta);
    return 0;
}

static int op_normalize(narm_op_args_t *a) {
    narm_tensor_t *x     = a->inputs[0];
    narm_tensor_t *scale = a->inputs[1];
    narm_tensor_t *out   = a->outputs[0];

    int64_t N = x->shape.dims[0];
    int64_t D = x->shape.dims[1];

    raw_normalization_rms_f32(
        (float *)x->data, (float *)scale->data, (float *)out->data,
        N, D, a->epsilon);
    return 0;
}

static int op_residual(narm_op_args_t *a) {
    narm_tensor_t *x   = a->inputs[0];
    narm_tensor_t *y   = a->inputs[1];
    narm_tensor_t *out = a->outputs[0];

    if (!shape_equal(&x->shape, &y->shape)) return -1;
    *out = tensor_create(&x->shape, x->dtype);
    raw_residual_f32(
        (float *)x->data, (float *)y->data, (float *)out->data,
        shape_numel(&x->shape));
    return 0;
}

static int op_recon_attention(narm_op_args_t *a) {
    narm_tensor_t *X   = a->inputs[0];
    narm_tensor_t *W_Q = a->inputs[1];
    narm_tensor_t *W_K = a->inputs[2];
    narm_tensor_t *W_V = a->inputs[3];
    narm_tensor_t *W_O = a->inputs[4];
    narm_tensor_t *out = a->outputs[0];

    int64_t batch   = X->shape.dims[0];
    int64_t seq     = X->shape.dims[1];
    int64_t d_model = X->shape.dims[2];
    int64_t d_k     = a->hidden_dim / a->num_heads;

    *out = tensor_create(&X->shape, X->dtype);
    raw_recon_attention_f32(
        (float *)X->data,
        (float *)W_Q->data, (float *)W_K->data,
        (float *)W_V->data, (float *)W_O->data,
        (float *)out->data,
        batch, seq, d_model, d_k, a->epsilon);
    return 0;
}

static int op_position(narm_op_args_t *a) {
    narm_tensor_t *x   = a->inputs[0];
    narm_tensor_t *out = a->outputs[0];
    int64_t N = shape_numel(&x->shape) / x->shape.dims[x->shape.rank - 1];
    int64_t D = x->shape.dims[x->shape.rank - 1];
    *out = tensor_create(&x->shape, x->dtype);
    raw_position_encoding_f32(
        (float *)x->data, (float *)out->data, N, D);
    return 0;
}

static int op_loss(narm_op_args_t *a) {
    narm_tensor_t *x     = a->inputs[0];
    narm_tensor_t *x_hat = a->inputs[1];
    narm_tensor_t *out   = a->outputs[0];

    narm_shape_t scalar_shape = { .dims = {1}, .rank = 1 };
    *out = tensor_create(&scalar_shape, DTYPE_F32);
    raw_reconstruction_loss_f32(
        (float *)x->data, (float *)x_hat->data, (float *)out->data,
        shape_numel(&x->shape), a->lambda1, a->lambda2);
    return 0;
}

/* ---------------------------------------------------------------------------
 * Op registry
 * -------------------------------------------------------------------------*/

typedef struct {
    const char  *name;
    narm_op_fn_t fn;
} narm_op_entry_t;

static const narm_op_entry_t NARM_OP_REGISTRY[OP_COUNT] = {
    [OP_INPUT]           = {"reconstruct.input",     NULL},
    [OP_OUTPUT]          = {"reconstruct.output",    NULL},
    [OP_GEMM]            = {"reconstruct.gemm",      op_gemm},
    [OP_PROJECT]         = {"reconstruct.project",   op_gemm},  /* thin wrapper */
    [OP_RECON_ATTENTION] = {"reconstruct.attention", op_recon_attention},
    [OP_KERNEL]          = {"reconstruct.kernel",    NULL},
    [OP_NORMALIZE]       = {"reconstruct.normalize", op_normalize},
    [OP_RESIDUAL]        = {"reconstruct.residual",  op_residual},
    [OP_ACTIVATION]      = {"reconstruct.activation",NULL},
    [OP_CONV]            = {"reconstruct.conv",      NULL},
    [OP_POSITION]        = {"reconstruct.position",  op_position},
    [OP_FUSE]            = {"reconstruct.fuse",      NULL},
    [OP_RECONSTRUCT]     = {"reconstruct.reconstruct",NULL},
    [OP_LOSS]            = {"reconstruct.loss",      op_loss},
    [OP_RESHAPE]         = {"reconstruct.reshape",   NULL},
    [OP_TRANSPOSE]       = {"reconstruct.transpose", NULL},
    [OP_REDUCE]          = {"reconstruct.reduce",    NULL},
    [OP_DOWNSAMPLE]      = {"reconstruct.downsample",NULL},
};

/* ---------------------------------------------------------------------------
 * Execution graph node
 * -------------------------------------------------------------------------*/

#define NARM_MAX_GRAPH_NODES 256

typedef struct {
    narm_op_t      op;
    narm_op_args_t args;
} narm_graph_node_t;

typedef struct {
    narm_graph_node_t nodes[NARM_MAX_GRAPH_NODES];
    uint32_t          n_nodes;
} narm_graph_t;

/* Topological-order execution (all nodes already sorted) */
static inline int narm_graph_execute(narm_graph_t *graph) {
    for (uint32_t i = 0; i < graph->n_nodes; ++i) {
        narm_graph_node_t *node = &graph->nodes[i];
        narm_op_fn_t fn = NARM_OP_REGISTRY[node->op].fn;
        if (!fn) continue;
        int rc = fn(&node->args);
        if (rc != 0) return rc;
    }
    return 0;
}

#endif /* NARM_OPS_H */
