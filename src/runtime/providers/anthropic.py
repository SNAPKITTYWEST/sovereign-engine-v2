"""
Anthropic Provider Adapter
Part of SOVEREIGN PYTHON LLM ENGINE

Per user memory: Routes through AWS Bedrock (not direct API).
"""

import boto3
import json
from typing import Any, AsyncIterator


class AnthropicProvider:
    """
    Anthropic/Claude via AWS Bedrock.

    Supports:
    - Messages API
    - Tool use
    - Streaming
    - Vision
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Anthropic provider via Bedrock.

        Args:
            region: AWS region
        """
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)

    async def messages_create(
        self,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        system: str | None = None
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """
        Create message with Anthropic API via Bedrock.

        Args:
            model: Model ID (e.g., "claude-3-5-sonnet-20241022-v2:0")
            messages: Conversation history
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            tools: Tool definitions (optional)
            stream: Whether to stream response
            system: System prompt (optional)

        Returns:
            Response dict or AsyncIterator if streaming
        """
        import asyncio

        # Map model name to Bedrock model ID
        bedrock_model_id = self._map_model_id(model)

        # Build request body
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if system:
            request_body["system"] = system

        if tools:
            request_body["tools"] = tools

        # Call Bedrock
        if stream:
            return self._stream_response(bedrock_model_id, request_body)
        else:
            response = await asyncio.to_thread(
                self.bedrock.invoke_model,
                modelId=bedrock_model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            return response_body

    async def _stream_response(
        self,
        model_id: str,
        request_body: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream response from Bedrock"""
        import asyncio

        response = await asyncio.to_thread(
            self.bedrock.invoke_model_with_response_stream,
            modelId=model_id,
            body=json.dumps(request_body)
        )

        for event in response['body']:
            chunk = json.loads(event['chunk']['bytes'])
            yield chunk

    def _map_model_id(self, model: str) -> str:
        """
        Map model name to Bedrock model ID.

        Args:
            model: Model name

        Returns:
            Bedrock model ID
        """
        # Map common names to Bedrock IDs
        model_map = {
            "sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "opus": "anthropic.claude-3-opus-20240229-v1:0",
            "haiku": "anthropic.claude-3-haiku-20240307-v1:0"
        }

        if model in model_map:
            return model_map[model]

        # If already a Bedrock ID, return as-is
        if "anthropic.claude" in model:
            return model

        # Default to Sonnet
        return model_map["sonnet"]
