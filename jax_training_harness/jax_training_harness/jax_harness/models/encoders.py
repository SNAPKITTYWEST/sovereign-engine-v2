import jax.numpy as jnp
from jax import nn
from .attention import init_linear, linear, glorot
from jax import random


def init_mlp(key, dims):
    keys = random.split(key, len(dims) - 1)
    return [init_linear(k, a, b) for k, (a, b) in zip(keys, zip(dims[:-1], dims[1:]))]


def mlp(params, x, activation=nn.gelu):
    for layer in params[:-1]:
        x = activation(linear(layer, x))
    return linear(params[-1], x)


def mean_pool(x, mask=None):
    if mask is None:
        return jnp.mean(x, axis=-2)
    weights = mask[..., None]
    return jnp.sum(x * weights, axis=-2) / (jnp.sum(weights, axis=-2) + 1e-6)


def init_graph_encoder(key, node_dim, hidden, layers=3):
    dims = [node_dim] + [hidden] * layers
    return init_mlp(key, dims)


def graph_message_passing(params, nodes, adjacency):
    degree = jnp.sum(adjacency, axis=-1, keepdims=True) + 1.0
    for layer in params:
        neighbors = jnp.einsum('bij,bjd->bid', adjacency, nodes) / degree
        nodes = nn.gelu(linear(layer, nodes + neighbors))
    return nodes


def init_signal_encoder(key, input_dim, hidden, output_dim):
    return init_mlp(key, [input_dim, hidden, hidden, output_dim])


def signal_encoder(params, x):
    return mlp(params, x, nn.silu)


def image_patchify(images, patch=4):
    b, h, w, c = images.shape
    assert h % patch == 0 and w % patch == 0
    return images.reshape(b, h // patch, patch, w // patch, patch, c).transpose(0, 1, 3, 2, 4, 5).reshape(b, -1, patch * patch * c)


def audio_stft_features(waveform, frame=32, hop=16):
    b, samples, channels = waveform.shape
    starts = range(0, samples - frame + 1, hop)
    frames = jnp.stack([waveform[:, s:s + frame, :] for s in starts], axis=1)
    window = jnp.hanning(frame)[None, None, :, None]
    spectrum = jnp.fft.rfft(frames * window, axis=2)
    return jnp.log1p(jnp.abs(spectrum))


def init_residual_1d(key, channels, hidden):
    keys = random.split(key, 4)
    return {'in': init_linear(keys[0], channels, hidden), 'mid': init_linear(keys[1], hidden, hidden),
            'out': init_linear(keys[2], hidden, channels), 'gate': init_linear(keys[3], channels, hidden)}


def residual_1d(params, x):
    h = nn.silu(linear(params['in'], x))
    h = nn.silu(linear(params['mid'], h))
    gate = nn.sigmoid(linear(params['gate'], x))
    return x + gate * linear(params['out'], h)
