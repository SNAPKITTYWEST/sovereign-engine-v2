"""RecursiveMemoryTwinNetwork — persistent latent state + gated memory + checkpointing.

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust
"""

import asyncio
import os
import torch
import torch.nn as nn
from typing import AsyncGenerator, Dict, Any, Optional


class RecursiveMemoryTwinNetwork(nn.Module):
    """GRU-based recurrent network with persistent latent state buffer and gated memory.

    Architecture:
    - Latent state: persistent 768-dim buffer (register)
    - Memory gate: 2×768 → 768 with LayerNorm+GELU+Tanh
    - Recurrent cell: GRUCell for state transitions
    - Integration: decay_factor=0.995, L2 normalization

    Forward pass:
    1. Concatenate latent_state ⊕ chunk_vector (1536-dim)
    2. Gate through memory_gate network
    3. Apply GRUCell recurrent transition
    4. Integrate with decay: state × 0.995 + (recurrent + gated) × 0.5 × 0.005
    5. Normalize to unit L2 norm
    6. Update latent_state in-place
    """

    def __init__(self, dimension: int = 768, hidden_dim: int = 768):
        super().__init__()
        self.dimension = dimension
        self.register_buffer("latent_state", torch.zeros(dimension, dtype=torch.float32))
        self.decay_factor = 0.995

        # Non-linear gating network for recursive memory binding
        self.memory_gate = nn.Sequential(
            nn.Linear(dimension * 2, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, dimension),
            nn.Tanh(),
        )

        # Recurrent state transition harness
        self.recurrent_cell = nn.GRUCell(dimension, dimension)

    def forward(self, chunk_vector: torch.Tensor) -> torch.Tensor:
        """Process a single chunk vector through persistent memory.

        Args:
            chunk_vector: shape (dimension,) or (batch, dimension)

        Returns:
            Updated latent state (same shape as chunk_vector)
        """
        # Concatenate current latent state with incoming micro-chunk vector
        combined = torch.cat([self.latent_state, chunk_vector], dim=-1)
        gated_delta = self.memory_gate(combined)

        # Execute recursive neural network transition step
        state_unsqueezed = self.latent_state.unsqueeze(0)
        vector_unsqueezed = chunk_vector.unsqueeze(0)
        recurrent_out = self.recurrent_cell(vector_unsqueezed, state_unsqueezed).squeeze(0)

        # State integration with decay and L2 normalization constraint
        integrated = (self.latent_state * self.decay_factor) + (
            (recurrent_out + gated_delta) * 0.5 * (1.0 - self.decay_factor)
        )
        normalized_state = torch.nn.functional.normalize(integrated, p=2, dim=-1)

        self.latent_state.copy_(normalized_state)
        return self.latent_state


class CheckpointedMemoryHarness:
    """Harness for persistent memory with checkpoint save/load."""

    def __init__(self, dimension: int = 768, device: Optional[str] = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.network = RecursiveMemoryTwinNetwork(dimension).to(device)
        self.network.eval()

    def save_checkpoint(self, filepath: str) -> None:
        """Serializes network weights, gating matrices, and the active latent state buffer."""
        checkpoint = {
            "state_dict": self.network.state_dict(),
            "latent_state": self.network.latent_state.detach().cpu(),
            "dimension": self.network.dimension,
            "device": self.device,
        }
        torch.save(checkpoint, filepath)

    def load_checkpoint(self, filepath: str) -> None:
        """Restores the recursive memory network and volatile latent state from disk."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Checkpoint state missing at path: {filepath}")

        checkpoint = torch.load(filepath, map_location=self.device)
        self.network.load_state_dict(checkpoint["state_dict"])

        # In-place copy of the persisted tensor into the active persistent buffer
        restored_state = checkpoint["latent_state"].to(self.device)
        self.network.latent_state.copy_(restored_state)
        self.network.eval()

    @torch.inference_mode()
    async def process_vector(self, chunk_vector: torch.Tensor) -> torch.Tensor:
        """Process a vector through the memory network (inference mode, no grad)."""
        tensor_gpu = chunk_vector.to(self.device)
        return self.network(tensor_gpu)


async def execute_recursive_resumption(
    filepath: str, dimension: int = 768, device: Optional[str] = None
) -> CheckpointedMemoryHarness:
    """Load or create a memory harness from checkpoint."""
    harness = CheckpointedMemoryHarness(dimension=dimension, device=device)
    if os.path.exists(filepath):
        harness.load_checkpoint(filepath)
    return harness


async def stream_ingest_pytorch(
    event_stream: AsyncGenerator[str, None], harness: CheckpointedMemoryHarness
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream events through the memory network, yielding state snapshots.

    Args:
        event_stream: async generator of string events
        harness: CheckpointedMemoryHarness instance

    Yields:
        Dict with status, device, latent_norm, tensor_shape
    """
    async for event in event_stream:
        # Real-time tensor generation (swap with local embedding model forward pass)
        vector = torch.randn(768, dtype=torch.float32)
        state_tensor = await harness.process_vector(vector)

        yield {
            "status": "pytorch_bound",
            "device": harness.device,
            "latent_norm": float(torch.norm(state_tensor).item()),
            "tensor_shape": list(state_tensor.shape),
        }
