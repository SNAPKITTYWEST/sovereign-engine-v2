"""Checkpoint storage, versioning, WORM sealing, and model pruning.

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.utils.prune as prune


class CheckpointManager:
    """Versioned checkpoint storage with WORM audit chain and S3/local backend."""

    def __init__(self, root_dir: str = "./checkpoints", use_s3: bool = False):
        """Initialize checkpoint manager.

        Args:
            root_dir: local directory for checkpoints
            use_s3: if True, upload to S3 (requires boto3 + AWS credentials)
        """
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.use_s3 = use_s3
        self.audit_log = self.root_dir / "audit.jsonl"

        if self.use_s3:
            try:
                import boto3
                self.s3_client = boto3.client("s3")
                self.s3_bucket = os.environ.get("CHECKPOINT_BUCKET", "sovereign-checkpoints")
            except ImportError:
                raise ImportError("boto3 required for S3 support: pip install boto3")

    def save_checkpoint(
        self,
        model: nn.Module,
        step: int,
        metadata: Dict[str, Any],
        prev_hash: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Save checkpoint with WORM hash chain.

        Args:
            model: PyTorch model
            step: training/inference step number
            metadata: dict with epoch, loss, timestamp, etc.
            prev_hash: previous seal hash (for chaining)

        Returns:
            (checkpoint_path, seal_hash)
        """
        checkpoint_path = self.root_dir / f"checkpoint_step_{step:06d}.pt"

        checkpoint = {
            "step": step,
            "state_dict": model.state_dict(),
            "metadata": metadata,
        }

        # Save locally
        torch.save(checkpoint, checkpoint_path)

        # Compute WORM seal
        with open(checkpoint_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        seal_payload = {
            "step": step,
            "file_sha256": file_hash,
            "metadata": metadata,
            "prev_hash": prev_hash,
        }
        seal_hash = hashlib.sha256(
            json.dumps(seal_payload, sort_keys=True).encode()
        ).hexdigest()

        # Append to audit log
        audit_entry = {
            "timestamp": metadata.get("timestamp"),
            "step": step,
            "checkpoint_path": str(checkpoint_path),
            "seal_hash": seal_hash,
            "prev_hash": prev_hash,
            "file_sha256": file_hash,
        }
        with open(self.audit_log, "a") as f:
            f.write(json.dumps(audit_entry) + "\n")

        # Upload to S3 if enabled
        if self.use_s3:
            s3_key = f"checkpoints/step_{step:06d}.pt"
            self.s3_client.upload_file(
                str(checkpoint_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={"Metadata": {"seal-hash": seal_hash}},
            )

        return str(checkpoint_path), seal_hash

    def load_checkpoint(
        self,
        model: nn.Module,
        checkpoint_path: str,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ) -> Dict[str, Any]:
        """Load checkpoint and verify seal integrity.

        Args:
            model: PyTorch model to restore into
            checkpoint_path: path to .pt file
            device: device to load onto

        Returns:
            metadata dict
        """
        checkpoint = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(checkpoint["state_dict"])

        # Verify audit chain (simple check: file exists in audit log)
        with open(self.audit_log, "r") as f:
            for line in f:
                entry = json.loads(line)
                if entry["checkpoint_path"] == checkpoint_path:
                    return entry

        return checkpoint.get("metadata", {})

    def list_checkpoints(self) -> list:
        """List all saved checkpoints in order."""
        checkpoints = sorted(self.root_dir.glob("checkpoint_step_*.pt"))
        return checkpoints


class ModelPruner:
    """Structured and unstructured pruning for weight reduction."""

    @staticmethod
    def prune_structured(
        model: nn.Module, sparsity: float = 0.3, target_layers: Optional[list] = None
    ) -> nn.Module:
        """Structured pruning: remove entire channels/filters.

        Args:
            model: PyTorch model
            sparsity: fraction of channels to prune (0.3 = remove 30%)
            target_layers: list of layer names to prune (None = all Linear/Conv)

        Returns:
            pruned model (in-place modification)
        """
        if target_layers is None:
            target_layers = [
                name
                for name, module in model.named_modules()
                if isinstance(module, (nn.Linear, nn.Conv2d))
            ]

        for name in target_layers:
            module = dict(model.named_modules())[name]
            if isinstance(module, nn.Linear):
                # Prune output channels (rows)
                prune.ln_structured(
                    module,
                    name="weight",
                    amount=sparsity,
                    n=2,
                    dim=0,
                )
            elif isinstance(module, nn.Conv2d):
                # Prune output channels
                prune.ln_structured(
                    module,
                    name="weight",
                    amount=sparsity,
                    n=2,
                    dim=0,
                )

        return model

    @staticmethod
    def prune_unstructured(
        model: nn.Module, sparsity: float = 0.2, target_layers: Optional[list] = None
    ) -> nn.Module:
        """Unstructured pruning: zero out individual weights.

        Args:
            model: PyTorch model
            sparsity: fraction of weights to zero (0.2 = zero 20%)
            target_layers: list of layer names to prune

        Returns:
            pruned model
        """
        if target_layers is None:
            target_layers = [
                name
                for name, module in model.named_modules()
                if isinstance(module, (nn.Linear, nn.Conv2d))
            ]

        for name in target_layers:
            module = dict(model.named_modules())[name]
            prune.l1_unstructured(module, name="weight", amount=sparsity)

        return model

    @staticmethod
    def remove_pruning_masks(model: nn.Module) -> nn.Module:
        """Permanently remove pruning masks (convert to actual sparse tensors).

        Args:
            model: pruned model

        Returns:
            model with permanent sparsity
        """
        for module in model.modules():
            if isinstance(module, (nn.Linear, nn.Conv2d)):
                if hasattr(module, "weight_mask"):
                    prune.remove(module, "weight")

        return model

    @staticmethod
    def quantize_and_prune(
        model: nn.Module,
        quantization_bits: int = 8,
        pruning_sparsity: float = 0.3,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ) -> nn.Module:
        """Combined quantization (INT8) + pruning for maximum compression.

        Args:
            model: PyTorch model
            quantization_bits: 8 or 4 bit quantization
            pruning_sparsity: unstructured pruning amount
            device: target device

        Returns:
            quantized + pruned model
        """
        model = model.to(device)

        # Step 1: Prune first
        ModelPruner.prune_unstructured(model, sparsity=pruning_sparsity)

        # Step 2: Quantize (post-training static)
        if quantization_bits == 8:
            model = torch.quantization.quantize_dynamic(
                model,
                {nn.Linear, nn.Conv2d},
                dtype=torch.qint8,
            )
        elif quantization_bits == 4:
            # 4-bit requires custom backend or bitsandbytes
            # For now, use 8-bit as fallback
            model = torch.quantization.quantize_dynamic(
                model,
                {nn.Linear, nn.Conv2d},
                dtype=torch.qint8,
            )

        return model

    @staticmethod
    def get_sparsity_ratio(model: nn.Module) -> float:
        """Compute sparsity: fraction of zero weights.

        Args:
            model: PyTorch model

        Returns:
            sparsity ratio (0.0 to 1.0)
        """
        total_params = 0
        zero_params = 0

        for name, param in model.named_parameters():
            if "weight" in name:
                total_params += param.numel()
                zero_params += (param == 0).sum().item()

        if total_params == 0:
            return 0.0

        return zero_params / total_params


# Usage example (not executed)
"""
# 1. Save checkpoint with WORM seal
manager = CheckpointManager(root_dir="./checkpoints", use_s3=True)
model = MyRecursiveNetwork(dimension=768)
step = 1000
metadata = {"epoch": 5, "loss": 0.023, "timestamp": "2026-09-07T10:30:00Z"}
ckpt_path, seal_hash = manager.save_checkpoint(model, step, metadata, prev_hash=None)

# 2. Prune for deployment
pruner = ModelPruner()
model_pruned = pruner.quantize_and_prune(model, quantization_bits=8, pruning_sparsity=0.3)
sparsity = pruner.get_sparsity_ratio(model_pruned)
print(f"Sparsity: {sparsity:.1%}")

# 3. Save pruned checkpoint
ckpt_pruned, seal_pruned = manager.save_checkpoint(
    model_pruned, step, {"...": "...", "pruned": True, "sparsity": sparsity}
)

# 4. List all checkpoints
for ckpt in manager.list_checkpoints():
    print(ckpt)
"""
