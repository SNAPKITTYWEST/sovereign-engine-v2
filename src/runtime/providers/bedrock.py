"""
AWS Bedrock Provider Adapter
Part of SOVEREIGN PYTHON LLM ENGINE

Unified interface for all Bedrock models (Claude, Llama, Mistral, etc.)
"""

import boto3
import json
from typing import Any, AsyncIterator


class BedrockProvider:
    """
    AWS Bedrock unified provider.

    Supports all Bedrock models with automatic format conversion.
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Bedrock provider.

        Args:
            region: AWS region
        """
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)

    async def invoke_model(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs
    ) -> dict[str, Any]:
        """
        Invoke model via Bedrock.

        Args:
            model_id: Bedrock model ID
            messages: Conversation history
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            **kwargs: Additional model-specific parameters

        Returns:
            Model response
        """
        import asyncio

        # Convert to provider-specific format
        request_body = self._format_request(model_id, messages, max_tokens, temperature, **kwargs)

        # Invoke model
        response = await asyncio.to_thread(
            self.bedrock.invoke_model,
            modelId=model_id,
            body=json.dumps(request_body)
        )

        # Parse response
        response_body = json.loads(response['body'].read())

        # Convert to standard format
        return self._format_response(model_id, response_body)

    async def invoke_model_stream(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream model response"""
        import asyncio

        request_body = self._format_request(model_id, messages, max_tokens, temperature, **kwargs)

        response = await asyncio.to_thread(
            self.bedrock.invoke_model_with_response_stream,
            modelId=model_id,
            body=json.dumps(request_body)
        )

        for event in response['body']:
            chunk = json.loads(event['chunk']['bytes'])
            yield self._format_response(model_id, chunk)

    def _format_request(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> dict[str, Any]:
        """Convert to model-specific format"""

        if "anthropic.claude" in model_id:
            # Anthropic format
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
            }
        elif "meta.llama" in model_id:
            # Llama format
            prompt = self._messages_to_prompt(messages)
            return {
                "prompt": prompt,
                "max_gen_len": max_tokens,
                "temperature": temperature,
                **kwargs
            }
        elif "mistral" in model_id:
            # Mistral format
            prompt = self._messages_to_prompt(messages)
            return {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
            }
        else:
            # Default format
            return {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
            }

    def _format_response(self, model_id: str, response: dict[str, Any]) -> dict[str, Any]:
        """Convert response to standard format"""

        if "anthropic.claude" in model_id:
            # Already in standard format
            return response
        elif "meta.llama" in model_id:
            # Convert Llama format
            return {
                "content": [{"type": "text", "text": response.get("generation", "")}],
                "stop_reason": response.get("stop_reason"),
                "usage": response.get("usage", {})
            }
        elif "mistral" in model_id:
            # Convert Mistral format
            return {
                "content": [{"type": "text", "text": response.get("outputs", [{}])[0].get("text", "")}],
                "stop_reason": response.get("stop_reason"),
                "usage": {}
            }
        else:
            # Return as-is
            return response

    def _messages_to_prompt(self, messages: list[dict[str, Any]]) -> str:
        """Convert messages to prompt string (for non-Anthropic models)"""
        parts = []
        for msg in messages:
            role = msg['role']
            content = msg['content']
            if isinstance(content, list):
                content = " ".join(item.get('text', '') for item in content if item.get('type') == 'text')
            parts.append(f"{role}: {content}")
        return "\n\n".join(parts)
