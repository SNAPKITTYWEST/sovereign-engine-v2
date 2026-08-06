"""
OpenRouter Provider Adapter
Part of SOVEREIGN PYTHON LLM ENGINE

Access to free models via OpenRouter (Nemotron, etc).
"""

import json
from typing import Any, AsyncIterator
import aiohttp
import os


class OpenRouterProvider:
    """
    OpenRouter API provider.

    Provides access to free models like nvidia/nemotron-mini.
    """

    def __init__(self, api_key: str | None = None, base_url: str = "https://openrouter.ai/api/v1"):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key (or set OPENROUTER_API_KEY env var)
            base_url: OpenRouter API base URL
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")

        if not self.api_key:
            raise ValueError("OpenRouter API key required. Set OPENROUTER_API_KEY env var.")

    async def invoke_model(
        self,
        model_id: str = "nvidia/llama-3.1-nemotron-70b-instruct:free",
        messages: list[dict[str, Any]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Invoke OpenRouter model.

        Args:
            model_id: Model name (e.g., "nvidia/llama-3.1-nemotron-70b-instruct:free")
            messages: Chat messages
            max_tokens: Max response tokens
            temperature: Sampling temperature
            system: System prompt
            tools: Tool definitions
            **kwargs: Additional parameters

        Returns:
            Response dict with "content" field
        """
        # Build request
        request_data = {
            "model": model_id,
            "messages": messages or [],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if system:
            # Add system message at start
            request_data["messages"].insert(0, {
                "role": "system",
                "content": system
            })

        if tools:
            request_data["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sovereignide.local",
            "X-Title": "Sovereign IDE"
        }

        # Send request
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=request_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"OpenRouter API error {response.status}: {error_text}")

                result = await response.json()

                # Convert to Bedrock-like format
                choice = result["choices"][0]
                message = choice["message"]
                content_text = message.get("content", "")

                usage = result.get("usage", {})

                return {
                    "content": [{"text": content_text}],
                    "stop_reason": choice.get("finish_reason", "end_turn"),
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0)
                    }
                }

    async def invoke_model_stream(
        self,
        model_id: str = "nvidia/llama-3.1-nemotron-70b-instruct:free",
        messages: list[dict[str, Any]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: str | None = None,
        **kwargs
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Invoke OpenRouter model with streaming.

        Args:
            model_id: Model name
            messages: Chat messages
            max_tokens: Max response tokens
            temperature: Sampling temperature
            system: System prompt
            **kwargs: Additional parameters

        Yields:
            Response chunks
        """
        request_data = {
            "model": model_id,
            "messages": messages or [],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }

        if system:
            request_data["messages"].insert(0, {
                "role": "system",
                "content": system
            })

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sovereignide.local",
            "X-Title": "Sovereign IDE"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=request_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"OpenRouter API error {response.status}: {error_text}")

                async for line in response.content:
                    if not line:
                        continue

                    line_str = line.decode('utf-8').strip()
                    if not line_str.startswith("data: "):
                        continue

                    data_str = line_str[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"]
                        content = delta.get("content", "")

                        if content:
                            yield {
                                "content": [{"text": content}],
                                "stop_reason": chunk["choices"][0].get("finish_reason")
                            }
                    except json.JSONDecodeError:
                        continue

    async def list_models(self) -> list[dict[str, Any]]:
        """
        List available models.

        Returns:
            List of model metadata
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return []

                result = await response.json()
                return result.get("data", [])
