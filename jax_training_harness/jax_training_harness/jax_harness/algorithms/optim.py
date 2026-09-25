from typing import Any
import jax.numpy as jnp
from jax import tree_util
from ..jax_compat import tree_clip_by_global_norm, tree_l2_norm

class AdamW:
    def __init__(self, learning_rate=1e-3, weight_decay=1e-4, beta1=0.9, beta2=0.999, eps=1e-8, max_grad_norm=1.0):
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.max_grad_norm = max_grad_norm

    def init(self, params):
        zeros = tree_util.tree_map(jnp.zeros_like, params)
        return {'m': zeros, 'v': zeros, 'step': jnp.array(0, dtype=jnp.int32)}

    def update(self, params, grads, state):
        grads, grad_norm = tree_clip_by_global_norm(grads, self.max_grad_norm)
        step = state['step'] + 1
        m = tree_util.tree_map(lambda a, g: self.beta1 * a + (1 - self.beta1) * g, state['m'], grads)
        v = tree_util.tree_map(lambda a, g: self.beta2 * a + (1 - self.beta2) * jnp.square(g), state['v'], grads)
        mhat = tree_util.tree_map(lambda x: x / (1 - self.beta1 ** step), m)
        vhat = tree_util.tree_map(lambda x: x / (1 - self.beta2 ** step), v)
        new_params = tree_util.tree_map(lambda p, mm, vv: p - self.learning_rate * (mm / (jnp.sqrt(vv) + self.eps) + self.weight_decay * p), params, mhat, vhat)
        return new_params, {'m': m, 'v': v, 'step': step}, grad_norm

    def schedule(self, step, warmup=0):
        if warmup <= 0:
            return self.learning_rate
        return self.learning_rate * jnp.minimum(1.0, (step + 1) / warmup)

class SGD:
    def __init__(self, learning_rate=1e-2, momentum=0.9):
        self.learning_rate = learning_rate
        self.momentum = momentum

    def init(self, params):
        return {'velocity': tree_util.tree_map(jnp.zeros_like, params), 'step': jnp.array(0)}

    def update(self, params, grads, state):
        velocity = tree_util.tree_map(lambda v, g: self.momentum * v + g, state['velocity'], grads)
        params = tree_util.tree_map(lambda p, v: p - self.learning_rate * v, params, velocity)
        return params, {'velocity': velocity, 'step': state['step'] + 1}, tree_l2_norm(grads)
