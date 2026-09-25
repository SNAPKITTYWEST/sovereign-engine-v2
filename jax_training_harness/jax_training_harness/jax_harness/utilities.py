"""Reusable pure-JAX utilities used by data pipelines and training loops.

The functions in this module deliberately avoid hidden host-side state. They are
small building blocks suitable for jit, vmap, scan, and unit testing.
"""
import math
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple
import jax
import jax.numpy as jnp
from jax import lax, nn, random

Array = jnp.ndarray

def safe_divide(numerator, denominator, epsilon=1e-8):
    return numerator / (denominator + epsilon)

def safe_log(value, epsilon=1e-8):
    return jnp.log(jnp.maximum(value, epsilon))

def l2_normalize(value, axis=-1):
    return value / (jnp.linalg.norm(value, axis=axis, keepdims=True) + 1e-8)

def cosine_similarity(left, right, axis=-1):
    return jnp.sum(l2_normalize(left, axis) * l2_normalize(right, axis), axis=axis)

def pairwise_squared_distance(left, right):
    return jnp.sum(jnp.square(left[:, None, :] - right[None, :, :]), axis=-1)

def one_hot(labels, classes):
    return (jnp.arange(classes) == labels[..., None]).astype(jnp.float32)

def one_hot_smooth(labels, classes, smoothing=0.1):
    return one_hot(labels, classes) * (1 - smoothing) + smoothing / classes

def masked_sum(values, mask, axis=None):
    return jnp.sum(values * mask, axis=axis)

def masked_mean(values, mask, axis=None):
    return safe_divide(masked_sum(values, mask, axis), jnp.sum(mask, axis=axis))

def masked_var(values, mask, axis=None):
    mean = masked_mean(values, mask, axis)
    centered = values - jnp.expand_dims(mean, axis if axis is not None else 0)
    return masked_mean(jnp.square(centered), mask, axis)

def lengths_to_mask(lengths, max_length=None):
    max_length = int(jnp.max(lengths)) if max_length is None else max_length
    return jnp.arange(max_length)[None, :] < lengths[:, None]

def sequence_mask(length, max_length):
    return jnp.arange(max_length) < length

def causal_mask_bool(length):
    positions = jnp.arange(length)
    return positions[None, :] <= positions[:, None]

def additive_causal_mask(length, dtype=jnp.float32):
    return jnp.where(causal_mask_bool(length), 0, jnp.finfo(dtype).min)

def expand_mask(mask, heads=1):
    return mask[:, None, None, :] if heads else mask[..., None]

def flatten_batch(value):
    return value.reshape((-1,) + value.shape[2:])

def unflatten_batch(value, batch, time):
    return value.reshape((batch, time) + value.shape[1:])

def pad_to_multiple(value, multiple, axis=1, constant=0):
    size = value.shape[axis]
    remainder = size % multiple
    amount = (multiple - remainder) % multiple
    pads = [(0, 0)] * value.ndim
    pads[axis] = (0, amount)
    return jnp.pad(value, pads, constant_values=constant)

def window_1d(value, size, stride=1):
    count = (value.shape[1] - size) // stride + 1
    starts = jnp.arange(count) * stride
    return jnp.stack([value[:, start:start + size] for start in starts], axis=1)

def rolling_mean(value, window):
    windows = window_1d(value[:, :, None], window)[..., 0]
    return jnp.mean(windows, axis=-1)

def rolling_std(value, window):
    windows = window_1d(value[:, :, None], window)[..., 0]
    return jnp.std(windows, axis=-1)

def interpolate_1d(value, positions):
    left = jnp.floor(positions).astype(jnp.int32)
    right = jnp.minimum(left + 1, value.shape[-1] - 1)
    weight = positions - left
    return value[..., left] * (1 - weight) + value[..., right] * weight

def normalize_minmax(value, axis=None):
    low = jnp.min(value, axis=axis, keepdims=True)
    high = jnp.max(value, axis=axis, keepdims=True)
    return safe_divide(value - low, high - low)

