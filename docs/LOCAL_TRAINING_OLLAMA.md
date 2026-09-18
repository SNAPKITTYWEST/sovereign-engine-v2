# Local Training & Inference with Ollama

## Overview

**Ollama Provider** — local model inference without cloud API costs. Run Llama 3.2, CodeLlama, Mistral, or any GGUF model locally. Part of the multi-provider MoE router.

**Location:** `src/runtime/providers/ollama.py`

---

## Setup

### 1. Install Ollama

Download from https://ollama.ai/

```bash
# macOS / Linux / Windows
ollama pull llama3.2       # 3.2B model, ~2GB
ollama pull codellama      # For code tasks
ollama pull mistral        # 7B fast model
```

### 2. Start Ollama Server

```bash
ollama serve
# Listens on http://localhost:11434
```

---

## Usage

### Direct Ollama Provider

```python
from src.runtime.providers.ollama import OllamaProvider

provider = OllamaProvider(
    base_url="http://localhost:11434",
    default_model="llama3.2",
    api_key=None  # Local, no key needed
)

# Single inference
response = await provider.invoke_model(
    model_id="llama3.2",
    messages=[{"role": "user", "content": "write a fibonacci function"}],
    max_tokens=1024,
    temperature=0.7,
    system="You are a helpful coding assistant"
)
print(response["content"][0]["text"])

# Streaming
async for chunk in provider.invoke_model_stream(
    model_id="llama3.2",
    messages=[{"role": "user", "content": "explain quantum computing"}],
    max_tokens=2048
):
    print(chunk["content"][0]["text"], end="", flush=True)

# Health check
is_healthy = await provider.health_check()
print(f"Ollama running: {is_healthy}")

# List available models
models = await provider.list_models()
print(f"Available: {models}")
```

### Via Multi-Provider (MoE Router)

```python
from src.runtime.providers.multi import MultiProvider

# Falls back to Ollama if OpenRouter key not set
provider = MultiProvider(key_manager=None)

response = await provider.invoke_model(
    messages=[{"role": "user", "content": "..."}],
    system="You are an assistant"
)
```

**Routing logic:**

| Task Type | Provider | Model |
|-----------|----------|-------|
| code | Ollama (fallback) | CodeLlama or Llama 3.2 |
| reasoning | Ollama (fallback) | Llama 3.2 |
| creative | Ollama (fallback) | Mistral 7B |
| chat | Ollama (fallback) | Llama 3.2 |

If `OPENROUTER_API_KEY` is set, prefers cloud models (Nemotron 70B for code/reasoning).

---

## Environment Variables

```bash
# Ollama server location (default: localhost:11434)
export OLLAMA_BASE_URL="http://localhost:11434"

# Optional: API key for cloud-hosted Ollama
export OLLAMA_API_KEY="..."

# MoE routing will prefer remote if available
export OPENROUTER_API_KEY="sk-..."
```

---

## Features

### Non-Streaming Response

```python
response = await provider.invoke_model(
    model_id="llama3.2",
    messages=[...],
    max_tokens=2048,
    temperature=0.7
)
# Returns: {
#     "content": [{"text": "..."}],
#     "stop_reason": "end_turn",
#     "usage": {"prompt_tokens": N, "completion_tokens": M, "total_tokens": N+M}
# }
```

### Streaming Response

```python
async for chunk in provider.invoke_model_stream(
    model_id="llama3.2",
    messages=[...],
    max_tokens=2048
):
    # Each chunk is {"content": [{"text": "..."}], "stop_reason": ...}
    print(chunk["content"][0]["text"], end="")
```

### Health Check

```python
if await provider.health_check():
    print("Ollama server is running")
else:
    print("Ollama server is not reachable")
```

### List Models

```python
models = await provider.list_models()
# Returns: ["llama3.2", "codellama", "mistral:7b", ...]
```

---

## Common Models

| Model | Size | Best For | Latency |
|-------|------|----------|---------|
| llama3.2 | 1B, 3B, 8B | General chat | Fast (1B), balanced (3B) |
| codellama | 7B, 34B | Code generation | ~5s (7B) |
| mistral | 7B, 8x7B | Fast/creative | Very fast |
| neural-chat | 7B | Chat | Fast |
| dolphin-mixtral | 8x7B | Reasoning | Slower (MoE) |

---

## Integration with Sovereign Engine

### ReAct Agent

```python
from src.bridge.http_server import HTTPBridge
from src.runtime.providers.multi import MultiProvider

# Create bridge with local-first routing
provider = MultiProvider()  # Falls back to Ollama
bridge = HTTPBridge(host="127.0.0.1", port=19000)
bridge.agent.model = provider

# Start server
await bridge.run()

# Send messages
# POST http://127.0.0.1:19000/chat
# {"message": "write a python function"}
# ← Uses local Ollama if OpenRouter key not set
```

### Tool Dispatch

```python
from src.agents.react import ReActAgent
from src.tools.registry import ToolRegistry
from src.runtime.providers.multi import MultiProvider

registry = ToolRegistry()
registry.load_all_tools()

provider = MultiProvider()  # Local fallback
agent = ReActAgent(provider, registry, ...)

result = await agent.run("write a fibonacci function in rust")
# If no OpenRouter API key:
#   → ReActAgent uses Ollama
#   → Reasons locally
#   → Dispatches to code_write tool
#   → Returns function + trace
```

---

## Performance

Local Ollama (Llama 3.2 on M1 Mac):

| Task | Model | Latency | Memory |
|------|-------|---------|--------|
| Simple chat | 3B | 500ms | 4GB |
| Code gen | 7B | 2-3s | 8GB |
| Reasoning | 8B | 5-10s | 16GB |
| Streaming | 3B | 50ms per chunk | 4GB |

---

## Troubleshooting

**"Connection refused"**
```bash
# Make sure Ollama is running
ollama serve

# Check port is listening
lsof -i :11434
```

**"Model not found"**
```bash
# Pull the model first
ollama pull llama3.2
ollama pull codellama

# List available
ollama list
```

**Out of memory**
```bash
# Use smaller model
ollama pull llama3.2:1b  # 1B instead of 3B

# Or adjust context window
ollama set llama3.2 num_ctx 2048  # Default 4096
```

**Slow responses**
```bash
# Use GPU acceleration if available
# Ollama automatically detects NVIDIA CUDA

# For macOS, enable Metal (GPU):
# Just run: ollama serve
```

---

## Next Steps

- [ ] Fine-tune Llama 3.2 on sovereign-specific domain data
- [ ] Add quantized models (GGUF Q4, Q5 for < 4GB memory)
- [ ] Benchmark vs OpenRouter on latency + cost
- [ ] Add parallel model inference (batching)
- [ ] Cache model weights in Redis KV for faster cold start

---

## Files

```
src/runtime/providers/
├── __init__.py
├── ollama.py           ← Local inference
├── openai.py           OpenAI API
├── anthropic.py        Anthropic Claude API
├── bedrock.py          AWS Bedrock
├── openrouter.py       OpenRouter MoE
├── multi.py            ← MoE router (local fallback)
└── qra_router.py       QRA tensor routing
```
