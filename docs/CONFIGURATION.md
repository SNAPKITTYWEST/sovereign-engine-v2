# Configuration Reference

Complete guide to all Sovereign Engine configuration options.

## EngineConfig Dataclass

The `EngineConfig` controls all engine behavior. Pass it to `SovereignEngine()`:

```python
from pathlib import Path
from src.sovereign import EngineConfig, SovereignEngine

config = EngineConfig(
    allowed_roots=[Path("/safe/paths")],
    ledger_path=Path("./sovereign.worm"),
    continuity_dir=Path.home() / ".sovereign" / "continuity",
    max_steps=15,
    enable_shadow=True,
    enable_ipc=True,
    agent_id="sovereign_main"
)
engine = SovereignEngine(config)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `allowed_roots` | `list[Path]` | `[Path.cwd()]` | Filesystem roots the engine can access. PathJail blocks all others. |
| `ledger_path` | `Path` | `./sovereign.worm` | Binary WORM ledger file for cryptographic audit trail. |
| `continuity_dir` | `Path` | `~/.sovereign/continuity` | Directory for all four continuity backends. Auto-created. |
| `max_steps` | `int` | `15` | Max reasoning steps in ReActAgent loop before timeout. |
| `enable_shadow` | `bool` | `True` | Enable ShadowAgent for non-blocking observation. |
| `enable_ipc` | `bool` | `True` | Enable native IPC multiplexer (O(1) tool dispatch). |
| `agent_id` | `str` | `"sovereign_main"` | Unique agent identifier (for multi-agent coordination). |

## Environment Variables

Override config via environment variables (prefixed with `SOVEREIGN_`):

```bash
export SOVEREIGN_ALLOWED_ROOTS="/home/user/projects:/tmp"
export SOVEREIGN_MAX_STEPS=25
export SOVEREIGN_ENABLE_SHADOW=false
export SOVEREIGN_AGENT_ID="batch_processor_1"

python your_script.py
```

Supported environment variables:

| Variable | Type | Maps To |
|----------|------|---------|
| `SOVEREIGN_ALLOWED_ROOTS` | CSV paths | `allowed_roots` (split on `:` or `;`) |
| `SOVEREIGN_LEDGER_PATH` | path | `ledger_path` |
| `SOVEREIGN_CONTINUITY_DIR` | path | `continuity_dir` |
| `SOVEREIGN_MAX_STEPS` | int | `max_steps` |
| `SOVEREIGN_ENABLE_SHADOW` | bool | `enable_shadow` (true/false/1/0) |
| `SOVEREIGN_ENABLE_IPC` | bool | `enable_ipc` |
| `SOVEREIGN_AGENT_ID` | str | `agent_id` |

Example:

```python
import os
from src.sovereign import SovereignEngine

# Environment variables take precedence
if "SOVEREIGN_MAX_STEPS" in os.environ:
    max_steps = int(os.environ["SOVEREIGN_MAX_STEPS"])
else:
    max_steps = 15
```

## ReActAgent Config

The ReAct reasoning agent has its own config:

```python
from src.agents.react import ReActConfig, ReActAgent

react_config = ReActConfig(
    max_steps=20,
    timeout_ms=60000,
    model_provider="bedrock",  # bedrock, openrouter, ollama, anthropic
    temperature=0.7,
    top_p=0.9,
)

agent = ReActAgent(
    agent_id="code_agent",
    config=react_config,
    registry=tool_registry,
    ledger=worm_ledger,
)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_steps` | `int` | `15` | Max thinking/action loops. |
| `timeout_ms` | `int` | `30000` | Total execution timeout. |
| `model_provider` | `str` | `"bedrock"` | LLM backend: bedrock, openrouter, ollama, anthropic. |
| `temperature` | `float` | `0.7` | Sampling temperature (0.0-1.0). |
| `top_p` | `float` | `0.9` | Nucleus sampling parameter. |

## Continuity Directory Structure

The engine uses 4 paradigms for state recovery. Structure:

```
~/.sovereign/continuity/
├── env_state.bin                # Paradigm 1: Env bitmask (for hot-restart)
├── seed.bin                     # Paradigm 2: Seed for deterministic replay
├── agent_id_seed.bin            # Paradigm 2 per-agent seed
├── inode/
│   ├── flags.db                 # Paradigm 3: File handles mapped to boolean gates
│   ├── agent_id.lock
│   └── agent_id.state
├── shm/
│   └── block_0.bin              # Paradigm 4: Shared memory block (4KB)
└── checkpoints/
    ├── checkpoint_001.ckpt      # Full state snapshot with signature
    ├── checkpoint_002.ckpt
    └── manifest.json
```

**Paradigm 1: Env State** — 64-bit bitmask in `os.environ["SOVEREIGN_STATE"]`:
- Fastest (RAM)
- Lost on process exit
- Use for: hot-restart via `os.execv()`

**Paradigm 2: Seed Chain** — Blake2b seed derivation:
- Deterministic replay
- Store operation log in binary
- Use for: replay testing, timeline forking

**Paradigm 3: Inode State** — Zero-byte files as gates:
- Kernel-durable
- Fast stat() reads
- Use for: boolean flags, pause/resume

**Paradigm 4: Shared Memory** — ctypes mmap block:
- Cross-process coordination
- 4KB block
- Use for: multi-agent sync, realtime state

## PathJail Configuration

Restrict filesystem access to approved roots:

```python
from src.core.path_jail import PathJail
from pathlib import Path

