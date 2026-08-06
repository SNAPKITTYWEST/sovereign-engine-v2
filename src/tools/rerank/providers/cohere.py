"""
Cohere Reranker Provider
Part of SOVEREIGN PYTHON LLM ENGINE
"""

import boto3
import json
from typing import Any


class CohereReranker:
    """
    Cohere reranking via AWS Bedrock.
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Cohere reranker.

        Args:
            region: AWS region
        """
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
        model: str = "rerank-english-v3.0"
    ) -> list[dict[str, Any]]:
        """
        Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of documents to rerank
            top_k: Number of documents to return
            model: Model name

        Returns:
            List of {document, score, index} sorted by relevance
        """
        import asyncio

        # Map to Bedrock model ID
        bedrock_model_id = "cohere.rerank-v3-5:0"

        # Prepare request
        request_body = {
            "query": query,
            "documents": documents,
            "top_n": min(top_k, len(documents))
        }

        # Call Bedrock
        response = await asyncio.to_thread(
            self.bedrock.invoke_model,
            modelId=bedrock_model_id,
            body=json.dumps(request_body)
        )

        # Parse response
        response_body = json.loads(response['body'].read())

        # Extract results
        results = []
        for result in response_body.get('results', []):
            results.append({
                'document': documents[result['index']],
                'score': result['relevance_score'],
                'index': result['index']
            })

        return results

    async def score(self, query: str, document: str, model: str = "rerank-english-v3.0") -> float:
        """
        Compute relevance score for single document.

        Args:
            query: Search query
            document: Document to score
            model: Model name

        Returns:
            Relevance score
        """
        results = await self.rerank(query, [document], top_k=1, model=model)
        return results[0]['score'] if results else 0.0
