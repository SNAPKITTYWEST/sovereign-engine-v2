# Configuration reference

Defaults below come from the source at `898dfbe`. Configuration is split across classes; there is no single loader that maps every `SOVEREIGN_*` variable into engine options.

## EngineConfig

Defined in [src/sovereign.py](../src/sovereign.py).

| Field | Default | Meaning |
|---|---|---|
| `allowed_roots` | `[Path.cwd()]` | Roots passed to the constructed PathJail |
| `ledger_path` | `Path("./sovereign.worm")` | Evidence ledger location |
| `continuity_dir` | `Path.home() / ".sovereign" / "continuity"` | Continuity base directory |
| `max_steps` | `15` | Value passed to ReActConfig |
| `enable_shadow` | `True` | Construct a shadow agent |
| `enable_ipc` | `True` | Construct the native-tool router |
| `agent_id` | `"sovereign_main"` | Agent identifier |

These are constructor fields. The class does not automatically read `SOVEREIGN_MAX_STEPS`, `SOVEREIGN_ALLOWED_ROOTS`, or the other environment overrides listed in the older guide. Constructing a PathJail does not automatically apply it to every registered handler.

## ReActConfig

Defined in [react.py](../src/agents/react.py).

| Field | Default |
|---|---|
| `max_steps` | `10` |
| `reflection_on_error` | `True` |
| `log_to_worm` | `True` |
| `require_approval_for_risky` | `True` |
| `continuity_base_dir` | `Path.home() / ".sovereign" / "continuity"` |
| `enable_continuity` | `True` |

There are no `timeout_ms`, `model_provider`, `temperature`, or `top_p` fields on this dataclass. The agent receives `model`, `tool_registry`, optional `approval_engine`, optional `worm_ledger`, `config`, and `agent_id`. Its run signature is `run(task: Task, initial_context: str | None = None)`.

## RoutingPipeline

The [pipeline constructor](../src/routing/pipeline.py) accepts `experts`, `top_k=2`, optional `routing_nodes`, optional `nand_conflicts`, `merge_strategy="weighted_concat"`, and `expert_timeout_ms=30000`. See [Routing](ROUTING.md) for a runnable callback example.

## Provider and bridge configuration

| Consumer | Setting | Source behavior |
|---|---|---|
| BedrockBackend | `model_id`, `region` constructor arguments | Defaults to the model listed in the root README and `us-east-1`; uses boto3 credentials |
| OllamaProvider | `base_url`, `default_model`, `api_key` | Explicit URL/key or `OLLAMA_BASE_URL` / `OLLAMA_API_KEY`; default model `llama3.2` |
| MultiProvider | `OPENROUTER_API_KEY` or key manager | Adds OpenRouter when configured, then Ollama fallback |
| HTTPBridge | `host`, `port` | Defaults to `127.0.0.1:19000` |
| Electron tool broker | `SOVEREIGN_ENGINE_BRIDGE_URL` | Defaults to `http://127.0.0.1:19000` |
| Electron renderer | `SHADOW_DESKTOP_DEV_URL` | Optional development renderer URL |

The HTTP module entrypoint constructs `HTTPBridge()` directly and does not parse `--host` or `--port`. To change those values, instantiate the class in your own launcher. Neither an `.env` file nor the names in `.env.example` establish that a particular consumer reads a value.

See [bridge contracts](ASR_AND_BRIDGE.md) and [known integration gaps](PRODUCTION_HARDENING.md) before using the orchestration paths.
