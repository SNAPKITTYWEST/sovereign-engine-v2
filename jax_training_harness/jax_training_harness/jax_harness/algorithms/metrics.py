from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional
import jax.numpy as jnp

@dataclass
class RunningMean:
    total: float = 0.0
    count: int = 0
    def update(self, value, weight=1):
        self.total += float(value) * weight
        self.count += weight
        return self
    @property
    def value(self):
        return self.total / self.count if self.count else 0.0
    def reset(self):
        self.total = 0.0
        self.count = 0
        return self

@dataclass
class MetricStore:
    values: Dict[str, RunningMean] = field(default_factory=dict)
    def update(self, metrics: Mapping[str, float], weight=1):
        for name, value in metrics.items():
            self.values.setdefault(name, RunningMean()).update(value, weight)
        return self
    def compute(self):
        return {name: metric.value for name, metric in self.values.items()}
    def reset(self):
        for metric in self.values.values():
            metric.reset()
        return self

class ConfusionMatrix:
    def __init__(self, classes):
        self.classes = classes
        self.matrix = jnp.zeros((classes, classes), dtype=jnp.int32)
    def update(self, labels, predictions):
        flat = labels * self.classes + predictions
        counts = jnp.bincount(flat, length=self.classes * self.classes)
        self.matrix = self.matrix + counts.reshape(self.classes, self.classes)
        return self
    def accuracy(self):
        return jnp.trace(self.matrix) / jnp.maximum(jnp.sum(self.matrix), 1)
    def per_class_recall(self):
        return jnp.diag(self.matrix) / jnp.maximum(jnp.sum(self.matrix, axis=1), 1)
    def macro_recall(self):
        return jnp.mean(self.per_class_recall())
    def reset(self):
        self.matrix = jnp.zeros_like(self.matrix)
        return self

class CalibrationBins:
    def __init__(self, bins=10):
        self.bins = bins
        self.count = jnp.zeros((bins,))
        self.confidence = jnp.zeros((bins,))
        self.correct = jnp.zeros((bins,))
    def update(self, probabilities, labels):
        confidence = jnp.max(probabilities, axis=-1)
        predictions = jnp.argmax(probabilities, axis=-1)
        indices = jnp.minimum((confidence * self.bins).astype(jnp.int32), self.bins - 1)
        self.count = self.count.at[indices].add(1)
        self.confidence = self.confidence.at[indices].add(confidence)
        self.correct = self.correct.at[indices].add(predictions == labels)
        return self
    def ece(self):
        total = jnp.maximum(jnp.sum(self.count), 1)
        mean_conf = self.confidence / jnp.maximum(self.count, 1)
        mean_acc = self.correct / jnp.maximum(self.count, 1)
        return jnp.sum(jnp.abs(mean_conf - mean_acc) * self.count) / total

def masked_accuracy(logits, labels, mask=None):
    correct = (jnp.argmax(logits, axis=-1) == labels).astype(jnp.float32)
    if mask is None:
        return jnp.mean(correct)
    return jnp.sum(correct * mask) / jnp.maximum(jnp.sum(mask), 1)

def top_k_accuracy(logits, labels, k=5):
    candidates = jnp.argsort(logits, axis=-1)[:, -k:]
    return jnp.mean(jnp.any(candidates == labels[:, None], axis=-1))

def mean_absolute_error(prediction, target):
    return jnp.mean(jnp.abs(prediction - target))

def root_mean_square_error(prediction, target):
    return jnp.sqrt(jnp.mean(jnp.square(prediction - target)) + 1e-8)

def explained_variance(prediction, target):
    return 1 - jnp.var(target - prediction) / jnp.maximum(jnp.var(target), 1e-8)