jail = PathJail(roots=[
    Path("/home/user/projects"),
    Path("/tmp/scratch"),
    Path.home() / "Downloads"
])

# This is OK
jail.check("/home/user/projects/code.py")  # ✓

# This is BLOCKED
jail.check("/etc/passwd")                   # ✗ PathJailError
jail.check("/root/.ssh/id_rsa")             # ✗ PathJailError
```

Pass to engine:

```python
config = EngineConfig(
    allowed_roots=[
        Path("/home/user/projects"),
        Path("/tmp/scratch"),
    ]
)
engine = SovereignEngine(config)
```

## Model Provider Configuration

Choose which LLM backend to use. Defaults to **AWS Bedrock** (all models via unified API).

### Bedrock (Recommended)

```python
from src.sovereign import EngineConfig
from src.runtime.providers.bedrock import BedrockProvider

config = EngineConfig()
provider = BedrockProvider(
    region="us-west-2",
    model="anthropic.claude-3-opus-20240229-v1:0",
)

# Engine automatically uses it
engine = SovereignEngine(config)
```

Requires `~/.aws/credentials`:
```
[default]
aws_access_key_id = YOUR_KEY
aws_secret_access_key = YOUR_SECRET
region = us-west-2
```

### OpenRouter (Open-source + proprietary models)

```python
from src.runtime.providers.openrouter import OpenRouterProvider

provider = OpenRouterProvider(api_key="sk-or-...")
# Uses OpenRouter API for Mistral, Llama, Qwen, etc.
```

Requires `OPENROUTER_API_KEY` environment variable.

### Ollama (Local models)

```python
from src.runtime.providers.ollama import OllamaProvider

provider = OllamaProvider(base_url="http://localhost:11434")
# Connect to local Ollama instance (ollama serve)
```

Run locally first:
```bash
ollama run mistral
# or
ollama run llama2
```

### Anthropic API (Direct)

```python
from src.runtime.providers.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="sk-ant-...")
```

## Example Configurations

### Development Mode

Minimal logging, fast iteration:

```python
from src.sovereign import EngineConfig
from pathlib import Path
import logging

logging.basicConfig(level=logging.DEBUG)

config = EngineConfig(
    allowed_roots=[Path.cwd()],
    ledger_path=Path("/tmp/dev.worm"),
    continuity_dir=Path("/tmp/continuity"),
    max_steps=10,  # Fast iteration
    enable_shadow=False,
)
```

### Production Mode

Full logging, durability, multi-agent:

```python
config = EngineConfig(
    allowed_roots=[
        Path("/var/app/data"),
        Path("/var/app/cache"),
    ],
    ledger_path=Path("/var/lib/sovereign/ledger.worm"),
    continuity_dir=Path("/var/lib/sovereign/continuity"),
    max_steps=25,  # More thinking
    enable_shadow=True,  # Async observation
    enable_ipc=True,  # Native IPC
    agent_id="prod_reactor_1",
)
```

With Bedrock:

```python
from src.runtime.providers.bedrock import BedrockProvider

provider = BedrockProvider(
    region="us-east-1",
    model="anthropic.claude-3-sonnet-20240229-v1:0",
    timeout_ms=120000,
)
```

### CI Testing Mode

Fast, deterministic, no external calls:

```python
config = EngineConfig(
    allowed_roots=[Path("/tmp/ci_test")],
    ledger_path=Path("/tmp/ci.worm"),
    continuity_dir=Path("/tmp/ci_continuity"),
    max_steps=5,
    enable_shadow=False,
    enable_ipc=False,  # Use pure Python
    agent_id=f"ci_test_{os.getenv('CI_BUILD_ID')}",
)
```

Use mock provider for testing:

```python
from src.runtime.providers.multi import MultiProvider

# Fallback chain: try each in order
provider = MultiProvider([
    MockProvider(),      # Return fixed responses
    OllamaProvider(),   # Fall back to local if available
])
```

## Logging Configuration

Control verbosity via Python logging:

```python
import logging

# Engine logs
logging.getLogger("sovereign.engine").setLevel(logging.INFO)

# Routing pipeline
logging.getLogger("sovereign.routing").setLevel(logging.DEBUG)

# Tool registry
logging.getLogger("sovereign.tools").setLevel(logging.WARNING)

# Everything
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

## Dynamic Configuration Updates

Update config without restarting:

```python
engine = SovereignEngine(config)

# Update max_steps
engine.config.max_steps = 25

# Restart agent with new config
from src.agents.react import ReActConfig
engine.agent.config.max_steps = 25

# Add a new allowed root
engine.config.allowed_roots.append(Path("/new/path"))
engine.path_jail = PathJail(roots=engine.config.allowed_roots)
```

## Configuration Validation

Validate config before starting engine:

```python
from src.sovereign import EngineConfig
from pathlib import Path

config = EngineConfig(
    allowed_roots=[Path("/tmp/test")],
)

# Check roots exist
for root in config.allowed_roots:
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)

# Check continuity dir writable
try:
    config.continuity_dir.mkdir(parents=True, exist_ok=True)
    (config.continuity_dir / ".test").touch()
    (config.continuity_dir / ".test").unlink()
except PermissionError:
    raise RuntimeError(f"Cannot write to {config.continuity_dir}")
```
