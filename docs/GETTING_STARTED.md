# Getting Started with Sovereign Engine

Welcome! This guide will get you running your first agent task in under 10 minutes.

## Prerequisites

- **Python 3.11 or higher** — Check with: `python --version`
- **No external dependencies** — Everything uses Python stdlib (struct, hashlib, asyncio, etc.)
- Optional: NASM (for native assembly compilation)
- Optional: C compiler (for IPC core dispatcher)

## Installation

### Option 1: From Source

```bash
git clone https://github.com/SNAPKITTYWEST/sovereign-reverse.git
cd sovereign-reverse/engine
python -m pip install -e .
```

### Option 2: Install Locally

```bash
cd /path/to/sovereign-reverse/engine
python -m pip install -e .
```

### Verify Installation

```bash
python -c "from src.sovereign import SovereignEngine; print('OK')"
```

## First Run: Hello World

Create a file `hello.py`:

```python
import asyncio
from pathlib import Path
from src.sovereign import SovereignEngine, EngineConfig

async def main():
    # Create engine with default config
    config = EngineConfig(
        allowed_roots=[Path.cwd()],
        continuity_dir=Path.home() / ".sovereign" / "continuity"
    )
    engine = SovereignEngine(config)
    
    # Run a simple task
    result = await engine.run("write a Python function to calculate fibonacci(5)")
    print("\n" + "="*60)
    print("RESULT:")
    print("="*60)
    print(result)
    
    # Clean up
    engine.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
python hello.py
```

You should see output like:

```
2024-08-06 10:15:23,456 - sovereign.engine - INFO - SovereignEngine initialized
2024-08-06 10:15:23,478 - sovereign.engine - INFO - Starting task: write a Python function to calculate fibonacci(5)
...
============================================================
RESULT:
============================================================
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(5))  # Output: 5
```

## Understanding the Output

### WORM Seal

Every task execution is sealed in a **Write-Once Read-Many (WORM)** cryptographic ledger:

```
sovereign.worm                    # Binary append-only file (no text, no injection surface)
  └─ 152-byte header             # Magic + version + timestamps + Blake2b hash + Ed25519 sig
  └─ payload                     # Your task result (binary encoded)
  └─ metadata                    # Execution context (binary encoded)
```

Read the ledger:

```python
from src.core.storage import WORMFile
from pathlib import Path

wf = WORMFile(Path("sovereign.worm"))
for record in wf.scan():
    print(f"Event: {record.event_type}")
    print(f"Timestamp: {record.timestamp_s}")
    print(f"Hash: {record.content_hash.hex()}")
```

### Routing Weights

The engine routes tasks to multiple **experts** (specialized agents). Output shows which experts fired and their contribution:

```
Routing Decision:
  code_generation:    0.65        # 65% contribution
  error_checking:     0.28        # 28% contribution  
  documentation:      0.07        # 7% contribution
```

This is driven by **Jordan algebra**, not softmax:
- Non-associative grouping — expert topology matters
- Fixed-point convergence — stable routing attractors
- Spectral decomposition — provably unique expert selection

### Continuity Directory

Agent state survives restarts across 4 paradigms:

```
~/.sovereign/continuity/
  └─ env_state.bin                # Paradigm 1: 64-bit env bitmask (hot-restart)
  └─ seed.bin                     # Paradigm 2: Blake2b seed for deterministic replay
  └─ inode/
  │   └─ agent_id.state           # Paradigm 3: Zero-byte files as boolean gates
  │   └─ agent_id.lock
  └─ shm_block.bin                # Paradigm 4: Shared memory (cross-process realtime)
  └─ checkpoints/
      └─ checkpoint_1.ckpt        # Full binary snapshot with signature
      └─ checkpoint_2.ckpt
```

## Common First-Time Issues

### Issue: "ModuleNotFoundError: No module named 'src.sovereign'"

**Fix:** Make sure you're in the engine directory and have run `pip install -e .`:

```bash
cd /path/to/sovereign-reverse/engine
python -m pip install -e .
python hello.py
```

### Issue: "PermissionError: Cannot create continuity directory"

**Fix:** The engine needs to write to `~/.sovereign/continuity`. Make sure it exists and is writable:

```bash
mkdir -p ~/.sovereign/continuity
chmod 700 ~/.sovereign/continuity
```

Or use a custom path:

```python
config = EngineConfig(
    continuity_dir=Path("/tmp/my_continuity")
)
```

### Issue: "ValueError: no signature in WORM record"

**Fix:** This is expected if no signing key is configured. The engine defaults to zero-signature (all bytes 0). To use real Ed25519 signing:

```python
from src.core.crypto import generate_signing_key

key = generate_signing_key()
engine = SovereignEngine(config)
# engine will use key internally
```

### Issue: "Timeout: task exceeded 30 seconds"

**Fix:** Increase the max step count or timeout in config:

```python
from src.agents.react import ReActConfig

config = EngineConfig(
    max_steps=25  # More thinking steps
)
engine = SovereignEngine(config)
```

Or in individual agent config:

```python
from src.agents.react import ReActAgent, ReActConfig

react_config = ReActConfig(max_steps=25, timeout_ms=60000)
```

### Issue: "PathJail: denied /path/to/file"

**Fix:** The engine restricts filesystem access to `allowed_roots`. Add your path:

```python
config = EngineConfig(
    allowed_roots=[
        Path("/home/user/projects"),
        Path("/tmp/scratch")
    ]
)
```

## Next Steps

- **[CONFIGURATION.md](CONFIGURATION.md)** — All EngineConfig options with defaults
- **[ROUTING.md](ROUTING.md)** — How the 11-stage pipeline works
- **[TOOLS.md](TOOLS.md)** — Complete tool inventory (34 tools)
- **[CONTINUITY.md](CONTINUITY.md)** — State recovery and replay
- **[SECURITY.md](SECURITY.md)** — PathJail, SSRFGuard, WORM verification

## Production Checklist

Before shipping to production:

- [ ] Set up Ed25519 signing key (see [SECURITY.md](SECURITY.md))
- [ ] Configure `allowed_roots` to restrict filesystem access
- [ ] Enable WORM ledger integrity checks (script in [SECURITY.md](SECURITY.md))
- [ ] Set up continuity directory with proper permissions
- [ ] Test task recovery (kill agent mid-task, restart)
- [ ] Configure rate limits on destructive tools (see [TOOLS.md](TOOLS.md))
- [ ] Enable shadow agent for async observation: `enable_shadow=True`
- [ ] Set appropriate model provider in config (Bedrock/OpenRouter/Ollama)
