# ASR and HTTP bridge

ASR training, direct provider chat, agent tasks, and routing traces are separate code paths. The HTTP bridge does not automatically turn audio into training data.

## HTTP service

Source: [http_server.py](../src/bridge/http_server.py).

The bridge imports engine dependencies and uses `aiohttp`, which is not listed in the root requirements file. After installing the engine requirements, install `aiohttp` in the same environment.

```bash
python -m pip install aiohttp
python -m src.bridge.http_server
```

This is an integration entrypoint, not a validated first-run example. Constructor/import failures are possible; see [deployment readiness](PRODUCTION_HARDENING.md). Defaults are `127.0.0.1:19000`. The module does not parse `--host`/`--port`; custom launchers must call `HTTPBridge(host=..., port=...)` explicitly.

## Handler contracts

| Method/path | Input | Source behavior |
|---|---|---|
| GET `/health` | None | Returns status and timestamp; not a provider health check |
| GET `/tools` | None | Returns up to 50 tool IDs, descriptions, and risk classes |
| POST `/chat` | `{"message": "Hello"}` | Calls MultiProvider directly and returns `{"reply": ...}` |
| POST `/agent/run` | `{"task": "..."}` | Attempts Task construction and agent execution; current `task_id`/`id` mismatch remains |
| POST `/tool/execute` | `{"tool": "...", "args": {}}` | Calls handler directly and stringifies the result |
| POST `/keys/set` | Provider/key payload | Changes provider credentials; inspect handler and key manager before use |
| GET `/keys/status` | None | Reports configured key status |
| DELETE `/keys/{provider}` | Provider in path | Removes a provider key |
| GET `/routing/traces` | Query options in handler | Returns trace collection |
| GET `/routing/stats` | None | Returns collector statistics |
| POST `/routing/test` | Test payload in handler | Exercises its routing-test path |
| GET `/routing/live` | Query options in handler | Server-sent routing events |

A simple health request, after startup:

```powershell
Invoke-RestMethod http://127.0.0.1:19000/health
```

```bash
curl http://127.0.0.1:19000/health
```

A health response does not establish successful tool execution, model inference, or evidence verification. `/chat` does not call the eleven-stage pipeline or agent tool loop.

## Security boundary

The current bridge has wildcard CORS and no authentication middleware. Its direct tool endpoint does not invoke schema validation or approval checks. Treat it as a local development surface; see [Security](SECURITY.md). Do not publish it as an authenticated service based on the presence of key-management endpoints.

## Qwen ASR training sources

[finetune.py](../src/asr/finetune.py) contains checkpoint discovery, prefix preprocessing, a data collator, trainer adaptation, and a callback that copies model configuration files into checkpoints. [forced_aligner.py](../src/asr/forced_aligner.py) provides forced-alignment classes. [compiler/](../src/asr/compiler/) contains a separate DAG/lowering experiment.

Training JSONL rows use `audio` (local file path), `text` (transcript), and optional `prompt`. A schematic row is:

```json
{"audio": "audio/sample.wav", "text": "Recorded transcript.", "prompt": ""}
```

The training module imports `torch`, `librosa`, `datasets`, `transformers`, and `qwen_asr`. The root requirements do not declare all of them. Provision a compatible Qwen ASR environment and dataset before invoking this interface example:

```bash
python -m src.asr.finetune --model_path /path/to/model --train_file train.jsonl --output_dir ./asr-output --batch_size 1
```

Inspect `parse_args()` for learning rate, gradient accumulation, checkpoint retention, and resume options. No training run, GPU-memory budget, word-error rate, or audio-to-agent pipeline was validated by this documentation update.
