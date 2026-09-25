import jax
import jax.numpy as jnp
from jax import random
from jax_harness.config import HarnessConfig
from jax_harness.data.generators import make_all_modalities
from jax_harness.data.pipeline import causal_mask
from jax_harness.models.attention import init_mha, fast_batched_attention
from jax_harness.algorithms.constraints import project_simplex, polynomial_residual
from jax_harness.algorithms.replay import ReplayBuffer
from jax_harness.experiment import build_trainer


def test_attention_shape_and_causal_mask():
    params = init_mha(random.PRNGKey(0), 32, 4)
    x = jnp.ones((3, 7, 32))
    out = fast_batched_attention(params, x, causal_mask(7))
    assert out.shape == x.shape


def test_modalities_are_deterministic():
    cfg = HarnessConfig(batch_size=2, seq_len=8, d_model=32, num_heads=4)
    first = make_all_modalities(random.PRNGKey(4), cfg)
    second = make_all_modalities(random.PRNGKey(4), cfg)
    assert jnp.array_equal(first['formal'][0], second['formal'][0])
    assert jnp.array_equal(first['graph'][1], second['graph'][1])


def test_simplex_projection():
    projected = project_simplex(jnp.array([[1.0, -1.0, 2.0]]))
    assert jnp.all(projected >= 0)
    assert jnp.allclose(jnp.sum(projected), 1.0)


def test_replay_buffer():
    buffer = ReplayBuffer(4, (2,), seed=1)
    for i in range(4):
        buffer.add(jnp.ones(2) * i, i, 1.0, jnp.ones(2) * (i + 1), False)
    sample = buffer.sample(2)
    assert sample['states'].shape == (2, 2)


def test_end_to_end_update():
    cfg = HarnessConfig(batch_size=2, seq_len=8, d_model=32, num_heads=4, graph_nodes=4, image_size=8, audio_samples=64)
    trainer = build_trainer(cfg)
    batch = next(iter(__import__('jax_harness.data.pipeline', fromlist=['SyntheticDataModule']).SyntheticDataModule(cfg, cfg.seed)))
    metrics = trainer.train_step(batch)
    assert jnp.isfinite(metrics.loss)
    assert int(trainer.state.step) == 1
