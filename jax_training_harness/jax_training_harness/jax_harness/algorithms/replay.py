from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class Transition:
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool

class ReplayBuffer:
    def __init__(self, capacity, state_shape, seed=0):
        self.capacity = capacity
        self.states = np.zeros((capacity, *state_shape), dtype=np.float32)
        self.next_states = np.zeros_like(self.states)
        self.actions = np.zeros((capacity,), dtype=np.int32)
        self.rewards = np.zeros((capacity,), dtype=np.float32)
        self.dones = np.zeros((capacity,), dtype=np.float32)
        self.position = 0
        self.size = 0
        self.rng = np.random.default_rng(seed)

    def add(self, state, action, reward, next_state, done):
        i = self.position
        self.states[i] = state
        self.actions[i] = action
        self.rewards[i] = reward
        self.next_states[i] = next_state
        self.dones[i] = done
        self.position = (i + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def extend(self, transitions):
        for transition in transitions:
            self.add(transition.state, transition.action, transition.reward, transition.next_state, transition.done)

    def sample(self, batch_size):
        if self.size < batch_size:
            raise ValueError('not enough transitions')
        indices = self.rng.choice(self.size, batch_size, replace=False)
        return {"states": self.states[indices], "actions": self.actions[indices],
                "rewards": self.rewards[indices], "next_states": self.next_states[indices],
                "dones": self.dones[indices]}

    def __len__(self):
        return self.size
