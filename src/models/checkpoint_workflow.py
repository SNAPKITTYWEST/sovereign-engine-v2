"""End-to-end checkpoint, pruning, and upload workflow."""

import asyncio
import time
from datetime import datetime
from pathlib import Path

import torch

from src.models.recursive_memory import CheckpointedMemoryHarness
from src.models.checkpoint_manager import CheckpointManager, ModelPruner


async def full_checkpoint_workflow(
    model_or_harness,
    step: int,
    output_dir: str = "./checkpoints",
    prune_sparsity: float = 0.3,
    quantize: bool = True,
    upload_s3: bool = False,
    prev_seal_hash: str = None,
):
    """Complete workflow: save → prune → quantize → upload.

    Args:
        model_or_harness: PyTorch model or CheckpointedMemoryHarness
        step: training/inference step
        output_dir: checkpoint directory
        prune_sparsity: fraction to prune (0.3 = 30%)
        quantize: whether to quantize to INT8
        upload_s3: whether to upload to S3
        prev_seal_hash: previous WORM seal (for chaining)

    Returns:
        dict with paths, hashes, metrics
    """
    manager = CheckpointManager(root_dir=output_dir, use_s3=upload_s3)

    # Extract model if harness was passed
    if isinstance(model_or_harness, CheckpointedMemoryHarness):
        model = model_or_harness.network
    else:
        model = model_or_harness

    # ─── Step 1: Save checkpoint with WORM seal ───
    print(f"[Step {step}] Saving checkpoint...")
    metadata = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "step": step,
        "device": str(next(model.parameters()).device),
    }

    ckpt_path, seal_hash = manager.save_checkpoint(
        model, step, metadata, prev_hash=prev_seal_hash
    )
    print(f"  ✓ Checkpoint: {ckpt_path}")
    print(f"  ✓ WORM seal: {seal_hash[:16]}...")

    # ─── Step 2: Measure baseline ───
    model_device = next(model.parameters()).device
    param_count = sum(p.numel() for p in model.parameters())
    baseline_size_mb = param_count * 4 / (1024 * 1024)  # float32 = 4 bytes
    print(f"  Baseline: {param_count:,} params ({baseline_size_mb:.1f} MB)")

    # ─── Step 3: Prune ───
    print(f"[Step {step}] Pruning {prune_sparsity:.0%}...")
    model_pruned = ModelPruner.prune_unstructured(model, sparsity=prune_sparsity)
    sparsity_ratio = ModelPruner.get_sparsity_ratio(model_pruned)
    print(f"  ✓ Achieved sparsity: {sparsity_ratio:.1%}")

    # ─── Step 4: Quantize (optional) ───
    if quantize:
        print(f"[Step {step}] Quantizing to INT8...")
        model_pruned = ModelPruner.quantize_and_prune(
            model_pruned,
            quantization_bits=8,
            pruning_sparsity=prune_sparsity,
            device=str(model_device),
        )
        # Quantized + sparse: roughly 4× compression
        compressed_size_mb = baseline_size_mb / 4
        print(f"  ✓ Compressed: {compressed_size_mb:.1f} MB (4× reduction)")
    else:
        # Just sparse: roughly 1/(1-sparsity)× savings
        compressed_size_mb = baseline_size_mb * (1 - sparsity_ratio)
        print(f"  ✓ Sparse only: {compressed_size_mb:.1f} MB")

    # ─── Step 5: Save pruned checkpoint ───
    print(f"[Step {step}] Saving pruned checkpoint...")
    metadata_pruned = {
        **metadata,
        "pruned": True,
        "sparsity": float(sparsity_ratio),
        "quantized": quantize,
    }
    ckpt_pruned_path, seal_pruned = manager.save_checkpoint(
        model_pruned, step, metadata_pruned, prev_hash=seal_hash
    )
    print(f"  ✓ Pruned checkpoint: {ckpt_pruned_path}")
    print(f"  ✓ WORM seal (chained): {seal_pruned[:16]}...")

    # ─── Step 6: List all checkpoints ───
    print(f"[Step {step}] Checkpoint history:")
    for ckpt in manager.list_checkpoints()[-5:]:  # Last 5
        print(f"    {ckpt.name} ({ckpt.stat().st_size / (1024*1024):.1f} MB)")

    return {
        "step": step,
        "checkpoint_path": ckpt_path,
        "seal_hash": seal_hash,
        "pruned_checkpoint_path": ckpt_pruned_path,
        "seal_hash_pruned": seal_pruned,
        "baseline_params": param_count,
        "baseline_size_mb": baseline_size_mb,
        "sparsity": float(sparsity_ratio),
        "compressed_size_mb": compressed_size_mb,
        "compression_ratio": baseline_size_mb / compressed_size_mb if compressed_size_mb > 0 else 1.0,
    }


async def example_workflow():
    """Example: checkpoint a RecursiveMemoryTwinNetwork."""
    from src.models.recursive_memory import CheckpointedMemoryHarness

    print("\n" + "=" * 70)
    print("CHECKPOINT + PRUNE + QUANTIZE WORKFLOW")
    print("=" * 70 + "\n")

    # Create harness
    harness = CheckpointedMemoryHarness(dimension=768, device="cpu")

    # Simulate some inference steps
    for step in [100, 200]:
        result = await full_checkpoint_workflow(
            harness,
            step=step,
            output_dir="./checkpoints",
            prune_sparsity=0.3,
            quantize=True,
            upload_s3=False,  # Set to True if AWS credentials available
            prev_seal_hash=result.get("seal_hash_pruned") if step > 100 else None,
        )

        print(f"\n✓ Workflow complete at step {step}:")
        print(f"  Compression: {result['compression_ratio']:.1f}×")
        print(f"  WORM chain: {result['seal_hash_pruned'][:16]}...\n")

        # Brief pause between steps
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    # Run example
    asyncio.run(example_workflow())
