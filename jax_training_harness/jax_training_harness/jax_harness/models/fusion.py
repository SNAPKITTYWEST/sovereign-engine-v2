import jax.numpy as jnp
from jax import nn
from .attention import init_linear, linear


def init_fusion(key, modality_dims, d_model, num_classes):
    from jax import random
    keys = random.split(key, len(modality_dims) + 2)
    projections = {name: init_linear(k, dim, d_model) for k, (name, dim) in zip(keys, modality_dims.items())}
    return {'projections': projections, 'gate': init_linear(keys[-2], d_model, len(modality_dims)),
            'head': init_linear(keys[-1], d_model, num_classes)}


def fuse(params, embeddings, training=True):
    names = list(params['projections'])
    projected = jnp.stack([linear(params['projections'][n], embeddings[n]) for n in names], axis=1)
    gates = nn.softmax(linear(params['gate'], jnp.mean(projected, axis=1)), axis=-1)
    return jnp.sum(projected * gates[..., None], axis=1)


def classify(params, embeddings):
    return linear(params['head'], fuse(params, embeddings))


def modality_dropout(embeddings, key, probability):
    from jax import random
    names = list(embeddings)
    keep = random.bernoulli(key, 1 - probability, (len(names),))
    return {name: value * keep[i] for i, (name, value) in enumerate(embeddings.items())}
