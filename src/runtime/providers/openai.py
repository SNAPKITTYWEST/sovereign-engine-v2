"""
OpenAI Provider Adapter
Part of SOVEREIGN PYTHON LLM ENGINE

Note: Per user memory, routes through Bedrock, not direct OpenAI API.
"""

import boto3
import json
from typing import Any, AsyncIterator


class OpenAIProvider:
    """
    OpenAI API compatibility via Bedrock or direct API.

    For now, implements direct API. User can override to use Bedrock.
    """

    def __init__(self, api_key: str | None = None, via_bedrock: bool = False, region: str = "us-east-1"):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (not used if via_bedrock=True)
            via_bedrock: Route through Bedrock instead
            region: AWS region (if via_bedrock=True)
        """
        self.via_bedrock = via_bedrock

        if via_bedrock:
            self.bedrock = boto3.client("bedrock-runtime", region_name=region)
        else:
            import os
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    async def chat_completions_create(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        stream: bool = False,
        temperature: float = 1.0,
        max_tokens: int | None = None,
        **kwargs
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        """
        Create chat completion (OpenAI API compatible).

        Args:
            model: Model name
            messages: Conversation history
            tools: Tool definitions
            response_format: Structured output schema
            stream: Stream response
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Returns:
            Response dict or AsyncIterator if streaming
        """
        if self.via_bedrock:
            return await self._bedrock_completion(model, messages, tools, stream, temperature, max_tokens, **kwargs)
        else:
            return await self._direct_completion(model, messages, tools, response_format, stream, temperature, max_tokens, **kwargs)

    async def _direct_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        response_format: dict[str, Any] | None,
        stream: bool,
        temperature: float,
        max_tokens: int | None,
        **kwargs
    ) -> dict[str, Any]:
        """Direct OpenAI API call"""
        import httpx

        request_body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }

        if max_tokens:
            request_body["max_tokens"] = max_tokens

        if tools:
            request_body["tools"] = tools

        if response_format:
            request_body["response_format"] = response_format

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request_body
            )

            return response.json()

    async def _bedrock_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        stream: bool,
        temperature: float,
        max_tokens: int | None,
        **kwargs
    ) -> dict[str, Any]:
        """Route through Bedrock"""
        # Map OpenAI model to Bedrock equivalent
        # For now, use Anthropic Claude as default
        bedrock_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature
        }

        if tools:
            request_body["tools"] = tools

        import asyncio

        response = await asyncio.to_thread(
            self.bedrock.invoke_model,
            modelId=bedrock_model_id,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        return response_body
