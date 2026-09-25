from dataclasses import dataclass
from typing import Any, Dict, Callable
import json
from pathlib import Path
import jax
import jax.numpy as jnp
from ..types import TrainState, Metrics
from ..jax_compat import tree_l2_norm

@dataclass
class StepOutput:
    state: TrainState
    metrics: Metrics

class Trainer:
    def __init__(self, params, optimizer, loss_fn, config):
        self.optimizer = optimizer
        self.loss_fn = loss_fn
        self.config = config
        self.state = TrainState(params, optimizer.init(params))
        self._compiled_step = jax.jit(self._step)

    def _step(self, state, batch):
        def objective(params):
            loss, aux = self.loss_fn(params, batch)
            return loss, aux
        (loss, aux), grads = jax.value_and_grad(objective, has_aux=True)(state.params)
        params, opt_state, grad_norm = self.optimizer.update(state.params, grads, state.opt_state)
        ema = jax.tree_util.tree_map(lambda old, new: 0.999 * old + 0.001 * new, state.ema_params, params)
        metrics = Metrics(loss=loss, accuracy=aux.get('accuracy', 0.0),
                          constraint_error=aux.get('constraint_error', 0.0),
                          reward=aux.get('reward', 0.0), grad_norm=grad_norm)
        return state.replace(params=params, opt_state=opt_state, step=state.step + 1, ema_params=ema), metrics

    def train_step(self, batch):
        self.state, metrics = self._compiled_step(self.state, batch)
        return metrics

    def train(self, batches, steps, log_every=10):
        history = []
        for step, batch in zip(range(steps), batches):
            metrics = self.train_step(batch)
            values = {name: float(value) for name, value in metrics._asdict().items()}
            history.append(values)
            if log_every and (step + 1) % log_every == 0:
                print(f"step={step + 1} " + ' '.join(f"{k}={v:.5f}" for k, v in values.items()))
        return history

    def evaluate(self, batches, steps):
        metrics = []
        params = self.state.ema_params
        for batch in batches:
            _, aux = self.loss_fn(params, batch)
            metrics.append(aux)
            if len(metrics) >= steps:
                break
        if not metrics:
            return {}
        keys = metrics[0].keys()
        return {key: float(jnp.mean(jnp.asarray([m.get(key, 0.0) for m in metrics]))) for key in keys}

    def save(self, path, metadata=None):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        leaves, treedef = jax.tree_util.tree_flatten(self.state.params)
        arrays = {f'param_{i}': jnp.asarray(x) for i, x in enumerate(leaves)}
        arrays['step'] = jnp.asarray(self.state.step)
        import numpy as np
        np.savez(path, **{k: np.asarray(v) for k, v in arrays.items()})
        path.with_suffix('.json').write_text(json.dumps(metadata or {}, indent=2))

    @staticmethod
    def summary(history):
        if not history:
            return {}
        keys = history[0]
        return {key: sum(row[key] for row in history) / len(history) for key in keys}
