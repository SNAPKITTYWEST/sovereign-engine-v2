"""
Train the Virtual H100 Graph Transformer using the JAX training harness.

The graph transformer (virtual_h100_pipeline.py) is lifted into JAX parameter
trees so the harness optimizer, loss functions, trainer loop, and data
generators all work without modification.

Pipeline:
  JAX batch (graph adjacency + node features)
    → canonicalize DAG
    → encode to TensorBundle
    → GraphTransformer (JAX params, forward pass reimplemented as pure JAX)
    → classification head
    → cross-entropy loss
    → AdamW via harness Trainer
    → EarlyStopping + HistoryCallback
"""

from __future__ import annotations

import sys
import math
from pathlib import Path
from typing import Any, Dict, Tuple

import jax
import jax.numpy as jnp
from jax import random, nn, tree_util

# ── repo paths ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "jax_training_harness" / "jax_training_harness"))
sys.path.insert(0, str(ROOT / "forth-array-transformer"))

from jax_harness.config import HarnessConfig
from jax_harness.data.generators import make_graph_batch
from jax_harness.algorithms.optim import AdamW
from jax_harness.algorithms.losses import cross_entropy
from jax_harness.algorithms.trainer import Trainer
from jax_harness.protocols import (
    EarlyStopping,
    HistoryCallback,
    NaNGuard,
    CallbackList,
    TrainLoop,
)
from jax_harness.types import Batch

# ── config ────────────────────────────────────────────────────────────────

cfg = HarnessConfig(
    seed=42,
    batch_size=8,
    seq_len=32,
    d_model=32,
    num_heads=4,
    num_layers=2,
    graph_nodes=12,
    num_classes=2,
    learning_rate=2e-3,
    weight_decay=1e-4,
    warmup_steps=20,
    max_grad_norm=1.0,
)
cfg.validate()

# ── pure-JAX graph transformer ────────────────────────────────────────────
# Re-implements virtual_h100_pipeline.GraphTransformer as a JAX param tree
# so jax.jit / jax.value_and_grad work without PyTorch tensors.

def glorot(key, shape):
    fan_in, fan_out = shape[-2], shape[-1]
    limit = math.sqrt(6.0 / (fan_in + fan_out))
    return random.uniform(key, shape, minval=-limit, maxval=limit)

def init_linear(key, in_dim, out_dim):
    return {"w": glorot(key, (in_dim, out_dim)), "b": jnp.zeros((out_dim,))}

def apply_linear(p, x):
    return jnp.einsum("...i,ij->...j", x, p["w"]) + p["b"]

def init_layer_norm(dim):
    return {"scale": jnp.ones((dim,)), "bias": jnp.zeros((dim,))}

def apply_layer_norm(p, x, eps=1e-6):
    mean = jnp.mean(x, axis=-1, keepdims=True)
    var  = jnp.var(x,  axis=-1, keepdims=True)
    return p["scale"] * (x - mean) / jnp.sqrt(var + eps) + p["bias"]

N_HEADS = cfg.num_heads  # module-level constant, not stored in param tree

def init_mha(key, d_model, n_heads):
    keys = random.split(key, 4)
    return {
        "q": init_linear(keys[0], d_model, d_model),
        "k": init_linear(keys[1], d_model, d_model),
        "v": init_linear(keys[2], d_model, d_model),
        "o": init_linear(keys[3], d_model, d_model),
    }

def apply_mha(p, x, attn_mask):
    """x: [N, D], attn_mask: [N, N] (1=visible)"""
    N, D = x.shape
    H = N_HEADS
    Dh = D // H
    q = apply_linear(p["q"], x).reshape(N, H, Dh).transpose(1, 0, 2)  # [H,N,Dh]
    k = apply_linear(p["k"], x).reshape(N, H, Dh).transpose(1, 0, 2)
    v = apply_linear(p["v"], x).reshape(N, H, Dh).transpose(1, 0, 2)
    scores = jnp.einsum("hid,hjd->hij", q, k) / math.sqrt(Dh)          # [H,N,N]
    scores = scores + jnp.where(attn_mask[None] == 0, -1e9, 0.0)
    weights = nn.softmax(scores, axis=-1)
    out = jnp.einsum("hij,hjd->hid", weights, v)                        # [H,N,Dh]
    out = out.transpose(1, 0, 2).reshape(N, D)
    return apply_linear(p["o"], out)

