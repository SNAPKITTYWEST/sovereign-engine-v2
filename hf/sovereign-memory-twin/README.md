# Sovereign memory twin

[modeling_rmtn.py](modeling_rmtn.py) implements a PyTorch recurrent memory module and checkpoint harness. [config.json](config.json) describes default dimensions. This directory contains source and configuration, not trained weights or a training/evaluation record.

Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST).

## State update

`RecursiveMemoryTwinNetwork(dimension=768, hidden_dim=768)` stores one latent vector as a registered buffer. It concatenates that vector with an input vector, computes a learned memory gate and GRUCell update, integrates them with decay `0.995`, normalizes the result, and copies it into the persistent buffer.

Use a single `(dimension,)` vector. The current concatenation/state code does not implement an independent state for every row of a batch. The returned tensor aliases the latent buffer; clone it if you need to preserve a historical value.

## Local example

Run from this directory in an environment with PyTorch:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import torch
from modeling_rmtn import CheckpointedMemoryHarness

torch.manual_seed(0)
harness = CheckpointedMemoryHarness(dimension=8, device="cpu")
with torch.inference_mode():
    first = harness.network(torch.ones(8)).clone()
assert first.shape == (8,)
with TemporaryDirectory() as directory:
    path = str(Path(directory) / "memory.pt")
    harness.save_checkpoint(path)
    restored = CheckpointedMemoryHarness(dimension=8, device="cpu")
    restored.load_checkpoint(path)
    assert torch.equal(first, restored.network.latent_state)
print("latent state restored")
```

This is a state round-trip check with initialized weights, not a trained-model quality test. Loading a checkpoint requires compatible dimensions and a trusted checkpoint file.

## Checkpoints

The harness saves `state_dict`, `latent_state`, `dimension`, and `device`. Instantiate the receiving harness with the matching dimension before loading.

The separate [CheckpointManager](../../src/models/checkpoint_manager.py) writes model checkpoints, file hashes, and an audit JSONL. Its seal hashes a JSON-serialized payload containing step, file hash, metadata, and optional previous hash. Callers must supply the previous seal to form a chain. This mechanism is separate from the engine's binary WORMLedger.

[ModelPruner](../../src/models/checkpoint_manager.py) and the [workflow](../../src/models/checkpoint_workflow.py) provide pruning/quantization helpers. Compression ratios and inference gains require measurement on a specific model; no fixed fourfold improvement is established here.

## Training and license

The repository includes [training/corpus sources](../../training/) and a [corpus schema](../sovereign-training-corpus/). Their presence does not establish that this model was trained on those corpora.

Consult [LICENSE.tri](../../LICENSE.tri) and component metadata for licensing. See [documentation](../../docs/README.md) for engine integration boundaries.
