from dataclasses import dataclass
from typing import Tuple
import jax.numpy as jnp

@dataclass
class ProofState:
    goals: jnp.ndarray
    proved: jnp.ndarray
    depth: jnp.ndarray

class ProofEnvironment:
    """Tiny deterministic sequent environment: actions rewrite or close goals."""
    def __init__(self, max_goals=8, max_depth=16):
        self.max_goals = max_goals
        self.max_depth = max_depth

    def reset(self, theorem_vector):
        goals = jnp.pad(theorem_vector, (0, self.max_goals - theorem_vector.shape[-1]))
        return ProofState(goals, jnp.array(False), jnp.array(0))

    def valid_actions(self, state):
        return jnp.stack([state.goals > 0, state.goals == 1, state.goals % 2 == 0], axis=-1)

    def step(self, state, action):
        selected = jnp.argmax(state.goals)
        value = state.goals[selected]
        closes = action == 1
        rewrites = action == 0
        next_value = jnp.where(closes, 0, jnp.where(rewrites, value // 2, value))
        goals = state.goals.at[selected].set(next_value)
        proved = jnp.all(goals == 0)
        done = proved | (state.depth + 1 >= self.max_depth)
        reward = jnp.where(proved, 1.0, jnp.where(rewrites | closes, 0.05, -0.05))
        return ProofState(goals, proved, state.depth + 1), reward, done

    def check_trace(self, theorem_vector, actions):
        state = self.reset(theorem_vector)
        rewards = []
        for action in actions:
            state, reward, done = self.step(state, action)
            rewards.append(reward)
            if bool(done):
                break
        return state.proved, jnp.asarray(rewards)
