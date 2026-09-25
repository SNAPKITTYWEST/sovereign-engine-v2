from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Tuple
import json

@dataclass
class HarnessConfig:
    seed: int = 7
    batch_size: int = 8
    seq_len: int = 32
    d_model: int = 64
    num_heads: int = 4
    num_layers: int = 2
    vocab_size: int = 128
    num_classes: int = 8
    graph_nodes: int = 16
    audio_samples: int = 256
    image_size: int = 16
    learning_rate: float = 2e-3
    weight_decay: float = 1e-4
    warmup_steps: int = 10
    max_grad_norm: float = 1.0
    dropout_rate: float = 0.0
    modality_weights: Dict[str, float] = field(default_factory=lambda: {
        "formal": 1.0, "rl": 1.0, "graph": 1.0, "tabular": 1.0,
        "timeseries": 1.0, "visual": 1.0, "audio": 1.0,
    })

    def validate(self) -> None:
        if self.d_model % self.num_heads:
            raise ValueError("d_model must be divisible by num_heads")
        if self.batch_size < 1 or self.seq_len < 1:
            raise ValueError("batch_size and seq_len must be positive")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if not 0 <= self.dropout_rate < 1:
            raise ValueError("dropout_rate must be in [0, 1)")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, values: Dict[str, Any]) -> "HarnessConfig":
        cfg = cls(**values)
        cfg.validate()
        return cfg
