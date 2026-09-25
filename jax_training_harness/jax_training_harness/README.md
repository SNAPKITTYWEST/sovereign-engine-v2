# JAX Training Harness

This repository is a from-scratch training harness for deterministic and structured learning workloads. It covers formal proof traces, algebraic constraints, reinforcement-learning trajectories, graph relational structures, tabular databases, time-series telemetry, visual tensors, and audio waveforms. The implementation is intentionally explicit: datasets, model components, losses, optimizers, checkpointing, metrics, evaluation, and experiment orchestration are all visible and testable.

## Design principles

* **Pure functional cores.** Forward functions, losses, environment transitions, and optimizer steps are pure JAX transformations whenever practical.
* **Static shapes.** Batches are padded or windowed to predictable shapes so `jit`, `vmap`, `scan`, and `pmap` can be layered without hidden Python work.
* **Deterministic experiments.** Every generator owns a PRNG key and every run records configuration, seed, metrics, and checkpoints.
* **Modality adapters.** Each input type is converted into a common `Batch` structure while retaining modality-specific fields.
* **Verifiable constraints.** Formal and algebraic tasks expose residuals and exact checks, not only a scalar prediction loss.

## Quick start

```bash
python -m pip install -r requirements.txt
python -m jax_harness.cli --steps 10 --batch-size 8 --seq-len 32
pytest
```

The CLI runs a compact smoke experiment on CPU. For a larger run, pass `--steps`, `--batch-size`, and `--d-model`. Checkpoints are `.npz` snapshots with JSON metadata; they are intentionally portable and easy to inspect.

## Layout

`jax_harness/data` contains deterministic generators and collators. `models` contains embeddings, attention, MLP, graph message passing, convolution-like signal features, and modality fusion. `algorithms` contains losses, constraints, optimizers, replay buffers, and the trainer. `environments` includes a tiny command-line environment and formal-proof transition environment. `tests` verifies shapes, gradients, deterministic replay, constraints, and an end-to-end update.