def standardize(value, axis=None):
    mean = jnp.mean(value, axis=axis, keepdims=True)
    std = jnp.std(value, axis=axis, keepdims=True)
    return safe_divide(value - mean, std)

def robust_standardize(value, axis=None):
    median = jnp.median(value, axis=axis, keepdims=True)
    mad = jnp.median(jnp.abs(value - median), axis=axis, keepdims=True)
    return safe_divide(value - median, 1.4826 * mad)

def clip_by_value(value, low, high):
    return jnp.clip(value, low, high)

def clip_by_percentile(value, low=0.01, high=0.99, axis=None):
    lower = jnp.quantile(value, low, axis=axis, keepdims=True)
    upper = jnp.quantile(value, high, axis=axis, keepdims=True)
    return jnp.clip(value, lower, upper)

def dropout(key, value, rate, deterministic=False):
    if deterministic or rate == 0:
        return value
    keep = random.bernoulli(key, 1 - rate, value.shape)
    return value * keep / (1 - rate)

def stochastic_depth(key, value, rate, deterministic=False):
    if deterministic or rate == 0:
        return value
    keep = random.bernoulli(key, 1 - rate, (value.shape[0],) + (1,) * (value.ndim - 1))
    return value * keep / (1 - rate)

def mixup(key, left, right, alpha=0.2):
    if alpha <= 0:
        return left, right, jnp.ones((left.shape[0],))
    concentration = jnp.asarray(alpha)
    lam = random.beta(key, concentration, concentration, (left.shape[0],))
    shape = (left.shape[0],) + (1,) * (left.ndim - 1)
    return lam.reshape(shape) * left + (1 - lam).reshape(shape) * right, lam, lam

def cutmix(key, left, right, fraction=0.25):
    width = max(1, int(left.shape[-2] * fraction))
    start = random.randint(key, (), 0, left.shape[-2] - width + 1)
    result = left.at[..., start:start + width, :].set(right[..., start:start + width, :])
    ratio = 1 - width / left.shape[-2]
    return result, jnp.asarray(ratio)

def random_crop(key, value, crop_height, crop_width):
    height, width = value.shape[-3:-1]
    k1, k2 = random.split(key)
    top = random.randint(k1, (), 0, height - crop_height + 1)
    left = random.randint(k2, (), 0, width - crop_width + 1)
    return lax.dynamic_slice(value, (0, top, left, 0), (value.shape[0], crop_height, crop_width, value.shape[-1]))

def horizontal_flip(key, images, probability=0.5):
    do_flip = random.bernoulli(key, probability, (images.shape[0],))
    flipped = images[..., ::-1, :]
    return jnp.where(do_flip[:, None, None, None], flipped, images)

def random_noise(key, value, scale=0.01):
    return value + scale * random.normal(key, value.shape)

def random_scale(key, value, low=0.9, high=1.1):
    factors = random.uniform(key, (value.shape[0],) + (1,) * (value.ndim - 1), minval=low, maxval=high)
    return value * factors

def random_shift(key, value, max_shift):
    shifts = random.randint(key, (value.shape[0],), -max_shift, max_shift + 1)
    return jnp.stack([jnp.roll(row, shift, axis=0) for row, shift in zip(value, shifts)])

def fft_magnitude(value, axis=-1):
    return jnp.abs(jnp.fft.rfft(value, axis=axis))

def fft_power(value, axis=-1):
    return jnp.square(fft_magnitude(value, axis))

def spectral_centroid(value, axis=-1):
    power = fft_power(value, axis)
    frequencies = jnp.arange(power.shape[axis])
    numerator = jnp.sum(power * frequencies, axis=axis)
    return safe_divide(numerator, jnp.sum(power, axis=axis))

