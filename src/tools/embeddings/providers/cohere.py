"""
Cohere Embeddings Provider
Part of SOVEREIGN PYTHON LLM ENGINE
"""

import numpy as np
import boto3
import json


class CohereEmbeddings:
    """
    Cohere embeddings via AWS Bedrock.
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Cohere embeddings.

        Args:
            region: AWS region
        """
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)

    async def encode(
        self,
        text: str,
        model: str = "embed-english-v3.0",
        input_type: str = "search_document"
    ) -> np.ndarray:
        """
        Encode single text to embedding.

        Args:
            text: Input text
            model: Model name
            input_type: "search_query" or "search_document" or "classification"

        Returns:
            Embedding vector
        """
        import asyncio

        # Map to Bedrock model ID
        bedrock_model_id = "cohere.embed-english-v3"

        # Prepare request
        request_body = {
            "texts": [text],
            "input_type": input_type
        }

        # Call Bedrock
        response = await asyncio.to_thread(
            self.bedrock.invoke_model,
            modelId=bedrock_model_id,
            body=json.dumps(request_body)
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        embedding = np.array(response_body['embeddings'][0])

        return embedding

    async def encode_batch(
        self,
        texts: list[str],
        model: str = "embed-english-v3.0",
        input_type: str = "search_document"
    ) -> list[np.ndarray]:
        """
        Encode multiple texts to embeddings (batched).

        Args:
            texts: List of input texts
            model: Model name
            input_type: Input type

        Returns:
            List of embedding vectors
        """
        import asyncio

        # Cohere supports batch encoding natively
        bedrock_model_id = "cohere.embed-english-v3"

        # Prepare request
        request_body = {
            "texts": texts,
            "input_type": input_type
        }

        # Call Bedrock
        response = await asyncio.to_thread(
            self.bedrock.invoke_model,
            modelId=bedrock_model_id,
            body=json.dumps(request_body)
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        embeddings = [np.array(emb) for emb in response_body['embeddings']]

        return embeddings