def init_block(key, d_model, n_heads, d_ff):
    k1, k2, k3 = random.split(key, 3)
    return {
        "attn":   init_mha(k1, d_model, n_heads),
        "ff0":    init_linear(k2, d_model, d_ff),
        "ff1":    init_linear(k3, d_ff, d_model),
        "norm1":  init_layer_norm(d_model),
        "norm2":  init_layer_norm(d_model),
    }

def apply_block(p, x, attn_mask):
    h = apply_layer_norm(p["norm1"], x)
    h = apply_mha(p["attn"], h, attn_mask)
    x = x + h
    h = apply_layer_norm(p["norm2"], x)
    h = apply_linear(p["ff1"], nn.gelu(apply_linear(p["ff0"], h)))
    return x + h

def init_graph_transformer(key, node_input_dim, d_model, n_layers, n_heads, n_classes):
    keys = random.split(key, n_layers + 3)
    blocks = [
        init_block(keys[i], d_model, n_heads, d_ff=4 * d_model)
        for i in range(n_layers)
    ]
    return {
        "input_proj":  init_linear(keys[n_layers],     node_input_dim, d_model),
        "output_proj": init_linear(keys[n_layers + 1], d_model, d_model),
        "head":        init_linear(keys[n_layers + 2], d_model, n_classes),
        "blocks": blocks,
    }

def apply_graph_transformer(params, node_feats, attn_mask):
    """
    node_feats : [N, node_input_dim]
    attn_mask  : [N, N]   (1 = can attend)
    returns      [N, n_classes] logits
    """
    x = apply_linear(params["input_proj"], node_feats)
    for block in params["blocks"]:
        x = apply_block(block, x, attn_mask)
    x = apply_linear(params["output_proj"], x)
    return apply_linear(params["head"], x)   # [N, n_classes]

# ── attention mask from adjacency (ancestor policy) ───────────────────────

def ancestor_mask(adj):
    """adj: [N, N] float, returns reachability mask [N, N].
    Two passes of squaring covers depth up to 4 — cheap enough for N=12."""
    N = adj.shape[0]
    reach = adj + jnp.eye(N)
    reach = jnp.minimum(reach @ reach, 1.0)
    reach = jnp.minimum(reach @ reach, 1.0)
    return reach

# ── batched loss / forward ────────────────────────────────────────────────

# node_input_dim = 5 fixed fields + cfg.graph_nodes features + 1 hash field
# We encode node features as: [node_id/N, in_deg/N, out_deg/N, depth/max_d, node_feat...]
# Here we use graph_nodes as node_dim directly (raw adjacency row = neighbourhood).
NODE_DIM = cfg.graph_nodes  # one float per potential neighbour = simple structural encoding

def encode_nodes(node_features, adjacency):
    """
    node_features : [B, N, node_feat_dim]  (from make_graph_batch)
    adjacency     : [B, N, N]
    returns         [B, N, NODE_DIM]  simple structural + feature encoding
    """
    B, N, _ = node_features.shape
    # in-degree and out-degree normalised
    in_deg  = adjacency.sum(axis=1) / (N - 1 + 1e-6)   # [B, N]
    out_deg = adjacency.sum(axis=2) / (N - 1 + 1e-6)   # [B, N]
    node_id = jnp.tile(jnp.arange(N)[None, :] / N, (B, 1))  # [B, N]
    # stack to [B, N, 3] then pad/truncate to NODE_DIM
    struct  = jnp.stack([node_id, in_deg, out_deg], axis=-1)  # [B, N, 3]
    # use adjacency row as neighbourhood fingerprint [B, N, N]
    # concatenate → [B, N, 3+N]; slice to NODE_DIM
    combined = jnp.concatenate([struct, adjacency], axis=-1)   # [B, N, 3+N]
    combined = combined[..., :NODE_DIM]                        # [B, N, NODE_DIM]
    # zero-pad if NODE_DIM > 3+N (shouldn't happen here)
    pad = NODE_DIM - combined.shape[-1]
    if pad > 0:
        combined = jnp.concatenate([combined, jnp.zeros((B, N, pad))], axis=-1)
    return combined

