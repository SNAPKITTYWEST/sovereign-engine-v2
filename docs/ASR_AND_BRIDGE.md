# Audio-to-Text & Message Bridge

## ASR: Qwen3 Fine-Tuning Pipeline

**Location:** `src/asr/`

Automatic Speech Recognition module with Qwen3-ASR-1.7B fine-tuning on custom audio data.

### Components

#### `src/asr/finetune.py`

**Qwen3-ASR Fine-tuning Script**

- **Model:** Qwen/Qwen3-ASR-1.7B (1.7B parameters)
- **Input format:** JSONL with `audio` (path), `text` (transcript), `prompt` (optional)
- **Audio preprocessing:** librosa @ 16kHz, mono
- **Trainer:** HuggingFace Trainer with Qwen3 processor
- **Dtype:** bfloat16 (A100) or float16 (fallback)
- **Checkpoint resumption:** Automatic latest checkpoint detection + resume-from flag

**Utilities:**

```python
# Find latest checkpoint
find_latest_checkpoint(output_dir)  # → "checkpoint-N"

# Ensure every checkpoint is loadable
MakeEveryCheckpointInferableCallback(base_model_path)
  # Copies config.json, tokenizer, etc to each checkpoint dir

# Data collation (prefix-only training)
DataCollatorForQwen3ASRFinetuning
  # Builds: prefix_text (system + audio prompt)
  #         full_text (prefix + target transcript)
  #         Masks prefix tokens in labels (-100 ignore index)
```

**CLI:**

```bash
python -m src.asr.finetune \
  --model_path Qwen/Qwen3-ASR-1.7B \
  --train_file train.jsonl \
  --output_dir ./qwen3-asr-finetuning-out \
  --batch_size 32 \
  --grad_acc 4 \
  --lr 2e-5 \
  --epochs 1 \
  --save_steps 200 \
  --resume 1  # Auto-find latest checkpoint
```

**Input JSONL format:**

```jsonl
{"audio": "/path/to/audio.wav", "text": "hello world", "prompt": ""}
{"audio": "/path/to/audio2.wav", "text": "another sample", "prompt": "Transcribe carefully"}
```

---

#### `src/tools/audio/transcribe.py`

**Audio Transcription Tool**

Multi-provider transcription (OpenAI Whisper + local Whisper).

```python
AudioTranscriber(provider="openai", model="whisper-1", worm_ledger=ledger)
  .transcribe(Path("audio.wav"), language="en")
  → Transcription(text, language, segments, duration, model)
```

**Providers:**

- `"openai"`: OpenAI Whisper API (requires `OPENAI_API_KEY`)
- `"local"`: Local Whisper model (requires `openai-whisper` package)

**Features:**

- Async interface (can stream multiple transcriptions)
- WORM ledger logging (audit trail)
- Returns: text, detected language, segment timings, duration

**Tool registration:**

```python
await transcribe_audio_tool(audio_path="file.wav", provider="openai", language="en")
→ {"text": "...", "language": "en", "duration": 3.5, "segments_count": 2}
```

---

## HTTP Bridge: Message Parsing & Agent Dispatch

**Location:** `src/bridge/http_server.py`

HTTP REST API for C frontend ↔ Python engine communication. Receives messages from Ahmad (or any external system), parses intent, routes through 11-stage pipeline, executes tools, returns results.

### Architecture

```
Ahmad (or external client)
  ↓ HTTP POST /chat
HTTPBridge (aiohttp server on :19000)
  ├─ Parse message → ReActAgent
  ├─ Stage 1-11 routing pipeline
  │  ├─ Regex parser (tokenize)
  │  ├─ AST builder (inverted tree)
  │  ├─ Symbolic graph (signal flow)
  │  ├─ Jordan transform (SpinFactor routing)
  │  ├─ Jacobian lens (sensitivity)
  │  ├─ Constraint eval (H ≤ 0.20 nats)
  │  ├─ Sparse activation (top-k experts)
  │  ├─ NAND filter (conflict suppression)
  │  ├─ Agent dispatch (tool selection)
  │  ├─ Merge output (concatenate/vote/weighted)
  │  └─ WORM seal (Blake2b + Ed25519)
  ├─ Execute tools (with approval)
  ├─ Log to WORM ledger
  └─ Return JSON response
```

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/chat` | Send message, get response |
| POST | `/agent/run` | Run ReAct agent on task |
| POST | `/tool/execute` | Execute single tool |
| GET | `/tools` | List all 34 tools |
| GET | `/health` | Health check |
| POST | `/keys/set` | Set API key (OpenAI, Anthropic, Bedrock) |
| GET | `/keys/status` | Show configured providers |
| DELETE | `/keys/{provider}` | Clear API key |
| GET | `/routing/traces` | Get last N routing traces |
| GET | `/routing/stats` | Aggregated routing stats |
| POST | `/routing/test` | Test routing on input |
| GET | `/routing/live` | WebSocket-ready live trace stream |

### Usage

**Start server:**

```bash
python -m src.bridge.http_server --host 127.0.0.1 --port 19000
```

**Send message from Ahmad:**

```bash
curl -X POST http://127.0.0.1:19000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "write a fibonacci function in python", "language": "python"}'
```

**Response:**

```json
{
  "status": "success",
  "response": "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)",
  "tool_calls": ["code_write"],
  "trace": {
    "stages": [
      {"stage": 1, "name": "regex_parser", "tokens": [...], "time_ms": 2},
      {"stage": 2, "name": "ast_builder", "tree": {...}, "time_ms": 1},
      ...
    ],
    "total_time_ms": 143,
    "seal_hash": "a3f7c9b2e5d1..."
  },
  "worm_entry": {
    "timestamp": "2026-09-07T10:30:00Z",
    "entry_hash": "7e2a4f1b8c3d...",
    "prev_hash": "a3f7c9b2e5d1..."
  }
}
```

### Key Components

**ReActAgent**

```python
ReActAgent(model, registry, approval, ledger, config)
  .run(task_description)
  → Agent reasons (think) → acts (tool call) → observes (result)
