"""
Embedding Encoding Tools
Part of SOVEREIGN PYTHON LLM ENGINE

Core embedding operations with provider abstraction.
"""

import numpy as np
from typing import Any
import asyncio

from ..registry import tool, RiskClass, ApprovalPolicy


# ==========================================
# Core Tools
# ==========================================

@tool(
    tool_id="embeddings.encode_text",
    version="1.0.0",
    title="Encode Text to Embedding",
    description="Convert text to embedding vector using specified model",
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "model": {"type": "string", "default": "text-embedding-3-small"},
            "provider": {"type": "string", "enum": ["openai", "cohere", "local"], "default": "openai"}
        },
        "required": ["text"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "embedding": {"type": "array", "items": {"type": "number"}},
            "dimension": {"type": "integer"},
            "model": {"type": "string"}
        }
    },
    risk_class=RiskClass.READ_ONLY_REMOTE,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["embeddings", "vector", "rag"]
)
async def encode_text(params: dict[str, Any]) -> dict[str, Any]:
    """
    Encode single text to embedding vector.

    Args:
        params: {text, model, provider}

    Returns:
        {embedding, dimension, model}
    """
    text = params['text']
    model = params.get('model', 'text-embedding-3-small')
    provider = params.get('provider', 'openai')

    # Get provider implementation
    if provider == 'openai':
        from .providers.openai import OpenAIEmbeddings
        provider_impl = OpenAIEmbeddings()
    elif provider == 'cohere':
        from .providers.cohere import CohereEmbeddings
        provider_impl = CohereEmbeddings()
    elif provider == 'local':
        from .providers.local import LocalEmbeddings
        provider_impl = LocalEmbeddings(model_name=model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Encode
    embedding = await provider_impl.encode(text, model=model)

    return {
        'embedding': embedding.tolist(),
        'dimension': len(embedding),
        'model': model
    }


@tool(
    tool_id="embeddings.encode_batch",
    version="1.0.0",
    title="Encode Batch of Texts",
    description="Convert multiple texts to embeddings (batched for efficiency)",
    input_schema={
        "type": "object",
        "properties": {
            "texts": {"type": "array", "items": {"type": "string"}},
            "model": {"type": "string", "default": "text-embedding-3-small"},
            "provider": {"type": "string", "enum": ["openai", "cohere", "local"], "default": "openai"}
        },
        "required": ["texts"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "embeddings": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
            "dimension": {"type": "integer"},
            "count": {"type": "integer"},
            "model": {"type": "string"}
        }
    },
    risk_class=RiskClass.READ_ONLY_REMOTE,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["embeddings", "vector", "rag", "batch"]
)
async def encode_batch(params: dict[str, Any]) -> dict[str, Any]:
    """
    Encode multiple texts to embeddings.

    Args:
        params: {texts, model, provider}

    Returns:
        {embeddings, dimension, count, model}
    """
    texts = params['texts']
    model = params.get('model', 'text-embedding-3-small')
    provider = params.get('provider', 'openai')

    # Get provider implementation
    if provider == 'openai':
        from .providers.openai import OpenAIEmbeddings
        provider_impl = OpenAIEmbeddings()
    elif provider == 'cohere':
        from .providers.cohere import CohereEmbeddings
        provider_impl = CohereEmbeddings()
    elif provider == 'local':
        from .providers.local import LocalEmbeddings
        provider_impl = LocalEmbeddings(model_name=model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Encode batch
    embeddings = await provider_impl.encode_batch(texts, model=model)

    return {
        'embeddings': [emb.tolist() for emb in embeddings],
        'dimension': len(embeddings[0]) if embeddings else 0,
        'count': len(embeddings),
        'model': model
    }


@tool(
    tool_id="embeddings.similarity",
    version="1.0.0",
    title="Compute Cosine Similarity",
    description="Compute cosine similarity between two embedding vectors",
    input_schema={
        "type": "object",
        "properties": {
            "embedding1": {"type": "array", "items": {"type": "number"}},
            "embedding2": {"type": "array", "items": {"type": "number"}}
        },
        "required": ["embedding1", "embedding2"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "similarity": {"type": "number"}
        }
    },
    risk_class=RiskClass.PURE_COMPUTATION,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["embeddings", "similarity", "vector"]
)
async def similarity(params: dict[str, Any]) -> dict[str, Any]:
    """
    Compute cosine similarity between two vectors.

    Args:
        params: {embedding1, embedding2}

    Returns:
        {similarity}
    """
    emb1 = np.array(params['embedding1'])
    emb2 = np.array(params['embedding2'])

    # Cosine similarity
    dot_product = np.dot(emb1, emb2)
    norm1 = np.linalg.norm(emb1)
    norm2 = np.linalg.norm(emb2)

    if norm1 == 0 or norm2 == 0:
        return {'similarity': 0.0}

    sim = float(dot_product / (norm1 * norm2))

    return {'similarity': sim}


@tool(
    tool_id="embeddings.normalize",
    version="1.0.0",
    title="Normalize Embedding Vector",
    description="L2 normalize embedding vector",
    input_schema={
        "type": "object",
        "properties": {
            "embedding": {"type": "array", "items": {"type": "number"}}
        },
        "required": ["embedding"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "normalized": {"type": "array", "items": {"type": "number"}}
        }
    },
    risk_class=RiskClass.PURE_COMPUTATION,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["embeddings", "normalization", "vector"]
)
async def normalize(params: dict[str, Any]) -> dict[str, Any]:
    """
    L2 normalize embedding vector.

    Args:
        params: {embedding}

    Returns:
        {normalized}
    """
    emb = np.array(params['embedding'])
    norm = np.linalg.norm(emb)

    if norm == 0:
        return {'normalized': emb.tolist()}

    normalized = emb / norm

    return {'normalized': normalized.tolist()}
