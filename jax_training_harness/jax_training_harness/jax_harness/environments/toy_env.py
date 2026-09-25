from dataclasses import dataclass
import jax.numpy as jnp
from jax import random

@dataclass
class LineWorld:
    length: int = 11
    max_steps: int = 32

    def reset(self, key):
        position = jnp.array(self.length // 2, dtype=jnp.int32)
        return position, {'steps': jnp.array(0), 'key': key}

    def step(self, state, action, info):
        direction = jnp.where(action == 0, -1, 1)
        next_position = jnp.clip(state + direction, 0, self.length - 1)
        reached = next_position == self.length - 1
        timeout = info['steps'] + 1 >= self.max_steps
        reward = jnp.where(reached, 1.0, -0.01)
        return next_position, reward, jnp.logical_or(reached, timeout), {'steps': info['steps'] + 1, 'key': info['key']}

    def rollout(self, key, policy, horizon=32):
        state, info = self.reset(key)
        def body(carry, _):
            state, info, done = carry
            action = policy(state, info['key'])
            next_state, reward, next_done, next_info = self.step(state, action, info)
            return (next_state, next_info, next_done), (state, action, reward, next_done)
        _, trajectory = __import__('jax').lax.scan(body, (state, info, False), None, length=horizon)
        return trajectory
