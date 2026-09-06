# p3_merkle.py
# P3 cryptographic Merkle leaf commitment for GDR recurrent state chunks.
# SHA-256 over the flattened FP32 state tensor, bound to chunk_id.

import hashlib
import torch


def compute_p3_merkle_root(state_tensor: torch.Tensor, chunk_id: int) -> bytes:
    flat_bytes = state_tensor.detach().cpu().float().numpy().tobytes()
    header = (
        f"P3_STATE_COMMIT_CH={chunk_id}_TS={torch.cuda.current_device()}"
        .encode("utf-8")
    )
    hasher = hashlib.sha256()
    hasher.update(header)
    hasher.update(flat_bytes)
    return hasher.digest()
