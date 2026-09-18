---
language: en
license: bsl-1.0
library_name: pytorch
tags:
  - pytorch
  - recurrent
  - memory
  - gru
  - sovereign
  - persistent-state
  - snapkittywest
model_type: recursive-memory-twin
pipeline_tag: feature-extraction
---

# sovereign-memory-twin

**RecursiveMemoryTwinNetwork** — a GRU-based recurrent network with a persistent 768-dim latent state buffer and gated memory binding. Designed for streaming inference over long event sequences where continuity across chunks matters.

Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST) — Bel Esprit D'Accord Irrevocable Trust

---

## Architecture

```
Input chunk_vector (768-dim)
        │
        ├── concat with latent_state → 1536-dim
        │         ↓
        │   memory_gate:
        │     Linear(1536→768) → LayerNorm → GELU → Linear(768→768) → Tanh
        │         ↓
        │   gated_delta (768-dim)
        │
        ├── GRUCell(input=chunk_vector, hidden=latent_state)
        │         ↓
        │   recurrent_out (768-dim)
        │
        └── Integration:
              new_state = latent_state × 0.995
                        + (recurrent_out + gated_delta) × 0.5 × 0.005
              latent_state ← L2_normalize(new_state)
```

**Key properties:**
- `decay_factor = 0.995` — exponential decay keeps past context alive without overflow
- `register_buffer("latent_state")` — state persists across `.forward()` calls, saved in checkpoints
- L2 normalization — unit sphere constraint, prevents magnitude explosion
- Async `process_vector()` — inference-mode, no grad, safe for streaming loops

---

## Parameters

| Component | Shape | Parameters |
|-----------|-------|------------|
| memory_gate.0 (Linear) | 1536 → 768 | 1,180,416 |
| memory_gate.1 (LayerNorm) | 768 | 1,536 |
| memory_gate.3 (Linear) | 768 → 768 | 590,592 |
| recurrent_cell (GRUCell) | 768 → 768 | 3,543,040 |
| latent_state (buffer) | 768 | — |
| **Total trainable** | | **~5.3M** |

---

## Usage

```python
import torch
from modeling_rmtn import RecursiveMemoryTwinNetwork, CheckpointedMemoryHarness

# Direct model use
model = RecursiveMemoryTwinNetwork(dimension=768)
chunk = torch.randn(768)
state = model(chunk)   # returns updated latent state
print(state.shape)     # torch.Size([768])

# Harness with checkpoint save/load
harness = CheckpointedMemoryHarness(dimension=768, device="cpu")
harness.save_checkpoint("memory.pt")

# Restore and continue
harness2 = CheckpointedMemoryHarness()
harness2.load_checkpoint("memory.pt")

# Async streaming
import asyncio

async def run():
    async def events():
        for _ in range(100):
            yield "event"

    from modeling_rmtn import stream_ingest_pytorch
    async for snapshot in stream_ingest_pytorch(events(), harness):
        print(snapshot)  # {"status": "pytorch_bound", "latent_norm": 1.0, ...}

asyncio.run(run())
```

---

## Checkpoint Format

```python
{
    "state_dict": { ... },          # model weights
    "latent_state": torch.Tensor,   # 768-dim persistent buffer
    "dimension": 768,
    "device": "cpu"
}
```

Save/load preserves the full latent state — resuming from a checkpoint picks up exactly where inference left off.

---

## Integration with CheckpointManager + ModelPruner

```python
from src.models.checkpoint_manager import CheckpointManager, ModelPruner

manager = CheckpointManager(root_dir="./checkpoints", use_s3=False)
model = RecursiveMemoryTwinNetwork(dimension=768)

# Save with WORM audit seal
ckpt_path, seal_hash = manager.save_checkpoint(
    model, step=1000,
    metadata={"epoch": 5, "loss": 0.023}
)

# Prune + quantize for deployment (4× compression)
pruned = ModelPruner.quantize_and_prune(model, quantization_bits=8, pruning_sparsity=0.3)
```

---

## WORM Audit Chain

Every checkpoint is sealed:
```
seal_hash = SHA-256(step || file_sha256 || metadata || prev_hash)
```
Appended to `audit.jsonl` — append-only, tamper-evident hash chain. Break one seal → break all downstream.

---

## Intended Use

- Long-horizon streaming inference over event sequences
- Persistent agent memory (sovereign engine context buffer)
- Federated training via AgentFishTank swarm pipeline
- Drop-in recurrent memory for any 768-dim embedding pipeline

---

## Training

Trained/used within the [sovereign-engine-v2](https://github.com/SNAPKITTYWEST/sovereign-engine-v2) stack.
Corpus: AgentFishTank federated training (NASA CMR · OpenMetadata · Autoware).

---

## License

BSL 1.1 → MIT on 2029-01-01
