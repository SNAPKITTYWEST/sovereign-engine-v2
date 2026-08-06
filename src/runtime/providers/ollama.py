"""
Ollama Provider Adapter
Part of SOVEREIGN PYTHON LLM ENGINE

Local inference via Ollama API.
"""

import json
import os
from typing import Any, AsyncIterator
import aiohttp


class OllamaProvider:
    """
    Ollama inference provider (local or cloud).

    Connects to Ollama server (default: http://localhost:11434).
    Supports API key for cloud Ollama instances.
    """

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str = "llama3.2",
        api_key: str | None = None
    ):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama API base URL (or OLLAMA_BASE_URL env var)
            default_model: Default model to use
            api_key: Optional API key for cloud Ollama (or OLLAMA_API_KEY env var)
        """
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip('/')
        self.default_model = default_model
        self.api_key = api_key or os.getenv("OLLAMA_API_KEY")

    async def invoke_model(
        self,
        model_id: str | None = None,
        messages: list[dict[str, Any]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Invoke Ollama model.

        Args:
            model_id: Model name (e.g., "llama3.2", "codellama")
            messages: Chat messages
            max_tokens: Max response tokens
            temperature: Sampling temperature
            system: System prompt
            tools: Tool definitions (Ollama supports this via JSON mode)
            **kwargs: Additional parameters

        Returns:
            Response dict with "content" field
        """
        model = model_id or self.default_model

        # Build Ollama request
        request_data = {
            "model": model,
            "messages": messages or [],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        if system:
            # Add system message at start
            request_data["messages"].insert(0, {
                "role": "system",
                "content": system
            })

        # Build headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Send request
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Ollama API error {response.status}: {error_text}")

                result = await response.json()

                # Convert Ollama response to Bedrock-like format
                message = result.get("message", {})
                content_text = message.get("content", "")

                return {
                    "content": [{"text": content_text}],
                    "stop_reason": "end_turn",
                    "usage": {
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                        "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                    }
                }

    async def invoke_model_stream(
        self,
        model_id: str | None = None,
        messages: list[dict[str, Any]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system: str | None = None,
        **kwargs
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Invoke Ollama model with streaming.

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
        model = model_id or self.default_model

        request_data = {
            "model": model,
            "messages": messages or [],
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        if system:
            request_data["messages"].insert(0, {
                "role": "system",
                "content": system
            })

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Ollama API error {response.status}: {error_text}")

                async for line in response.content:
                    if not line:
                        continue

                    try:
                        chunk = json.loads(line)
                        message = chunk.get("message", {})
                        content = message.get("content", "")

                        if content:
                            yield {
                                "content": [{"text": content}],
                                "stop_reason": "end_turn" if chunk.get("done") else None
                            }
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        """
        Check if Ollama server is reachable.

        Returns:
            True if server is up
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """
        List available models.

        Returns:
            List of model names
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return []

                result = await response.json()
                models = result.get("models", [])
                return [m["name"] for m in models]
