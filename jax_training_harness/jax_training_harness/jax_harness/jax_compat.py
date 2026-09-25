"""Small compatibility helpers; the project requires JAX at runtime."""
import jax
import jax.numpy as jnp
from jax import lax, random, tree_util, grad, value_and_grad, jit, vmap, nn

def tree_l2_norm(tree):
    leaves = tree_util.tree_leaves(tree)
    return jnp.sqrt(sum(jnp.sum(jnp.square(x)) for x in leaves) + 1e-12)

def tree_zeros_like(tree):
    return tree_util.tree_map(jnp.zeros_like, tree)

def tree_clip_by_global_norm(tree, max_norm):
    norm = tree_l2_norm(tree)
    scale = jnp.minimum(1.0, max_norm / (norm + 1e-8))
    return tree_util.tree_map(lambda x: x * scale, tree), norm

def split_key(key, count):
    return random.split(key, count)