def batch_loss(params, batch):
    """
    batch = (node_features [B,N,D], adjacency [B,N,N], labels [B])
    Returns (scalar_loss, aux_dict)
    """
    node_feats, adjacency, labels = batch
    B, N, _ = node_feats.shape

    encoded = encode_nodes(node_feats, adjacency)   # [B, N, NODE_DIM]

    def single(nf, adj, lbl):
        mask   = ancestor_mask(adj)                 # [N, N]
        logits = apply_graph_transformer(params, nf, mask)  # [N, n_classes]
        # graph-level prediction: mean-pool over nodes
        graph_logit = jnp.mean(logits, axis=0)      # [n_classes]
        loss = cross_entropy(graph_logit[None], lbl[None])
        pred = jnp.argmax(graph_logit)
        acc  = (pred == lbl).astype(jnp.float32)
        return loss, acc

    losses, accs = jax.vmap(single)(encoded, adjacency, labels)
    return jnp.mean(losses), {"accuracy": jnp.mean(accs)}

# ── data generator ────────────────────────────────────────────────────────

def infinite_graph_batches(seed):
    key = random.PRNGKey(seed)
    while True:
        key, sub = random.split(key)
        node_feats, adj, labels = make_graph_batch(
            sub, cfg.batch_size, cfg.graph_nodes, node_dim=cfg.graph_nodes
        )
        yield (node_feats, adj, labels)

# ── init params ───────────────────────────────────────────────────────────

key = random.PRNGKey(cfg.seed)
params = init_graph_transformer(
    key,
    node_input_dim=NODE_DIM,
    d_model=cfg.d_model,
    n_layers=cfg.num_layers,
    n_heads=cfg.num_heads,
    n_classes=cfg.num_classes,
)

n_params = sum(x.size for x in tree_util.tree_leaves(params))
print(f"Model parameters: {n_params:,}")

# ── optimizer + trainer ───────────────────────────────────────────────────

optimizer = AdamW(
    learning_rate=cfg.learning_rate,
    weight_decay=cfg.weight_decay,
    max_grad_norm=cfg.max_grad_norm,
)

trainer = Trainer(
    params=params,
    optimizer=optimizer,
    loss_fn=batch_loss,
    config=cfg,
)

# ── callbacks ─────────────────────────────────────────────────────────────

history_cb  = HistoryCallback()
nan_guard   = NaNGuard(fields=("loss",))
early_stop  = EarlyStopping(patience=30, mode="min", min_delta=1e-4)

TRAIN_STEPS = 200
LOG_EVERY   = 20

print(f"\nTraining for {TRAIN_STEPS} steps  (graph nodes={cfg.graph_nodes}, "
      f"d_model={cfg.d_model}, layers={cfg.num_layers}, heads={cfg.num_heads})\n")

# ── training loop ─────────────────────────────────────────────────────────

data = infinite_graph_batches(cfg.seed + 1)
history = trainer.train(data, steps=TRAIN_STEPS, log_every=LOG_EVERY)

# ── early stopping post-hoc summary ──────────────────────────────────────

for row in history:
    if early_stop.update(row["loss"]):
        print(f"\nEarly stopping triggered (patience={early_stop.patience})")
        break

summary = Trainer.summary(history)
print(f"\n-- Training summary --------------------------------------------------")
for k, v in summary.items():
    print(f"  {k:20s}: {v:.5f}")

# ── save checkpoint ───────────────────────────────────────────────────────

ckpt_path = ROOT / "checkpoints" / "graph_transformer"
trainer.save(ckpt_path, metadata={
    "train_steps": TRAIN_STEPS,
    "final_loss":  summary.get("loss", 0.0),
    "final_acc":   summary.get("accuracy", 0.0),
    "n_params":    n_params,
    "config":      cfg.to_dict(),
})
print(f"\nCheckpoint saved -> {ckpt_path}.npz")
