from typing import Dict
import jax
import jax.numpy as jnp
from .config import HarnessConfig
from .data.pipeline import SyntheticDataModule, causal_mask
from .data.generators import make_all_modalities
from .models.attention import embedding, init_transformer, transformer, init_linear, linear
from .models.encoders import init_mlp, mlp, mean_pool, init_graph_encoder, graph_message_passing, image_patchify, audio_stft_features
from .algorithms.losses import cross_entropy, mse, binary_cross_entropy
from .algorithms.constraints import polynomial_residual, equality_penalty
from .algorithms.optim import AdamW
from .algorithms.trainer import Trainer


def init_params(key, cfg):
    keys = jax.random.split(key, 9)
    return {
        'token_embedding': embedding(keys[0], cfg.vocab_size, cfg.d_model),
        'transformer': init_transformer(keys[1], cfg.d_model, cfg.num_heads, cfg.num_layers),
        'formal_head': init_linear(keys[2], cfg.d_model, cfg.vocab_size),
        'tabular': init_mlp(keys[3], [12, cfg.d_model, cfg.d_model]),
        'graph': init_graph_encoder(keys[4], 16, cfg.d_model),
        'graph_head': init_linear(keys[5], cfg.d_model, 2),
        'visual': init_mlp(keys[6], [4 * 4 * 3, cfg.d_model, cfg.d_model]),
        'audio': init_mlp(keys[7], [17, cfg.d_model, cfg.d_model]),
        'fusion_head': init_linear(keys[8], cfg.d_model, cfg.num_classes),
    }


def model_loss(params, batch, cfg):
    formal_tokens, formal_mask, formal_labels, formal_features = batch['formal']
    x = jnp.take(params['token_embedding'], formal_tokens, axis=0)
    x = transformer(params['transformer'], x, causal_mask(x.shape[1]))
    formal_logits = linear(params['formal_head'], x[:, 0])
    formal_loss = cross_entropy(formal_logits, formal_labels)
    formal_acc = jnp.mean(jnp.argmax(formal_logits, -1) == formal_labels)

    tab_x, tab_y = batch['tabular']
    tab_emb = mean_pool(mlp(params['tabular'], tab_x)[:, None, :])
    tab_logits = linear(params['fusion_head'], tab_emb)
    tab_loss = cross_entropy(tab_logits, tab_y)

    nodes, adjacency, graph_y = batch['graph']
    graph_nodes = graph_message_passing(params['graph'], nodes, adjacency)
    graph_emb = mean_pool(graph_nodes)
    graph_logits = linear(params['graph_head'], graph_emb)
    graph_loss = cross_entropy(graph_logits, graph_y)

    images, image_y, _ = batch['visual']
    patches = image_patchify(images)
    visual_emb = mean_pool(mlp(params['visual'], patches))
    visual_logits = linear(params['fusion_head'], visual_emb)
    visual_loss = cross_entropy(visual_logits, image_y)

    audio, audio_y = batch['audio']
    audio_features = audio_stft_features(audio)
    audio_emb = jnp.mean(mlp(params['audio'], audio_features), axis=(1, 2))
    audio_logits = linear(params['fusion_head'], audio_emb)
    audio_loss = cross_entropy(audio_logits, audio_y)

    x_alg, coeff, target = batch['algebraic']
    residual = polynomial_residual(x_alg, coeff) - target
    constraint_error = equality_penalty(residual)
    total = formal_loss + tab_loss + graph_loss + visual_loss + audio_loss + 0.1 * constraint_error
    return total, {'accuracy': formal_acc, 'constraint_error': constraint_error, 'reward': 0.0}


def build_trainer(cfg):
    cfg.validate()
    params = init_params(jax.random.PRNGKey(cfg.seed), cfg)
    optimizer = AdamW(cfg.learning_rate, cfg.weight_decay, max_grad_norm=cfg.max_grad_norm)
    return Trainer(params, optimizer, lambda p, b: model_loss(p, b, cfg), cfg)


def run_experiment(cfg, steps=10, log_every=1):
    trainer = build_trainer(cfg)
    data = SyntheticDataModule(cfg, cfg.seed)
    history = trainer.train(data.epoch_batches(steps), steps, log_every)
    return trainer, history
