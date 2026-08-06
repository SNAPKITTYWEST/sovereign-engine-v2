"""
OpenAI Embeddings Provider
Part of SOVEREIGN PYTHON LLM ENGINE
"""

import numpy as np
import os
import boto3
import json
from typing import Any


class OpenAIEmbeddings:
    """
    OpenAI embeddings via AWS Bedrock.

    Per user's memory: ALL model inference routes through AWS Bedrock.
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize OpenAI embeddings via Bedrock.

        Args:
            region: AWS region
        """
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)

    async def encode(self, text: str, model: str = "text-embedding-3-small") -> np.ndarray:
        """
        Encode single text to embedding.

        Args:
            text: Input text
            model: Model name

        Returns:
            Embedding vector (numpy array)
        """
        import asyncio

        # Map to Bedrock model ID
        bedrock_model_id = self._map_model_id(model)

        # Prepare request
        request_body = {
            "inputText": text
        }

        # Call Bedrock (sync, so run in thread pool)
        response = await asyncio.to_thread(
            self.bedrock.invoke_model,
            modelId=bedrock_model_id,
            body=json.dumps(request_body)
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        embedding = np.array(response_body['embedding'])

        return embedding

    async def encode_batch(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small"
    ) -> list[np.ndarray]:
        """
        Encode multiple texts to embeddings.

        Args:
            texts: List of input texts
            model: Model name

        Returns:
            List of embedding vectors
        """
        import asyncio

        # Encode concurrently
        tasks = [self.encode(text, model) for text in texts]
        embeddings = await asyncio.gather(*tasks)

        return embeddings

    def _map_model_id(self, model: str) -> str:
        """
        Map OpenAI model name to Bedrock model ID.

        Args:
            model: OpenAI model name

        Returns:
            Bedrock model ID
        """
        # For actual deployment, map to real Bedrock embedding models
        # For now, return Amazon Titan embedding model
        if "text-embedding" in model:
            return "amazon.titan-embed-text-v1"

        return "amazon.titan-embed-text-v1"
