"""
Reranking Tools
Part of SOVEREIGN PYTHON LLM ENGINE
"""

from typing import Any

from ..registry import tool, RiskClass, ApprovalPolicy


@tool(
    tool_id="rerank.documents",
    version="1.0.0",
    title="Rerank Documents",
    description="Rerank documents by relevance to query using cross-encoder model",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "documents": {"type": "array", "items": {"type": "string"}},
            "top_k": {"type": "integer", "default": 5},
            "model": {"type": "string", "default": "rerank-english-v3.0"},
            "provider": {"type": "string", "enum": ["cohere"], "default": "cohere"}
        },
        "required": ["query", "documents"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "ranked_documents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "document": {"type": "string"},
                        "score": {"type": "number"},
                        "index": {"type": "integer"}
                    }
                }
            },
            "model": {"type": "string"}
        }
    },
    risk_class=RiskClass.READ_ONLY_REMOTE,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["rerank", "rag", "retrieval"]
)
async def rerank_documents(params: dict[str, Any]) -> dict[str, Any]:
    """
    Rerank documents by relevance to query.

    Args:
        params: {query, documents, top_k, model, provider}

    Returns:
        {ranked_documents, model}
    """
    query = params['query']
    documents = params['documents']
    top_k = params.get('top_k', 5)
    model = params.get('model', 'rerank-english-v3.0')
    provider = params.get('provider', 'cohere')

    # Get provider implementation
    if provider == 'cohere':
        from .providers.cohere import CohereReranker
        provider_impl = CohereReranker()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Rerank
    ranked = await provider_impl.rerank(
        query=query,
        documents=documents,
        top_k=top_k,
        model=model
    )

    return {
        'ranked_documents': ranked,
        'model': model
    }


@tool(
    tool_id="rerank.score",
    version="1.0.0",
    title="Score Document Relevance",
    description="Compute relevance score for single document given query",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "document": {"type": "string"},
            "model": {"type": "string", "default": "rerank-english-v3.0"},
            "provider": {"type": "string", "enum": ["cohere"], "default": "cohere"}
        },
        "required": ["query", "document"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "score": {"type": "number"},
            "model": {"type": "string"}
        }
    },
    risk_class=RiskClass.READ_ONLY_REMOTE,
    approval_policy=ApprovalPolicy.AUTOMATIC,
    tags=["rerank", "rag", "relevance"]
)
async def score_document(params: dict[str, Any]) -> dict[str, Any]:
    """
    Compute relevance score for document.

    Args:
        params: {query, document, model, provider}

    Returns:
        {score, model}
    """
    query = params['query']
    document = params['document']
    model = params.get('model', 'rerank-english-v3.0')
    provider = params.get('provider', 'cohere')

    # Get provider implementation
    if provider == 'cohere':
        from .providers.cohere import CohereReranker
        provider_impl = CohereReranker()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Score single document
    ranked = await provider_impl.rerank(
        query=query,
        documents=[document],
        top_k=1,
        model=model
    )

    score = ranked[0]['score'] if ranked else 0.0

    return {
        'score': score,
        'model': model
    }
