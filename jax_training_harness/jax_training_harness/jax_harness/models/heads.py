from typing import Dict, Tuple
import jax.numpy as jnp
from jax import nn, random
from .attention import init_linear, linear

class LinearHead:
    def __init__(self, params):
        self.params = params
    def __call__(self, x):
        return linear(self.params, x)

def init_classification_head(key, in_dim, classes):
    return init_linear(key, in_dim, classes)

def init_regression_head(key, in_dim, outputs=1):
    return init_linear(key, in_dim, outputs)

def classification_logits(params, embeddings):
    return linear(params, embeddings)

def regression_output(params, embeddings):
    return linear(params, embeddings)

def ordinal_logits(params, embeddings, levels):
    raw = linear(params, embeddings)
    thresholds = jnp.cumsum(nn.softplus(raw[..., :levels]), axis=-1)
    return thresholds

def multilabel_logits(params, embeddings):
    return linear(params, embeddings)

def multilabel_loss(logits, labels):
    return jnp.mean(nn.softplus(logits) - labels * logits)

def focal_loss(logits, labels, gamma=2.0):
    probabilities = nn.softmax(logits, axis=-1)
    selected = jnp.take_along_axis(probabilities, labels[..., None], axis=-1)[..., 0]
    return -jnp.mean((1 - selected) ** gamma * jnp.log(selected + 1e-8))

def label_smoothed_loss(logits, labels, smoothing=0.1):
    classes = logits.shape[-1]
    one_hot = jax_one_hot(labels, classes)
    targets = one_hot * (1 - smoothing) + smoothing / classes
    return -jnp.mean(jnp.sum(targets * nn.log_softmax(logits), axis=-1))

def jax_one_hot(labels, classes):
    return (jnp.arange(classes) == labels[..., None]).astype(jnp.float32)

def gaussian_nll(mean, log_scale, target):
    precision = jnp.exp(-2 * log_scale)
    return jnp.mean(0.5 * (jnp.square(target - mean) * precision + 2 * log_scale))

def quantile_loss(prediction, target, quantile):
    error = target - prediction
    return jnp.mean(jnp.maximum(quantile * error, (quantile - 1) * error))

def mixture_mean(weights, means):
    weights = nn.softmax(weights, axis=-1)
    return jnp.sum(weights * means, axis=-1)

def mixture_variance(weights, means, scales):
    weights = nn.softmax(weights, axis=-1)
    center = mixture_mean(weights, means)
    return jnp.sum(weights * (jnp.square(scales) + jnp.square(means - center[..., None])), axis=-1)
