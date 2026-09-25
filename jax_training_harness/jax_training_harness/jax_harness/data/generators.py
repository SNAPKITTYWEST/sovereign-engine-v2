from typing import Dict, Tuple
import jax.numpy as jnp
from jax import random


def _normal(key, shape, scale=1.0):
    return scale * random.normal(key, shape)


def make_formal_proof_batch(key, batch_size, seq_len, vocab_size):
    k1, k2, k3 = random.split(key, 3)
    tokens = random.randint(k1, (batch_size, seq_len), 0, vocab_size)
    premises = random.randint(k2, (batch_size, 4), 0, vocab_size)
    theorem = jnp.mod(jnp.sum(premises, axis=-1), vocab_size)
    labels = jnp.mod(theorem + tokens[:, 0], vocab_size)
    mask = jnp.ones((batch_size, seq_len), dtype=jnp.float32)
    features = _normal(k3, (batch_size, seq_len, 8))
    return tokens, mask, labels, features


def make_algebraic_constraints(key, batch_size, width=8):
    k1, k2 = random.split(key)
    x = random.uniform(k1, (batch_size, width), minval=-1, maxval=1)
    coeff = random.normal(k2, (width, width))
    target = jnp.einsum('bi,ij,bj->b', x, coeff, x)
    return x, coeff, target


def make_rl_batch(key, batch_size, seq_len, state_dim=16, action_dim=4):
    ks = random.split(key, 5)
    states = random.normal(ks[0], (batch_size, seq_len, state_dim))
    actions = random.randint(ks[1], (batch_size, seq_len), 0, action_dim)
    rewards = random.normal(ks[2], (batch_size, seq_len))
    dones = random.bernoulli(ks[3], 0.05, (batch_size, seq_len))
    next_states = states + 0.1 * random.normal(ks[4], states.shape)
    return states, actions, rewards, dones, next_states


def make_graph_batch(key, batch_size, nodes, node_dim=16):
    k1, k2, k3 = random.split(key, 3)
    node_features = random.normal(k1, (batch_size, nodes, node_dim))
    logits = random.normal(k2, (batch_size, nodes, nodes))
    adjacency = (logits > 0.4).astype(jnp.float32)
    adjacency = adjacency * (1 - jnp.eye(nodes)[None, :, :])
    labels = random.randint(k3, (batch_size,), 0, 2)
    return node_features, adjacency, labels


def make_tabular_batch(key, batch_size, columns=12, classes=8):
    k1, k2 = random.split(key)
    x = random.normal(k1, (batch_size, columns))
    x = (x - jnp.mean(x, axis=0)) / (jnp.std(x, axis=0) + 1e-5)
    y = random.randint(k2, (batch_size,), 0, classes)
    return x, y


def make_timeseries_batch(key, batch_size, seq_len, channels=6):
    k1, k2 = random.split(key)
    t = jnp.linspace(0, 1, seq_len)[None, :, None]
    frequencies = random.uniform(k1, (batch_size, 1, channels), minval=1, maxval=8)
    phase = random.uniform(k2, (batch_size, 1, channels), minval=0, maxval=6.28)
    signal = jnp.sin(6.28 * frequencies * t + phase)
    trend = t * random.normal(k1, (batch_size, 1, channels))
    return signal + 0.1 * trend, frequencies[:, 0, :]


def make_visual_batch(key, batch_size, size, classes=8):
    k1, k2, k3 = random.split(key, 3)
    images = random.uniform(k1, (batch_size, size, size, 3))
    labels = random.randint(k2, (batch_size,), 0, classes)
    boxes = random.uniform(k3, (batch_size, 4))
    return images, labels, boxes


def make_audio_batch(key, batch_size, samples, classes=8):
    k1, k2 = random.split(key)
    t = jnp.arange(samples)[None, :] / samples
    frequency = random.uniform(k1, (batch_size, 1), minval=1, maxval=20)
    waveform = jnp.sin(2 * jnp.pi * frequency * t)
    waveform += 0.05 * random.normal(k2, waveform.shape)
    labels = jnp.mod(frequency[:, 0].astype(jnp.int32), classes)
    return waveform[..., None], labels


def make_all_modalities(key, cfg):
    keys = random.split(key, 8)
    return {
        'formal': make_formal_proof_batch(keys[0], cfg.batch_size, cfg.seq_len, cfg.vocab_size),
        'algebraic': make_algebraic_constraints(keys[1], cfg.batch_size),
        'rl': make_rl_batch(keys[2], cfg.batch_size, cfg.seq_len),
        'graph': make_graph_batch(keys[3], cfg.batch_size, cfg.graph_nodes),
        'tabular': make_tabular_batch(keys[4], cfg.batch_size, classes=cfg.num_classes),
        'timeseries': make_timeseries_batch(keys[5], cfg.batch_size, cfg.seq_len),
        'visual': make_visual_batch(keys[6], cfg.batch_size, cfg.image_size, cfg.num_classes),
        'audio': make_audio_batch(keys[7], cfg.batch_size, cfg.audio_samples, cfg.num_classes),
    }