def spectral_rolloff(value, fraction=0.85, axis=-1):
    power = fft_power(value, axis)
    cumulative = jnp.cumsum(power, axis=axis)
    threshold = fraction * jnp.sum(power, axis=axis, keepdims=True)
    indices = jnp.arange(power.shape[axis])
    selected = cumulative >= threshold
    return jnp.sum(selected * indices, axis=axis)

def zero_crossing_rate(value, axis=-1):
    signs = jnp.sign(value)
    changes = signs[..., 1:] != signs[..., :-1]
    return jnp.mean(changes, axis=axis)

def rms_energy(value, axis=-1):
    return jnp.sqrt(jnp.mean(jnp.square(value), axis=axis) + 1e-8)

def hann_window(size):
    return jnp.hanning(size)

def frame_signal(value, frame, hop):
    starts = jnp.arange(0, value.shape[-1] - frame + 1, hop)
    return jnp.stack([value[..., start:start + frame] for start in starts], axis=-2)

def log_magnitude_spectrogram(value, frame=32, hop=16):
    frames = frame_signal(value, frame, hop)
    windowed = frames * hann_window(frame)
    return jnp.log1p(fft_magnitude(windowed))

def mel_filterbank(bins, frequencies, bands=24):
    points = jnp.linspace(0, bins - 1, bands + 2)
    indices = jnp.arange(bins)[:, None]
    left = jnp.maximum((indices - points[:-2]) / (points[1:-1] - points[:-2]), 0)
    right = jnp.maximum((points[2:] - indices) / (points[2:] - points[1:-1]), 0)
    return jnp.minimum(left, right).T

def apply_filterbank(spectrum, filters):
    return jnp.einsum('...f,bf->...b', spectrum, filters)

def adjacency_normalize(adjacency, add_self_loops=True):
    if add_self_loops:
        adjacency = adjacency + jnp.eye(adjacency.shape[-1])
    degree = jnp.sum(adjacency, axis=-1)
    inv_sqrt = jnp.rsqrt(jnp.maximum(degree, 1e-8))
    return inv_sqrt[..., :, None] * adjacency * inv_sqrt[..., None, :]

def graph_laplacian(adjacency, normalized=True):
    if normalized:
        return jnp.eye(adjacency.shape[-1]) - adjacency_normalize(adjacency)
    degree = jnp.sum(adjacency, axis=-1)
    return jnp.diag(degree) - adjacency

def graph_degree(adjacency, axis=-1):
    return jnp.sum(adjacency, axis=axis)

def graph_density(adjacency):
    nodes = adjacency.shape[-1]
    return jnp.sum(adjacency) / max(nodes * (nodes - 1), 1)

def graph_symmetrize(adjacency):
    return 0.5 * (adjacency + jnp.swapaxes(adjacency, -1, -2))

def graph_remove_self_loops(adjacency):
    eye = jnp.eye(adjacency.shape[-1])
    return adjacency * (1 - eye)

def graph_k_hop(adjacency, k):
    result = jnp.eye(adjacency.shape[-1])
    power = result
    for _ in range(k):
        power = power @ adjacency
        result = jnp.minimum(result + power, 1)
    return result

def scatter_add(values, indices, size):
    output = jnp.zeros((size,) + values.shape[1:], dtype=values.dtype)
    return output.at[indices].add(values)

def segment_mean(values, segment_ids, segments):
    sums = scatter_add(values, segment_ids, segments)
    counts = scatter_add(jnp.ones((values.shape[0],)), segment_ids, segments)
    return safe_divide(sums, counts.reshape((-1,) + (1,) * (values.ndim - 1)))

def segment_sum(values, segment_ids, segments):
    return scatter_add(values, segment_ids, segments)

def gather_nodes(nodes, indices):
    return jnp.take(nodes, indices, axis=-2)

def pairwise_edges(nodes):
    left = jnp.repeat(nodes, nodes.shape[-2], axis=-2)
    right = jnp.tile(nodes, (1, nodes.shape[-2], 1))
    return jnp.concatenate([left, right], axis=-1)

