from typing import Tuple
import math
import jax.numpy as jnp
from jax import random, nn


def glorot(key, shape):
    fan_in, fan_out = shape[-2], shape[-1]
    limit = math.sqrt(6 / (fan_in + fan_out))
    return random.uniform(key, shape, minval=-limit, maxval=limit)


def init_linear(key, in_dim, out_dim):
    k1, k2 = random.split(key)
    return {'w': glorot(k1, (in_dim, out_dim)), 'b': jnp.zeros((out_dim,))}


def linear(params, x):
    return jnp.einsum('...i,ij->...j', x, params['w']) + params['b']


def init_mha(key, d_model, num_heads):
    keys = random.split(key, 4)
    if num_heads != 4:
        raise ValueError('this compact harness uses four static attention heads')
    return {'q': init_linear(keys[0], d_model, d_model),
            'k': init_linear(keys[1], d_model, d_model),
            'v': init_linear(keys[2], d_model, d_model),
            'o': init_linear(keys[3], d_model, d_model)}


def split_heads(x, heads):
    b, t, d = x.shape
    return x.reshape(b, t, heads, d // heads).transpose(0, 2, 1, 3)


def merge_heads(x):
    b, h, t, d = x.shape
    return x.transpose(0, 2, 1, 3).reshape(b, t, h * d)


def fast_batched_attention(params, x, causal_mask=None, key_mask=None):
    heads = 4
    q = split_heads(linear(params['q'], x), heads)
    k = split_heads(linear(params['k'], x), heads)
    v = split_heads(linear(params['v'], x), heads)
    scores = jnp.einsum('bhid,bhjd->bhij', q, k) / math.sqrt(q.shape[-1])
    if causal_mask is not None:
        scores = scores + causal_mask[None, None, :, :]
    if key_mask is not None:
        scores = scores + (1 - key_mask[:, None, None, :]) * -1e9
    weights = nn.softmax(scores, axis=-1)
    return linear(params['o'], merge_heads(jnp.einsum('bhij,bhjd->bhid', weights, v)))


def transformer_block(params, x, mask=None):
    attended = fast_batched_attention(params['attention'], x, mask)
    x = x + attended
    x = x + linear(params['ff1'], nn.gelu(linear(params['ff0'], x)))
    return x


def init_transformer(key, d_model, heads, layers, ff_mult=4):
    keys = random.split(key, layers * 3 + 1)
    blocks = []
    index = 0
    for _ in range(layers):
        blocks.append({'attention': init_mha(keys[index], d_model, heads),
                       'ff0': init_linear(keys[index + 1], d_model, d_model * ff_mult),
                       'ff1': init_linear(keys[index + 2], d_model * ff_mult, d_model)})
        index += 3
    return {'blocks': blocks, 'token': init_linear(d_model, d_model) if False else None}


def transformer(params, x, mask=None):
    for block in params['blocks']:
        x = transformer_block(block, x, mask)
    return x


def embedding(key, vocab, d_model):
    return random.normal(key, (vocab, d_model)) * (1 / math.sqrt(d_model))


def embed_tokens(table, token_ids):
    return table[token_ids]
