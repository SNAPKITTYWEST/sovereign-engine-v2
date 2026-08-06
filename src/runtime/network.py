"""
Layer 4: Network Effects
Part of SOVEREIGN PYTHON LLM ENGINE

Explicit network effect handling with httpx.
All HTTP operations are async and auditable.
"""

from typing import AsyncIterator, Any
import httpx
import json
from datetime import datetime

from ..core.types import Temperature


# ==========================================
# HTTP Client
# ==========================================

class NetworkRuntime:
    """
    Explicit network effect handler.

    Wraps httpx with explicit timeouts and retry logic.
    """

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 2,
        follow_redirects: bool = True
    ):
        """
        Initialize network runtime.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            follow_redirects: Follow HTTP redirects
        """
        self.timeout = httpx.Timeout(timeout)
        self.max_retries = max_retries
        self.follow_redirects = follow_redirects

        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=follow_redirects
        )

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """
        HTTP GET request.

        Args:
            url: Request URL
            headers: Optional headers
            params: Optional query parameters

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: On request failure
        """
        response = await self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None
    ) -> httpx.Response:
        """
        HTTP POST request.

        Args:
            url: Request URL
            data: Form data
            json_data: JSON body
            headers: Optional headers

        Returns:
            HTTP response
        """
        response = await self.client.post(
            url,
            data=data,
            json=json_data,
            headers=headers
        )
        response.raise_for_status()
        return response

    async def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        POST JSON and parse JSON response.

        Args:
            url: Request URL
            payload: JSON payload
            headers: Optional headers

        Returns:
            Parsed JSON response
        """
        response = await self.post(url, json_data=payload, headers=headers)
        return response.json()

    async def put(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None
    ) -> httpx.Response:
        """HTTP PUT request"""
        response = await self.client.put(
            url,
            data=data,
            json=json_data,
            headers=headers
        )
        response.raise_for_status()
        return response

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None
    ) -> httpx.Response:
        """HTTP DELETE request"""
        response = await self.client.delete(url, headers=headers)
        response.raise_for_status()
        return response

    async def stream_get(
        self,
        url: str,
        headers: dict[str, str] | None = None
    ) -> AsyncIterator[bytes]:
        """
        Stream GET response.

        Args:
            url: Request URL
            headers: Optional headers

        Yields:
            Response chunks
        """
        async with self.client.stream('GET', url, headers=headers) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def stream_sse(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream Server-Sent Events (SSE).

        Args:
            url: Request URL
            payload: JSON payload
            headers: Optional headers

        Yields:
            Parsed SSE events
        """
        async with self.client.stream('POST', url, json=payload, headers=headers) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                # SSE format: "data: {...}"
                if line.startswith('data: '):
                    data_str = line[6:]  # Remove "data: " prefix
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

    async def close(self) -> None:
        """Close HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        """Context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()


# ==========================================
# Retry Logic
# ==========================================

class RetryableHTTPClient:
    """HTTP client with automatic retry logic"""

    def __init__(
        self,
        network: NetworkRuntime,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        retry_statuses: set[int] | None = None
    ):
        """
        Initialize retryable client.

        Args:
            network: Base network runtime
            max_retries: Maximum retry attempts
            backoff_factor: Backoff multiplier (seconds)
            retry_statuses: HTTP statuses to retry (None = 408, 429, 5xx)
        """
        self.network = network
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        if retry_statuses is None:
            self.retry_statuses = {408, 429, 500, 502, 503, 504}
        else:
            self.retry_statuses = retry_statuses

    async def post_with_retry(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        POST with automatic retry.

        Args:
            url: Request URL
            payload: JSON payload
            headers: Optional headers

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPError: After all retries exhausted
        """
        import asyncio

        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return await self.network.post_json(url, payload, headers)
            except httpx.HTTPStatusError as e:
                last_error = e

                # Check if status is retryable
                if e.response.status_code not in self.retry_statuses:
                    raise

                # Don't retry on last attempt
                if attempt == self.max_retries:
                    raise

                # Exponential backoff
                wait_time = self.backoff_factor * (2 ** attempt)
                await asyncio.sleep(wait_time)

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e

                # Don't retry on last attempt
                if attempt == self.max_retries:
                    raise

                # Exponential backoff
                wait_time = self.backoff_factor * (2 ** attempt)
                await asyncio.sleep(wait_time)

        # Should not reach here, but just in case
        raise last_error


# ==========================================
# LLM API Clients
# ==========================================

class LlamaAPIClient:
    """
    Client for Llama API (from llama-api-python analysis).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.llama.com/v1",
        network: NetworkRuntime | None = None
    ):
        """
        Initialize Llama API client.

        Args:
            api_key: API key
            base_url: Base URL for API
            network: Network runtime (creates if None)
        """
        self.api_key = api_key
        self.base_url = base_url

        if network is None:
            self.network = NetworkRuntime()
        else:
            self.network = network

    def _auth_headers(self) -> dict[str, str]:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.api_key}"}

    async def generate(
        self,
        messages: list[dict[str, str]],
        model: str = "Llama-3.3-70B-Instruct",
        temperature: float = 0.0,
        max_tokens: int | None = None
    ) -> str:
        """
        Generate completion.

        Args:
            messages: Conversation messages
            model: Model ID
            temperature: Sampling temperature
            max_tokens: Max tokens to generate

        Returns:
            Generated text
        """
        url = f"{self.base_url}/chat/completions"

        payload: dict[str, Any] = {
            "messages": messages,
            "model": model,
            "temperature": temperature
        }

        if max_tokens is not None:
            payload["max_completion_tokens"] = max_tokens

        headers = self._auth_headers()
        response = await self.network.post_json(url, payload, headers)

        return response["completion_message"]["content"]

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        model: str = "Llama-3.3-70B-Instruct",
        temperature: float = 0.0
    ) -> AsyncIterator[str]:
        """
        Generate completion with streaming.

        Yields:
            Text chunks
        """
        url = f"{self.base_url}/chat/completions"

        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "stream": True
        }

        headers = self._auth_headers()

        async for event in self.network.stream_sse(url, payload, headers):
            if "event" in event and "delta" in event["event"]:
                delta = event["event"]["delta"]
                if "text" in delta:
                    yield delta["text"]


