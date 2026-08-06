"""
Embeddings Namespace
Part of SOVEREIGN PYTHON LLM ENGINE

Text embedding tools with multiple provider support.
"""

from .encode import (
    encode_text,
    encode_batch,
    similarity,
    normalize
)

__all__ = [
    'encode_text',
    'encode_batch',
    'similarity',
    'normalize'
]
