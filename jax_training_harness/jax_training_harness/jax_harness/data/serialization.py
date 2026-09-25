from pathlib import Path
from typing import Any, Dict, Iterable, Mapping
import json
import numpy as np
import jax
import jax.numpy as jnp

class ArrayStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
    def write(self, name, value):
        path = self.root / f'{name}.npy'
        np.save(path, np.asarray(value))
        return path
    def read(self, name):
        return jnp.asarray(np.load(self.root / f'{name}.npy'))
    def exists(self, name):
        return (self.root / f'{name}.npy').exists()
    def delete(self, name):
        path = self.root / f'{name}.npy'
        if path.exists():
            path.unlink()

class JsonlLogger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def write(self, record):
        with self.path.open('a') as stream:
            stream.write(json.dumps(_jsonable(record), sort_keys=True) + '\n')
    def read(self):
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]
    def clear(self):
        self.path.unlink(missing_ok=True)

def _jsonable(value):
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, 'tolist'):
        return value.tolist()
    if hasattr(value, 'item'):
        return value.item()
    return value

def flatten_tree(tree, prefix=''):
    leaves, structure = jax.tree_util.tree_flatten(tree)
    return {f'{prefix}{index}': np.asarray(leaf) for index, leaf in enumerate(leaves)}, structure

def unflatten_tree(arrays, structure):
    ordered = [jnp.asarray(arrays[key]) for key in sorted(arrays, key=lambda x: int(x.split('_')[-1]))]
    return jax.tree_util.tree_unflatten(structure, ordered)

def save_pytree(path, tree, metadata=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    leaves, structure = jax.tree_util.tree_flatten(tree)
    payload = {f'leaf_{i}': np.asarray(value) for i, value in enumerate(leaves)}
    payload['structure'] = np.asarray([str(structure)])
    np.savez(path, **payload)
    path.with_suffix('.json').write_text(json.dumps(_jsonable(metadata or {}), indent=2))

def load_arrays(path):
    data = np.load(path)
    return {key: jnp.asarray(data[key]) for key in data.files if key.startswith('leaf_')}

def atomic_write_json(path, payload):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True))
    temporary.replace(path)
