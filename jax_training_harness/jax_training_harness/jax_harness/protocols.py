"""Protocol-style components for experiment control and reproducible callbacks."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence
import time
import json
import jax.numpy as jnp

@dataclass
class Event:
    name: str
    step: int
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self.history: List[Event] = []
    def subscribe(self, name, handler):
        self._handlers.setdefault(name, []).append(handler)
        return handler
    def unsubscribe(self, name, handler):
        if name in self._handlers and handler in self._handlers[name]:
            self._handlers[name].remove(handler)
    def publish(self, event):
        self.history.append(event)
        for handler in self._handlers.get(event.name, []):
            handler(event)
        for handler in self._handlers.get('*', []):
            handler(event)
    def emit(self, name, step, **payload):
        event = Event(name, step, payload)
        self.publish(event)
        return event
    def clear(self):
        self.history.clear()
    def names(self):
        return tuple(sorted(self._handlers))

@dataclass
class EarlyStopping:
    patience: int = 10
    mode: str = 'min'
    min_delta: float = 0.0
    best: Optional[float] = None
    bad_steps: int = 0
    stopped: bool = False
    def update(self, value):
        if self.best is None:
            improved = True
        elif self.mode == 'min':
            improved = value < self.best - self.min_delta
        elif self.mode == 'max':
            improved = value > self.best + self.min_delta
        else:
            raise ValueError('mode must be min or max')
        if improved:
            self.best = float(value)
            self.bad_steps = 0
        else:
            self.bad_steps += 1
        self.stopped = self.bad_steps >= self.patience
        return self.stopped
    def reset(self):
        self.best = None
        self.bad_steps = 0
        self.stopped = False

@dataclass
class BestKeeper:
    path: Path
    mode: str = 'min'
    best: Optional[float] = None
    def consider(self, value, save_fn):
        improved = self.best is None or (value < self.best if self.mode == 'min' else value > self.best)
        if improved:
            self.best = float(value)
            save_fn(self.path)
        return improved

@dataclass
class CheckpointIndex:
    directory: Path
    keep: int = 3
    entries: List[Dict[str, Any]] = field(default_factory=list)
    def __post_init__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
    def add(self, path, step, metrics):
        self.entries.append({'path': str(path), 'step': int(step), 'metrics': _jsonable(metrics)})
        self.entries.sort(key=lambda entry: entry['step'])
        while len(self.entries) > self.keep:
            removed = self.entries.pop(0)
            Path(removed['path']).unlink(missing_ok=True)
        self.flush()
    def flush(self):
        (self.directory / 'index.json').write_text(json.dumps(self.entries, indent=2))
    def load(self):
        path = self.directory / 'index.json'
        if path.exists():
            self.entries = json.loads(path.read_text())
        return self.entries
    def latest(self):
        return self.entries[-1] if self.entries else None

class Callback:
    def on_start(self, context):
        pass
    def on_step(self, context):
        pass
    def on_epoch(self, context):
        pass
    def on_end(self, context):
        pass

class CallbackList(Callback):
    def __init__(self, callbacks=None):
        self.callbacks = list(callbacks or [])
    def on_start(self, context):
        for callback in self.callbacks:
            callback.on_start(context)
    def on_step(self, context):
        for callback in self.callbacks:
            callback.on_step(context)
    def on_epoch(self, context):
        for callback in self.callbacks:
            callback.on_epoch(context)
    def on_end(self, context):
        for callback in self.callbacks:
            callback.on_end(context)

class HistoryCallback(Callback):
    def __init__(self):
        self.history = []
    def on_step(self, context):
        self.history.append(dict(context.get('metrics', {})))
    def values(self, name):
        return [row[name] for row in self.history if name in row]
    def latest(self):
        return self.history[-1] if self.history else {}
    def mean(self, name):
        values = self.values(name)
        return sum(values) / len(values) if values else 0.0

class LRSnapshotCallback(Callback):
    def __init__(self, schedule):
        self.schedule = schedule
        self.values = []
    def on_step(self, context):
        step = context.get('step', 0)
        self.values.append(float(self.schedule(step)))

class TimerCallback(Callback):
    def __init__(self):
        self.started = None
        self.elapsed = []
    def on_start(self, context):
        self.started = time.perf_counter()
    def on_step(self, context):
        if self.started is not None:
            self.elapsed.append(time.perf_counter() - self.started)
            self.started = time.perf_counter()
    def total(self):
        return sum(self.elapsed)
    def mean_step(self):
        return self.total() / len(self.elapsed) if self.elapsed else 0.0

class JsonlCallback(Callback):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def on_step(self, context):
        with self.path.open('a') as stream:
            stream.write(json.dumps(_jsonable(context)) + '\n')

class NaNGuard(Callback):
    def __init__(self, fields=('loss',)):
        self.fields = fields
    def on_step(self, context):
        metrics = context.get('metrics', {})
        for field in self.fields:
            value = metrics.get(field)
            if value is not None and not bool(jnp.isfinite(value)):
                raise FloatingPointError(f'non-finite metric: {field}')

@dataclass
class ExperimentContext:
    config: Any
    step: int = 0
    epoch: int = 0
    metrics: Dict[str, float] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)
    def update(self, metrics):
        self.metrics.update({key: float(value) for key, value in metrics.items()})
        return self
    def as_dict(self):
        return {'step': self.step, 'epoch': self.epoch, 'metrics': self.metrics, 'extras': self.extras}

def _jsonable(value):
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if hasattr(value, 'item'):
        return value.item()
    if hasattr(value, 'tolist'):
        return value.tolist()
    return value

def aggregate_records(records, keys=None):
    records = list(records)
    if not records:
        return {}
    keys = keys or records[0].keys()
    return {key: sum(float(row[key]) for row in records if key in row) / max(sum(key in row for row in records), 1) for key in keys}

def percentile(values, q):
    values = jnp.asarray(values)
    return jnp.quantile(values, q)

def running_min(values):
    result = []
    current = None
    for value in values:
        current = value if current is None else min(current, value)
        result.append(current)
    return result

def running_max(values):
    result = []
    current = None
    for value in values:
        current = value if current is None else max(current, value)
        result.append(current)
    return result

def smooth(values, window=5):
    values = list(values)
    return [sum(values[max(0, i - window + 1):i + 1]) / len(values[max(0, i - window + 1):i + 1]) for i in range(len(values))]

def flatten_metrics(metrics, prefix=''):
    output = {}
    for key, value in metrics.items():
        name = f'{prefix}/{key}' if prefix else str(key)
        if isinstance(value, Mapping):
            output.update(flatten_metrics(value, name))
        else:
            output[name] = value
    return output

class TrainLoop:
    def __init__(self, trainer, callbacks=None):
        self.trainer = trainer
        self.callbacks = CallbackList(callbacks)
    def run(self, batches, steps):
        context = ExperimentContext(self.trainer.config)
        self.callbacks.on_start(context.as_dict())
        history = []
        for step, batch in zip(range(steps), batches):
            context.step = step
            metrics = self.trainer.train_step(batch)
            context.update(metrics._asdict())
            self.callbacks.on_step(context.as_dict())
            history.append(context.metrics.copy())
        self.callbacks.on_end(context.as_dict())
        return history

def validate_config(config, required=('batch_size', 'seq_len', 'd_model')):
    for name in required:
        if not hasattr(config, name):
            raise AttributeError(f'config lacks required field {name}')
    if config.batch_size <= 0 or config.seq_len <= 0 or config.d_model <= 0:
        raise ValueError('dimensions must be positive')
    return config

def freeze_tree(tree, predicate):
    import jax.tree_util as tree_util
    return tree_util.tree_map(lambda value: value if predicate(value) else jnp.array(value), tree)

def count_parameters(tree):
    import jax
    return sum(leaf.size for leaf in jax.tree_util.tree_leaves(tree))

def dtype_report(tree):
    import jax
    return {str(leaf.dtype): sum(1 for x in jax.tree_util.tree_leaves(tree) if str(x.dtype) == str(leaf.dtype)) for leaf in jax.tree_util.tree_leaves(tree)}

def shape_report(tree):
    import jax
    return [tuple(leaf.shape) for leaf in jax.tree_util.tree_leaves(tree)]

def validate_tree_finite(tree):
    import jax
    return all(bool(jnp.all(jnp.isfinite(leaf))) for leaf in jax.tree_util.tree_leaves(tree))
