"""
Unified Continuity Manager
Part of SOVEREIGN PYTHON LLM ENGINE

Facade over all four continuity paradigms.
Picks the right backend per use case automatically.

Decision matrix:
  Hot restart needed        → EnvStateMachine  (Paradigm 1)
  Deterministic replay      → SeedChain        (Paradigm 2)
  Fast boolean flags        → InodeStateMachine (Paradigm 3)
  Cross-process realtime    → SharedMemoryState (Paradigm 4)
  Full state + crypto chain → CheckpointFile    (binary storage)

Usage:
    cm = ContinuityManager(base_dir=Path("~/.sovereign"), agent_id="react_1")
    cm.transition("IDLE", "THINKING")
    cm.advance_op("THINK:plan task")
    cm.set_step(1)
    state = cm.snapshot()
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .env_state   import EnvStateMachine, DaemonRestarter, FLAG_NAMES
from .seed_state  import SeedChain, SeedLedger, OpLog
from .inode_state import InodeStateMachine, InodeRegistry
from .shared_mem  import SharedStateBlock


# ─────────────────────────────────────────────
# State name → flag index mapping
# ─────────────────────────────────────────────

STATE_FLAGS = {name: idx for idx, name in FLAG_NAMES.items()}

# e.g. STATE_FLAGS["THINKING"] = 1


@dataclass
class ContinuitySnapshot:
    agent_id:     str
    step:         int
    active_states: list[str]
    seed_hash:    bytes
    env_version:  int
    inode_flags:  list[str]
    shm_step:     int


class ContinuityManager:
    """
    Unified continuity manager.

    Manages all four backends simultaneously so agents get:
    - Fast in-memory flag reads  (shared memory)
    - Filesystem-durable flags   (inode state)
    - Env-portable hot restart   (env state)
    - Deterministic replay       (seed chain + op log)
    - Binary audit trail         (CheckpointFile via storage.py)
    """

    def __init__(
        self,
        base_dir: Path,
        agent_id: str,
        enable_shm:   bool = True,
        enable_inode: bool = True,
        enable_env:   bool = True,
        enable_seed:  bool = True,
    ):
        self.agent_id = agent_id
        self.base_dir = base_dir
        base_dir.mkdir(parents=True, exist_ok=True)

        # Paradigm 1: Env state
        self._env: EnvStateMachine | None = None
        if enable_env:
            self._env = EnvStateMachine(agent_id)
            # Restore from env if daemon was restarted
            snapshot = EnvStateMachine.load_from_env()
            if snapshot and snapshot.agent_id == agent_id:
                self._env.restore(snapshot)

        # Paradigm 2: Seed chain
        self._seed: SeedChain | None = None
        self._seed_ledger: SeedLedger | None = None
        self._op_log: OpLog | None = None
        if enable_seed:
            seed_path = base_dir / agent_id / "seed.bin"
            op_path   = base_dir / agent_id / "ops.bin"
            self._seed_ledger = SeedLedger(seed_path)
            self._op_log      = OpLog(op_path)

            loaded = self._seed_ledger.load()
            if loaded:
                seed_int, step = loaded
                ops = self._op_log.read_up_to(step)
                self._seed = SeedChain(seed=seed_int)
                for op in ops:
                    self._seed.advance(op)
            else:
                self._seed = SeedChain()
                self._seed_ledger.save(self._seed)

        # Paradigm 3: Inode state
        self._inode: InodeStateMachine | None = None
        if enable_inode:
            inode_dir = base_dir / "inode"
            self._inode = InodeStateMachine(inode_dir, agent_id)

        # Paradigm 4: Shared memory
        self._shm: SharedStateBlock | None = None
        if enable_shm:
            self._shm = SharedStateBlock(agent_id)

        self._step = 0

    # ─────────────────────────────────────────
    # State transitions
    # ─────────────────────────────────────────

    def transition(self, from_state: str, to_state: str) -> None:
        """
        Transition agent from one state to another across all backends.
        """
        from_flag = STATE_FLAGS.get(from_state.upper())
        to_flag   = STATE_FLAGS.get(to_state.upper())

        if self._env and from_flag is not None and to_flag is not None:
            self._env.transition(
                remove={from_flag},
                add={to_flag}
            )

        if self._inode:
            self._inode.transition(
                remove={from_state.upper()},
                add={to_state.upper()}
            )

        if self._shm and from_flag is not None and to_flag is not None:
            self._shm.clear_flag(from_flag)
            self._shm.set_flag(to_flag)

    def set_states(self, states: set[str]) -> None:
        """Set exact set of active states, clearing all others."""
        flag_indices = {STATE_FLAGS[s.upper()] for s in states if s.upper() in STATE_FLAGS}

        if self._env:
            self._env.set_flags(flag_indices)

        if self._inode:
            self._inode.clear_all()
            for s in states:
                self._inode.set_flag(s.upper())

        if self._shm:
            self._shm.set_flags_from_set(flag_indices)

    # ─────────────────────────────────────────
    # Step management
    # ─────────────────────────────────────────

    def set_step(self, step: int) -> None:
        self._step = step

        if self._env:
            self._env.set_step(step)

        if self._inode:
            self._inode.set_step(step)

        if self._shm:
            self._shm.set_step(step)

    def increment_step(self) -> int:
        self._step += 1
        self.set_step(self._step)
        return self._step

    def get_step(self) -> int:
        return self._step

    # ─────────────────────────────────────────
    # Seed chain operations
    # ─────────────────────────────────────────

    def advance_op(self, op: str) -> bytes:
        """
        Advance the seed chain with an operation.
        Returns the new 32-byte state hash.
        """
        if not self._seed:
            return b'\x00' * 32

        state = self._seed.advance(op)

        if self._op_log:
            self._op_log.append(op)

        if self._seed_ledger:
            self._seed_ledger.save(self._seed)

        return state.state_hash

    def fork_timeline(self, from_step: int | None = None) -> SeedChain:
        """Create a forked timeline from the current seed chain."""
        if not self._seed:
            return SeedChain()
        return self._seed.fork(from_step)

    def current_state_hash(self) -> bytes:
        if not self._seed:
            return b'\x00' * 32
        return self._seed.current_hash

    # ─────────────────────────────────────────
    # Hot restart
    # ─────────────────────────────────────────

    def prepare_restart(self) -> None:
        """Flush all state to env before daemon exec restart."""
        if self._env:
            self._env.set_step(self._step)

    def exec_restart(self) -> None:
        """Hot-restart daemon via os.execv. Does not return."""
        self.prepare_restart()
        DaemonRestarter().exec_restart()

    @property
    def was_restarted(self) -> bool:
        return DaemonRestarter.is_restarted()

    # ─────────────────────────────────────────
    # Snapshot
    # ─────────────────────────────────────────

    def snapshot(self) -> ContinuitySnapshot:
        return ContinuitySnapshot(
            agent_id=self.agent_id,
            step=self._step,
            active_states=self._inode.active_flags() if self._inode else [],
            seed_hash=self._seed.current_hash if self._seed else b'\x00' * 32,
            env_version=self._env.snapshot().version if self._env else 0,
            inode_flags=self._inode.active_flags() if self._inode else [],
            shm_step=self._shm.get_step() if self._shm else 0,
        )

    def cleanup(self) -> None:
        """Remove all inode state. Call on agent completion."""
        if self._inode:
            self._inode.destroy()