def graph_pool_sum(nodes, mask=None):
    return jnp.sum(nodes if mask is None else nodes * mask[..., None], axis=-2)

def graph_pool_mean(nodes, mask=None):
    if mask is None:
        return jnp.mean(nodes, axis=-2)
    return safe_divide(graph_pool_sum(nodes, mask), jnp.sum(mask, axis=-1, keepdims=True))

def graph_pool_max(nodes, mask=None):
    if mask is not None:
        nodes = jnp.where(mask[..., None], nodes, -jnp.inf)
    return jnp.max(nodes, axis=-2)

def tree_map(fn, tree):
    return jax.tree_util.tree_map(fn, tree)

def tree_add(left, right):
    return tree_map(lambda a, b: a + b, (left, right))

def tree_scale(tree, scalar):
    return tree_map(lambda value: scalar * value, tree)

def tree_zeros_like(tree):
    return tree_map(jnp.zeros_like, tree)

def tree_sum(trees):
    trees = list(trees)
    if not trees:
        raise ValueError('tree_sum needs at least one tree')
    result = trees[0]
    for tree in trees[1:]:
        result = tree_add(result, tree)
    return result

def tree_mean(trees):
    return tree_scale(tree_sum(trees), 1 / len(trees))

def tree_norm(tree):
    return jnp.sqrt(sum(jnp.sum(jnp.square(leaf)) for leaf in jax.tree_util.tree_leaves(tree)) + 1e-12)

def tree_max_abs(tree):
    return jnp.max(jnp.asarray([jnp.max(jnp.abs(leaf)) for leaf in jax.tree_util.tree_leaves(tree)]))

def tree_count(tree):
    return sum(leaf.size for leaf in jax.tree_util.tree_leaves(tree))

def tree_cast(tree, dtype):
    return tree_map(lambda value: value.astype(dtype), tree)

def assert_shape(value, expected):
    if tuple(value.shape) != tuple(expected):
        raise ValueError(f'expected shape {expected}, got {value.shape}')
    return value

def assert_finite(value, name='value'):
    if not bool(jnp.all(jnp.isfinite(value))):
        raise FloatingPointError(f'{name} contains non-finite values')
    return value

def assert_probability(value, name='probability'):
    if not bool(jnp.all((value >= 0) & (value <= 1))):
        raise ValueError(f'{name} is outside [0, 1]')
    return value

def check_same_batch(*values):
    sizes = {value.shape[0] for value in values}
    if len(sizes) != 1:
        raise ValueError(f'inconsistent batch sizes: {sizes}')
    return next(iter(sizes))

def batch_indices(size, batch_size, drop_remainder=True):
    count = size // batch_size if drop_remainder else math.ceil(size / batch_size)
    return [slice(i * batch_size, min((i + 1) * batch_size, size)) for i in range(count)]

def gather_batch(value, indices):
    return value[indices]

def permute_batch(key, batch):
    permutation = random.permutation(key, batch.shape[0])
    return batch[permutation], permutation

def repeat_batch(value, repeats):
    return jnp.repeat(value, repeats, axis=0)

def tile_batch(value, repeats):
    return jnp.tile(value, (repeats,) + (1,) * (value.ndim - 1))

def concat_batches(values, axis=0):
    return jnp.concatenate(tuple(values), axis=axis)

def stack_batches(values, axis=0):
    return jnp.stack(tuple(values), axis=axis)

def split_batch(value, sections, axis=0):
    return tuple(jnp.array_split(value, sections, axis=axis))

def repeat_key(key, count):
    return random.split(key, count)

def fold_in_key(key, data):
    return random.fold_in(key, data)

def deterministic_seed(seed, stream=0):
    return random.PRNGKey(seed).fold_in(stream) if hasattr(random.PRNGKey(seed), 'fold_in') else random.fold_in(random.PRNGKey(seed), stream)