```

- **Think:** LLM generates reasoning step
- **Act:** Selects tool + parameters
- **Observe:** Executes tool, captures output
- **Loop:** Up to `max_steps=15` iterations

**ToolRegistry**

34 registered tools across 9 namespaces:
- `filesystem` (read, write, list, search)
- `code` (parse, analyze, execute)
- `git` (status, diff, log, blame)
- `web` (fetch, parse, headers)
- `audio` (transcribe, extract, process)
- `database` (query, schema, insert)
- `embeddings` (semantic search)
- `pytorch` (model load, inference)
- `inference` (claude, openai, bedrock, ollama)

**ApprovalEngine**

Human-in-the-loop gate for sensitive operations:
- High-risk tools require approval
- Can auto-approve if user trust score > threshold
- WORM logs all approvals

**WORMLedger**

Append-only audit log:
- Every message logged
- Every tool call logged
- Every approval logged
- Hash chain (tamper-evident)
- Ed25519 signing

---

## Integration: Video → Transcript → Agent Parse

**End-to-end workflow:**

```
1. User uploads video.mp4
   ↓
2. Extract audio → audio.wav
   ↓
3. transcribe_audio_tool(audio.wav)
   → "write a fibonacci function in python"
   ↓
4. POST /chat with transcript
   ↓
5. HTTPBridge parses via 11-stage routing
   ↓
6. ReActAgent dispatches to code_write tool
   ↓
7. Tool generates function
   ↓
8. Response sealed in WORM ledger
```

---

## Cloudflare Worker Wrapper (Optional)

Could deploy HTTPBridge to Cloudflare Workers for global edge availability:

```typescript
// wrangler.toml
name = "sovereign-bridge-worker"
main = "src/worker.ts"
compatibility_date = "2026-09-07"

[[env.production]]
routes = [
  { pattern = "api.sovereign.engine/*", zone_name = "sovereign.engine" }
]
```

Ahmad's messages could arrive via:
- Discord webhook → Worker → bridge
- Slack slash command → Worker → bridge
- Email (via SendGrid) → Worker → bridge
- Direct HTTPS POST → Worker → bridge

Worker acts as stateless proxy; all state kept in Redis KV (message history, approval queue).

---

## Files

```
src/asr/
├── __init__.py
├── finetune.py           Qwen3-ASR fine-tuning
├── forced_aligner.py     CTC alignment (for punctuation/timing)
└── compiler/
    └── dag_ir.py         Compilation DAG (for inference optimization)

src/tools/audio/
├── __init__.py
└── transcribe.py         Multi-provider transcription

src/bridge/
├── __init__.py
├── http_server.py        Main HTTPBridge class
├── key_manager.py        API key storage/retrieval
├── routing_trace.py      Trace collection + stats
└── stdio_server.py       Alternative stdio-based bridge (not HTTP)
```

---

## Environment Variables

```bash
# For Whisper API
export OPENAI_API_KEY="sk-..."

# For Anthropic routing (Claude backend)
export ANTHROPIC_API_KEY="sk-ant-..."

# For Bedrock (AWS)
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."

# Optional: S3 checkpoint storage
export CHECKPOINT_BUCKET="sovereign-checkpoints"
export AWS_REGION="us-west-2"
```

---

## Performance

| Component | Latency | Throughput |
|-----------|---------|-----------|
| Whisper API (1min audio) | 2-5s | 12 audio files/min |
| Whisper local (base model) | 15-30s | 2-4 audio files/min |
| HTTPBridge routing (11 stages) | 100-300ms | 3-10 messages/sec |
| ReActAgent (1 tool call) | 1-5s | 0.2-1 tool call/sec |
| WORM ledger append | 5-20ms | 50-200 entries/sec |

---

## Next Steps

- [ ] Add Discord bot wrapper (receive voice messages → bridge)
- [ ] Deploy HTTPBridge to Cloudflare Workers (global edge)
- [ ] Implement Redis KV for distributed state (if Workers)
- [ ] Add streaming response support (SSE for long-running tasks)
- [ ] Fine-tune Qwen3-ASR on domain-specific audio (sovereign jargon)
- [ ] Build WebSocket endpoint for real-time transcription
