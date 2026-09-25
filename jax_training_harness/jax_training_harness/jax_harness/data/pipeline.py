from dataclasses import dataclass
from typing import Iterator, Dict, Any
import jax.numpy as jnp
from jax import random
from .generators import make_all_modalities

@dataclass
class SyntheticDataModule:
    config: Any
    seed: int
    epoch: int = 0

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        key = random.PRNGKey(self.seed + self.epoch)
        while True:
            key, batch_key = random.split(key)
            yield make_all_modalities(batch_key, self.config)

    def epoch_batches(self, count: int):
        iterator = iter(self)
        for _ in range(count):
            yield next(iterator)
        self.epoch += 1


def causal_mask(length):
    return jnp.triu(jnp.full((length, length), -jnp.inf), k=1)


def pad_sequence(values, length, pad_value=0):
    current = values.shape[-1]
    if current >= length:
        return values[..., :length]
    pad_width = [(0, 0)] * values.ndim
    pad_width[-1] = (0, length - current)
    return jnp.pad(values, pad_width, constant_values=pad_value)


def normalize_features(x, axis=0):
    mean = jnp.mean(x, axis=axis, keepdims=True)
    variance = jnp.mean(jnp.square(x - mean), axis=axis, keepdims=True)
    return (x - mean) / jnp.sqrt(variance + 1e-6), mean, variance


def batch_to_device(batch, device=None):
    if device is None:
        return batch
    import jax
    return jax.device_put(batch, device)
