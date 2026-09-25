from dataclasses import dataclass
from typing import Any, Callable, Iterable
import jax
import jax.numpy as jnp
from .jax_compat import tree_l2_norm

@dataclass
class DeviceInfo:
    count: int
    local_count: int
    platform: str
    devices: tuple

def device_info():
    devices = tuple(jax.devices())
    local = tuple(jax.local_devices())
    return DeviceInfo(len(devices), len(local), devices[0].platform if devices else 'unknown', devices)

def shard_batch(batch, devices=None):
    devices = tuple(jax.local_devices() if devices is None else devices)
    count = len(devices)
    return jax.tree_util.tree_map(lambda value: jnp.asarray(value).reshape((count, -1) + jnp.asarray(value).shape[1:]), batch)

def replicate_tree(tree, devices=None):
    return jax.device_put_replicated(tree, jax.local_devices() if devices is None else devices)

def unreplicate_tree(tree):
    return jax.tree_util.tree_map(lambda value: value[0], tree)

def average_gradients(grads, axis_name='devices'):
    return jax.lax.pmean(grads, axis_name=axis_name)

def synchronize_metrics(metrics, axis_name='devices'):
    return jax.tree_util.tree_map(lambda value: jax.lax.pmean(value, axis_name=axis_name), metrics)

def make_pmap_step(step_fn, axis_name='devices'):
    return jax.pmap(step_fn, axis_name=axis_name)

def split_for_devices(key, devices=None):
    count = len(jax.local_devices() if devices is None else devices)
    return jax.random.split(key, count)

def tree_equal(left, right, atol=1e-6):
    leaves_left = jax.tree_util.tree_leaves(left)
    leaves_right = jax.tree_util.tree_leaves(right)
    if len(leaves_left) != len(leaves_right):
        return False
    return all(bool(jnp.allclose(a, b, atol=atol)) for a, b in zip(leaves_left, leaves_right))

def gradient_statistics(grads):
    leaves = jax.tree_util.tree_leaves(grads)
    norms = jnp.asarray([jnp.linalg.norm(x) for x in leaves])
    return {'global_norm': tree_l2_norm(grads), 'max_norm': jnp.max(norms), 'mean_norm': jnp.mean(norms), 'leaf_count': len(leaves)}
