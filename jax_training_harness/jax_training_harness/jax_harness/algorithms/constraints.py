from typing import Dict, Callable
import jax.numpy as jnp
from jax import lax


def polynomial_residual(x, coeff):
    return jnp.einsum('bi,ij,bj->b', x, coeff, x)


def equality_penalty(residual, power=2):
    return jnp.mean(jnp.abs(residual) ** power)


def inequality_penalty(value, lower=None, upper=None):
    penalty = jnp.zeros_like(value)
    if lower is not None:
        penalty = penalty + jnp.square(jnp.minimum(value - lower, 0))
    if upper is not None:
        penalty = penalty + jnp.square(jnp.maximum(value - upper, 0))
    return jnp.mean(penalty)


def lagrangian(objective, residuals, multipliers, penalty=1.0):
    residual_vector = jnp.stack([jnp.mean(r) for r in residuals])
    return objective + jnp.dot(multipliers, residual_vector) + penalty * jnp.sum(jnp.square(residual_vector))


def project_simplex(x, total=1.0):
    u = jnp.sort(x, axis=-1)[..., ::-1]
    cssv = jnp.cumsum(u, axis=-1) - total
    ind = jnp.arange(1, x.shape[-1] + 1)
    cond = u - cssv / ind > 0
    rho = jnp.sum(cond, axis=-1, keepdims=True) - 1
    theta = jnp.take_along_axis(cssv, rho, axis=-1) / (rho + 1)
    return jnp.maximum(x - theta, 0)


def check_conservation(flow, tolerance=1e-5):
    residual = jnp.sum(flow, axis=-1)
    return residual, jnp.all(jnp.abs(residual) <= tolerance)


def check_boolean(logits):
    values = __import__('jax').nn.sigmoid(logits)
    residual = values * (1 - values)
    return residual, jnp.mean(residual)


def exact_modular_constraint(values, modulus, target):
    return jnp.mod(values - target, modulus)


def constraint_report(residuals: Dict[str, jnp.ndarray]):
    return {name: {'mean_abs': jnp.mean(jnp.abs(value)), 'max_abs': jnp.max(jnp.abs(value))}
            for name, value in residuals.items()}
