from dataclasses import dataclass
from typing import Callable, Sequence
import jax.numpy as jnp

@dataclass
class ConstantSchedule:
    value: float
    def __call__(self, step):
        return jnp.asarray(self.value)

@dataclass
class LinearWarmup:
    peak: float
    warmup_steps: int
    def __call__(self, step):
        return self.peak * jnp.minimum(1.0, (step + 1) / max(self.warmup_steps, 1))

@dataclass
class CosineDecay:
    peak: float
    total_steps: int
    minimum: float = 0.0
    def __call__(self, step):
        progress = jnp.clip(step / max(self.total_steps, 1), 0.0, 1.0)
        return self.minimum + 0.5 * (self.peak - self.minimum) * (1 + jnp.cos(jnp.pi * progress))

@dataclass
class WarmupCosine:
    peak: float
    warmup_steps: int
    total_steps: int
    minimum: float = 0.0
    def __call__(self, step):
        warm = self.peak * (step + 1) / max(self.warmup_steps, 1)
        cosine = self.minimum + 0.5 * (self.peak - self.minimum) * (1 + jnp.cos(jnp.pi * (step - self.warmup_steps) / max(self.total_steps - self.warmup_steps, 1)))
        return jnp.where(step < self.warmup_steps, warm, cosine)

@dataclass
class ExponentialDecay:
    initial: float
    decay_rate: float
    decay_steps: int
    staircase: bool = False
    def __call__(self, step):
        exponent = step / max(self.decay_steps, 1)
        exponent = jnp.floor(exponent) if self.staircase else exponent
        return self.initial * self.decay_rate ** exponent

@dataclass
class PolynomialDecay:
    initial: float
    end: float
    power: float
    total_steps: int
    def __call__(self, step):
        progress = jnp.clip(step / max(self.total_steps, 1), 0.0, 1.0)
        return (self.initial - self.end) * (1 - progress) ** self.power + self.end

class PiecewiseSchedule:
    def __init__(self, boundaries: Sequence[int], schedules: Sequence[Callable]):
        if len(schedules) != len(boundaries) + 1:
            raise ValueError('one more schedule than boundaries is required')
        self.boundaries = tuple(boundaries)
        self.schedules = tuple(schedules)
    def __call__(self, step):
        value = self.schedules[-1](step)
        for boundary, schedule in reversed(list(zip(self.boundaries, self.schedules))):
            value = jnp.where(step < boundary, schedule(step), value)
        return value

def clip_schedule(schedule, lower, upper):
    return lambda step: jnp.clip(schedule(step), lower, upper)

def scale_schedule(schedule, factor):
    return lambda step: factor * schedule(step)

def build_schedule(name, learning_rate, total_steps, warmup_steps=0):
    if name == 'constant':
        return ConstantSchedule(learning_rate)
    if name == 'cosine':
        return CosineDecay(learning_rate, total_steps)
    if name == 'warmup_cosine':
        return WarmupCosine(learning_rate, warmup_steps, total_steps)
    if name == 'exponential':
        return ExponentialDecay(learning_rate, 0.95, max(total_steps // 10, 1))
    raise ValueError(f'unknown schedule: {name}')
