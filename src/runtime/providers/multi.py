"""
Multi-Provider Adapter with MoE Routing
Part of SOVEREIGN PYTHON LLM ENGINE

Mixture of Experts routing:
- Code tasks → Nemotron 70B (best for coding)
- Creative/chat → Mistral 7B (fast, creative)
- Reasoning → Nemotron 70B (best reasoning)
- Fallback → Ollama (local Llama 3.2, Muse 1.0)
"""

import os
from typing import Any, AsyncIterator
from .openrouter import OpenRouterProvider
from .ollama import OllamaProvider


# MoE Task Classification
def classify_task(messages: list[dict[str, Any]], system: str | None = None) -> str:
    """
    Classify task type from messages to route to best expert.

    Returns:
        "code" | "creative" | "reasoning" | "chat"
    """
    # Combine all text
    all_text = (system or "").lower()
    for msg in messages or []:
        all_text += " " + msg.get("content", "").lower()

    # Code indicators
    code_keywords = ["function", "class", "def ", "import", "const", "let", "var",
                     "python", "javascript", "typescript", "rust", "go", "code",
                     "bug", "error", "debug", "implement", "refactor"]

    # Creative indicators
    creative_keywords = ["write", "story", "poem", "creative", "imagine", "describe",
                        "explain like", "eli5", "metaphor", "analogy"]

    # Reasoning indicators
    reasoning_keywords = ["analyze", "compare", "evaluate", "reason", "logic", "proof",
                         "theorem", "mathematical", "calculate", "solve", "deduce"]

    code_score = sum(1 for kw in code_keywords if kw in all_text)
    creative_score = sum(1 for kw in creative_keywords if kw in all_text)
    reasoning_score = sum(1 for kw in reasoning_keywords if kw in all_text)

    if code_score >= 2:
        return "code"
    elif reasoning_score >= 2:
        return "reasoning"
    elif creative_score >= 2:
        return "creative"
    else:
        return "chat"


class MultiProvider:
    """
    Multi-provider with MoE routing and fallback.

    Expert routing:
    - Code → Nemotron 70B (best coding model)
    - Reasoning → Nemotron 70B (best logic)
    - Creative → Mistral 7B (fast, creative)
    - Chat → Mistral 7B or Llama 3.2

    Fallback chain:
    1. OpenRouter (if API key set)
    2. Ollama (local)
    """

    def __init__(self, key_manager=None):
        """Initialize multi-provider with MoE routing."""
        self.providers = []
        self.has_openrouter = False
        self.key_manager = key_manager

        # Try OpenRouter first if API key available
        openrouter_key = None
        if key_manager and key_manager.is_valid("openrouter"):
            openrouter_key = key_manager.get_key("openrouter")
        else:
            openrouter_key = os.getenv("OPENROUTER_API_KEY")

        if openrouter_key:
            try:
                self.providers.append({
                    "name": "openrouter",
                    "provider": OpenRouterProvider(api_key=openrouter_key),
                    "models": {
                        "code": "nvidia/llama-3.1-nemotron-70b-instruct:free",
                        "reasoning": "nvidia/llama-3.1-nemotron-70b-instruct:free",
                        "creative": "mistralai/mistral-7b-instruct:free",
                        "chat": "mistralai/mistral-7b-instruct:free"
                    }
                })
                self.has_openrouter = True
                print("OK: OpenRouter loaded: Nemotron 70B (code/reasoning), Mistral 7B (creative/chat)")
            except Exception as e:
                print(f"OpenRouter init failed: {e}")

        # Always add Ollama as fallback
        self.providers.append({
            "name": "ollama",
            "provider": OllamaProvider(),
            "models": {
                "code": "codellama",
                "reasoning": "llama3.2",
                "creative": "muse:1.0",
                "chat": "llama3.2"
            }
        })
        print("OK: Ollama loaded: CodeLlama (code), Llama 3.2 (reasoning/chat), Muse 1.0 (creative)")

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
        Invoke model with MoE routing and fallback.

        Routes to best expert based on task type, with fallback chain.

        Args:
            model_id: Override model (skips MoE routing)
            messages: Chat messages
            max_tokens: Max response tokens
            temperature: Sampling temperature
            system: System prompt
            tools: Tool definitions
            **kwargs: Additional parameters

        Returns:
            Response dict with "content" field
        """
        # Classify task for MoE routing (unless model specified)
        if model_id is None:
            task_type = classify_task(messages, system)
        else:
            task_type = "chat"  # Default if user specified model

        last_error = None

        for provider_config in self.providers:
            provider_name = provider_config["name"]
            provider = provider_config["provider"]
            model_map = provider_config["models"]

            # Select expert for this task
            if model_id:
                effective_model = model_id
            else:
                effective_model = model_map.get(task_type, model_map.get("chat", "llama3.2"))

            try:
                print(f"→ Routing {task_type} task to {provider_name}:{effective_model}")

                result = await provider.invoke_model(
                    model_id=effective_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    tools=tools,
                    **kwargs
                )

                # Success - return result with metadata
                result["_provider"] = provider_name
                result["_model"] = effective_model
                result["_task_type"] = task_type
                return result

            except Exception as e:
                last_error = e
                print(f"ERROR: {provider_name} failed: {e}")
                print(f"  Trying next provider...")
                continue

        # All providers failed
        raise RuntimeError(f"All providers failed. Last error: {last_error}")

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
        Invoke model with streaming, MoE routing, and fallback.

        Args:
            model_id: Override model (skips MoE routing)
            messages: Chat messages
            max_tokens: Max response tokens
            temperature: Sampling temperature
            system: System prompt
            **kwargs: Additional parameters

        Yields:
            Response chunks
        """
        # Classify task for MoE routing
        if model_id is None:
            task_type = classify_task(messages, system)
        else:
            task_type = "chat"

        last_error = None

        for provider_config in self.providers:
            provider_name = provider_config["name"]
            provider = provider_config["provider"]
            model_map = provider_config["models"]

            # Select expert for this task
            if model_id:
                effective_model = model_id
            else:
                effective_model = model_map.get(task_type, model_map.get("chat", "llama3.2"))

            try:
                print(f"→ Streaming {task_type} task via {provider_name}:{effective_model}")

                async for chunk in provider.invoke_model_stream(
                    model_id=effective_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    **kwargs
                ):
                    chunk["_provider"] = provider_name
                    chunk["_model"] = effective_model
                    chunk["_task_type"] = task_type
                    yield chunk

                # If we successfully streamed, we're done
                return

            except Exception as e:
                last_error = e
                print(f"ERROR: {provider_name} stream failed: {e}")
                print(f"  Trying next provider...")
                continue

        # All providers failed
        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def list_providers(self) -> list[dict[str, Any]]:
        """
        List available providers and their models.

        Returns:
            List of provider configs
        """
        result = []
        for config in self.providers:
            result.append({
                "name": config["name"],
                "available_models": config["models"]
            })
        return result
