# Continuity and recovery

[ContinuityManager](../src/continuity/manager.py) coordinates environment flags, a seed chain and operation log, inode flags, and shared memory. Its public operations are synchronous.

| Backend | Source | What it stores |
|---|---|---|
| Environment | [env_state.py](../src/continuity/env_state.py) | Flags and step information for an inherited process environment |
| Seed | [seed_state.py](../src/continuity/seed_state.py) | Seed state and operations under `<base>/<agent>/seed.bin` and `ops.bin` |
| Inodes | [inode_state.py](../src/continuity/inode_state.py) | Filesystem flags under `<base>/inode` |
| Shared memory | [shared_mem.py](../src/continuity/shared_mem.py) | Shared block state, with platform-specific fallback |

## Local example: isolated state transitions

This example disables shared memory, environment state, and seed persistence so it can demonstrate the manager without altering process environment or leaving persistent state.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from src.continuity.manager import ContinuityManager

with TemporaryDirectory() as directory:
    manager = ContinuityManager(
        base_dir=Path(directory), agent_id="docs_example",
        enable_shm=False, enable_env=False, enable_seed=False,
    )
    manager.set_states({"IDLE"})
    manager.transition("IDLE", "THINKING")
    manager.set_step(1)
    snapshot = manager.snapshot()
    assert snapshot.step == 1
    assert "THINKING" in snapshot.inode_flags
    print(snapshot.active_states)
    manager.cleanup()
```

## Recovery interfaces

`advance_op(text)` updates the enabled seed chain and log. `prepare_restart()` copies the current step into environment state. `exec_restart()` replaces the process using `os.execv`; do not use it as a harmless inspection method.

`snapshot()` returns a dataclass, not a durable snapshot file. `cleanup()` removes inode state; it is not a general close/delete operation for every backend. SharedStateBlock has separate `close()` and `unlink()` methods.

A new manager initializes its local step counter to zero. Do not assume reopening its directory restores every field or proves crash recovery. Validate the exact backend and lifecycle used by your application.

## Integration boundary

The manager does not define `create_task`, `mark_complete`, or `mark_failed`, although the current unified engine calls those names. ReAct construction catches continuity initialization exceptions and can continue with continuity disabled. Inspect `agent.continuity` and test persistence explicitly before relying on it.

[checkpoint.py](../src/continuity/checkpoint.py) and [replay.py](../src/continuity/replay.py) provide additional mechanisms; their existence is separate from a demonstrated recovery path in the unified engine.