# ==========================================
# Generic LLM Client
# ==========================================

class GenericLLMClient:
    """
    Generic LLM client (OpenAI-compatible API).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        network: NetworkRuntime | None = None
    ):
        self.api_key = api_key
        self.base_url = base_url

        if network is None:
            self.network = NetworkRuntime()
        else:
            self.network = network

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def generate(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None
    ) -> str:
        """OpenAI-compatible chat completion"""
        url = f"{self.base_url}/chat/completions"

        payload: dict[str, Any] = {
            "messages": messages,
            "model": model,
            "temperature": temperature
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        headers = self._auth_headers()
        response = await self.network.post_json(url, payload, headers)

        return response["choices"][0]["message"]["content"]


# ==========================================
# Rate Limiter
# ==========================================

class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    """

    def __init__(self, requests_per_second: float):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second
        """
        self.requests_per_second = requests_per_second
        self.interval = 1.0 / requests_per_second
        self.last_request_time: float | None = None

    async def acquire(self) -> None:
        """
        Acquire rate limit token (wait if necessary).
        """
        import asyncio
        import time

        now = time.time()

        if self.last_request_time is not None:
            elapsed = now - self.last_request_time
            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                await asyncio.sleep(wait_time)

        self.last_request_time = time.time()


# ==========================================
# Request/Response Logging
# ==========================================

class LoggedNetworkRuntime:
    """
    Network runtime with request/response logging.
    """

    def __init__(self, network: NetworkRuntime, log_path: str | None = None):
        """
        Initialize logged runtime.

        Args:
            network: Base network runtime
            log_path: Path to log file (None = no file logging)
        """
        self.network = network
        self.log_path = log_path
        self.requests_log: list[dict[str, Any]] = []

    async def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """POST with logging"""
        start_time = datetime.now()

        try:
            response = await self.network.post_json(url, payload, headers)
            elapsed = (datetime.now() - start_time).total_seconds()

            # Log request/response
            log_entry = {
                "timestamp": start_time.isoformat(),
                "method": "POST",
                "url": url,
                "payload": payload,
                "response": response,
                "elapsed_seconds": elapsed,
                "success": True
            }

            self.requests_log.append(log_entry)

            return response

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()

            # Log error
            log_entry = {
                "timestamp": start_time.isoformat(),
                "method": "POST",
                "url": url,
                "payload": payload,
                "error": str(e),
                "elapsed_seconds": elapsed,
                "success": False
            }

            self.requests_log.append(log_entry)
            raise

    def get_logs(self) -> list[dict[str, Any]]:
        """Get all logged requests"""
        return self.requests_log

    async def save_logs(self) -> None:
        """Save logs to file"""
        if self.log_path is None:
            return

        import aiofiles
        from pathlib import Path

        log_path = Path(self.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(log_path, 'w') as f:
            for entry in self.requests_log:
                await f.write(json.dumps(entry) + '\n')
