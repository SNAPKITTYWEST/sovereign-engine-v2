"""Structured JAX training harness."""
from .config import HarnessConfig
from .types import Batch, TrainState, Metrics
__all__ = ["HarnessConfig", "Batch", "TrainState", "Metrics"]
