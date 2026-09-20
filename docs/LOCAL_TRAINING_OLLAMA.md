# Local inference with Ollama

[OllamaProvider](../src/runtime/providers/ollama.py) is an HTTP inference adapter. It does not implement model training. The historical filename is retained so existing links continue to work.

## Prerequisites

Use an environment with the repository imports available and `aiohttp` installed. Separately provide a running Ollama service and a model already available to that service. This guide does not download a model or claim any specific model is currently available remotely.

The adapter defaults to `http://localhost:11434`. It reads `OLLAMA_BASE_URL` and optional `OLLAMA_API_KEY`, or accepts explicit constructor arguments. Its default model name is `llama3.2`; choose an installed model instead of assuming that default exists.

## Direct provider example

This example contacts your configured service. It has not been exercised against a live model in the documentation validation.

```python
import asyncio
from src.runtime.providers.ollama import OllamaProvider

async def main():
    provider = OllamaProvider(base_url="http://localhost:11434")
    if not await provider.health_check():
        raise RuntimeError("Ollama service is unavailable")
    models = await provider.list_models()
    if not models:
        raise RuntimeError("No models reported by the service")
    print("Using:", models[0])
    response = await provider.invoke_model(
        model_id=models[0],
        messages=[{"role": "user", "content": "Explain binary search briefly."}],
        temperature=0.0, max_tokens=128,
    )
    print(response["content"][0]["text"])

asyncio.run(main())
```

`invoke_model_stream` exposes the streaming path. Read its yielded event shape before connecting it to a renderer.

## Multi-provider routing

[MultiProvider](../src/runtime/providers/multi.py) adds OpenRouter when a key is available, then Ollama as fallback. It classifies tasks and selects from hard-coded model-name mappings. Those names are configuration in the source, not proof that a local model is installed or a remote endpoint remains available.

Use OllamaProvider directly when you want a specific local model without the fallback policy. Neither provider implements the same `generate` interface as [BedrockBackend](../src/inference/bedrock_backend.py); consumers need an explicit adapter.

## Training is separate

The [ASR guide](ASR_AND_BRIDGE.md) describes a fine-tuning entrypoint. [src/models/](../src/models/) contains memory and checkpoint utilities; [training/](../training/) contains the Swift corpus/swarm visualization. A local inference response does not demonstrate training or distributed parameter updates.

See [Configuration](CONFIGURATION.md) for actual settings and [Testing](TESTING.md) for failure diagnosis.
