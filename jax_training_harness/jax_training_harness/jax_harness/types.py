from typing import Any, Dict, NamedTuple, Optional, Tuple
import jax.numpy as jnp
from jax import tree_util

class Batch(NamedTuple):
    tokens: jnp.ndarray
    mask: jnp.ndarray
    labels: jnp.ndarray
    features: jnp.ndarray
    adjacency: jnp.ndarray
    rewards: jnp.ndarray
    dones: jnp.ndarray
    metadata: Any = None

class Metrics(NamedTuple):
    loss: jnp.ndarray
    accuracy: jnp.ndarray
    constraint_error: jnp.ndarray
    reward: jnp.ndarray
    grad_norm: jnp.ndarray

@tree_util.register_pytree_node_class
class TrainState:
    def __init__(self, params, opt_state, step=0, ema_params=None):
        self.params = params
        self.opt_state = opt_state
        self.step = step
        self.ema_params = params if ema_params is None else ema_params

    def tree_flatten(self):
        return (self.params, self.opt_state, self.ema_params), self.step

    @classmethod
    def tree_unflatten(cls, aux, children):
        params, opt_state, ema_params = children
        return cls(params, opt_state, aux, ema_params)

    def replace(self, **kwargs):
        values = {"params": self.params, "opt_state": self.opt_state,
                  "step": self.step, "ema_params": self.ema_params}
        values.update(kwargs)
        return TrainState(**values)
