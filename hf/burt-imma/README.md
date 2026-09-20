# BURT-IMMA component reference

This directory contains [NumPy modeling code](modeling_burt_imma.py) and [configuration metadata](config.json). It does not contain trained weights or a recorded comparison against a standard transformer.

Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST).

## Matrix memory

`CIFGCell(d, seed=None)` maintains a `d × d` matrix. For an input vector `x`, it computes forget, value, key, and query projections, updates memory using coupled forget/input weights, and retrieves a vector from that memory:

```text
f = sigmoid(W_f x)
v = tanh(W_v x)
k = tanh(W_k x)
C <- f[:, None] * C + (1 - f[:, None]) * outer(v, k)
y = (W_q x) @ C
```

The source also provides `smooth_leaky` and `entropy_constrained_softmax`. These are functions; the previously documented `CIFGMatrixMemoryCell(input_dim=...)` interface does not exist in this file.

## Local example

Run from this directory with NumPy installed:

```python
import numpy as np
from modeling_burt_imma import CIFGCell, entropy_constrained_softmax

cell = CIFGCell(d=8, seed=0)
output = cell.step(np.ones(8, dtype=np.float32))
assert output.shape == (8,)
assert np.isfinite(output).all()
weights = entropy_constrained_softmax(np.array([0.0, 1.0, 2.0]))
assert np.isclose(weights.sum(), 1.0)
print(output.shape, weights)
```

## Entropy limits

The softmax helper reduces temperature while measured entropy exceeds the requested budget and temperature remains above its cutoff. It does not enforce the bound for every input: equal logits remain uniform under temperature changes. Evaluate the returned distribution rather than assuming a guaranteed `0.20`-nat bound.

The related [Lean source](../../research/formal/sovereign_entropy/EntropyBound.lean) states a mathematical result under its assumptions. No native proof-check run or equivalence proof between that file and this function is recorded here. The former “60% fewer parameters” comparison lacked a specified baseline and measurement.

## Integration

The engine has a separate [BURT-IMMA module](../../src/models/burt_imma.py). Inspect signatures before swapping implementations. See [model and training overview](../../README.md#models-and-training) and [validation](../../docs/VALIDATION.md).

## License

Consult [LICENSE.tri](../../LICENSE.tri) and component metadata. This documentation does not assign a new license.
