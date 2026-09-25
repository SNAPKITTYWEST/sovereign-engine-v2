import jax.numpy as jnp
from jax import nn


def cross_entropy(logits, labels, mask=None):
    log_probs = nn.log_softmax(logits, axis=-1)
    picked = jnp.take_along_axis(log_probs, labels[..., None], axis=-1)[..., 0]
    if mask is None:
        return -jnp.mean(picked)
    return -jnp.sum(picked * mask) / (jnp.sum(mask) + 1e-6)


def mse(prediction, target, mask=None):
    error = jnp.square(prediction - target)
    if mask is None:
        return jnp.mean(error)
    return jnp.sum(error * mask) / (jnp.sum(mask) + 1e-6)


def huber(prediction, target, delta=1.0):
    error = jnp.abs(prediction - target)
    quadratic = jnp.minimum(error, delta)
    linear = error - quadratic
    return jnp.mean(0.5 * quadratic ** 2 + delta * linear)


def binary_cross_entropy(logits, labels):
    return jnp.mean(nn.softplus(logits) - labels * logits)


def entropy(logits):
    probs = nn.softmax(logits, axis=-1)
    return -jnp.mean(jnp.sum(probs * nn.log_softmax(logits, axis=-1), axis=-1))


def discounted_returns(rewards, dones, gamma=0.99):
    def step(carry, values):
        reward, done = values
        output = reward + gamma * carry * (1 - done)
        return output, output
    _, returns = __import__('jax').lax.scan(step, jnp.zeros(rewards.shape[0]), (rewards.T, dones.T))
    return returns.T


def gae(rewards, values, dones, gamma=0.99, lam=0.95):
    next_values = jnp.concatenate([values[:, 1:], values[:, -1:]], axis=1)
    deltas = rewards + gamma * next_values * (1 - dones) - values
    def step(carry, values):
        delta, done = values
        out = delta + gamma * lam * carry * (1 - done)
        return out, out
    _, advantages = __import__('jax').lax.scan(step, jnp.zeros(rewards.shape[0]), (deltas[:, ::-1].T, dones[:, ::-1].T))
    return advantages[::-1].T


def contrastive_loss(left, right, temperature=0.07):
    left = left / (jnp.linalg.norm(left, axis=-1, keepdims=True) + 1e-8)
    right = right / (jnp.linalg.norm(right, axis=-1, keepdims=True) + 1e-8)
    logits = left @ right.T / temperature
    labels = jnp.arange(logits.shape[0])
    return 0.5 * (cross_entropy(logits, labels) + cross_entropy(logits.T, labels))
