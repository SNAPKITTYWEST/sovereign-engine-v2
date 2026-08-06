# 🔌 PROVIDER CONFIGURATION

## Overview

Sovereign Engine uses a **Mixture of Experts (MoE)** routing system with automatic fallback:

1. **OpenRouter** (free credits, daily key rotation)
   - Nemotron 70B → Code & Reasoning tasks
   - Mistral 7B → Creative & Chat tasks

2. **Ollama** (local, always available)
   - CodeLlama → Code tasks
   - Llama 3.2 → Reasoning & Chat
   - Muse 1.0 → Creative tasks

---

## Setup

### 1. Copy environment template

```bash
cp .env.example .env
```

### 2. Add your OpenRouter key

Get free credits: https://openrouter.ai/keys

```env
OPENROUTER_API_KEY=sk-or-v1-YOUR_KEY_HERE
```

### 3. Install Ollama (optional, for local fallback)

Download: https://ollama.ai

Pull models:
```bash
ollama pull llama3.2
ollama pull codellama
ollama pull muse:1.0
```

---

## Daily Key Rotation

OpenRouter free credits require daily key rotation.

**Option 1: Manual**
1. Get new key from https://openrouter.ai/keys
2. Update `.env` file
3. Restart bridge server

**Option 2: Automated (TODO)**
- Script to auto-rotate from key pool
- Cron job for midnight rotation

---

## MoE Routing Logic

The system automatically classifies tasks and routes to the best expert:

| Task Type | OpenRouter | Ollama Fallback |
|-----------|-----------|-----------------|
| **Code** | Nemotron 70B | CodeLlama |
| **Reasoning** | Nemotron 70B | Llama 3.2 |
| **Creative** | Mistral 7B | Muse 1.0 |
| **Chat** | Mistral 7B | Llama 3.2 |

Classification keywords:
- **Code**: function, class, import, debug, implement, refactor
- **Reasoning**: analyze, evaluate, prove, logic, calculate
- **Creative**: write, story, poem, imagine, describe
- **Chat**: everything else

---

## Free Models Available

### OpenRouter (with key)
- `nvidia/llama-3.1-nemotron-70b-instruct:free` — 70B params, best coding
- `mistralai/mistral-7b-instruct:free` — 7B params, fast chat
- `mistralai/mixtral-8x7b-instruct:free` — 8×7B MoE, balanced

### Ollama (local)
- `llama3.2` — Meta's latest, 3B params
- `codellama` — Specialized for code
- `muse:1.0` — Creative writing
- `qwen2.5-coder` — Alternative code model
- `deepseek-coder` — Another code specialist

---

## Testing Provider Setup

```bash
# Start bridge server
cd c:/tmp/sovereign-reverse/engine
python -m src.bridge.http_server

# Test with C client
cd C:/Users/jessi/Desktop/sovereign-ide/native/bridge
./example.exe
```

You should see:
```
✓ OpenRouter loaded: Nemotron 70B (code/reasoning), Mistral 7B (creative/chat)
✓ Ollama loaded: CodeLlama (code), Llama 3.2 (reasoning/chat), Muse 1.0 (creative)
```

---

## Troubleshooting

**No OpenRouter key → Uses Ollama only**
- Still works, just slower/smaller models
- Set `OPENROUTER_API_KEY` to enable cloud experts

**Ollama not installed → OpenRouter only**
- Works if key is valid
- Install Ollama for offline fallback

**Both fail → Check logs**
- OpenRouter: Check key validity, rate limits
- Ollama: Check service running (`ollama serve`)

---

## Cost

**Total cost: $0/month**
- OpenRouter: Free tier with daily key rotation
- Ollama: Runs locally, no API costs

This is the **100% free architecture** Jessica requested.
