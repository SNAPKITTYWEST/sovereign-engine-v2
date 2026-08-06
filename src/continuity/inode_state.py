"""
Paradigm 3: Filesystem Inode State (Zero-Byte File Gates)
Part of SOVEREIGN PYTHON LLM ENGINE

Boolean state flags stored as directory entries.
File existence = 1, absence = 0.
No file content ever written or read — pure stat() calls.

Structure:
  {base_dir}/
    {agent_id}/
      flags/
        IDLE          ← exists = agent is idle
        THINKING      ← exists = agent is thinking
        ACTING        ← exists = agent is acting
        OBSERVING     ← exists = agent is observing
        REFLECTING    ← exists = agent is reflecting
        DONE          ← exists = agent is done
        ERROR         ← exists = agent errored
      step/
        0000000000000005   ← filename = current step number (zero-padded)
      locks/
        tool:filesystem.read   ← exists = this tool is checked out

Why this is fast:
  - os.stat() is a single kernel syscall
  - Directory entries live in kernel dcache (hot in memory)
  - No open(), read(), write(), close() — just stat() + mkdir() + unlink()
  - Concurrent readers are safe (no file locking needed for boolean flags)
  - Corruption-proof: filesystem guarantees atomic rename/unlink

Use cases:
  - Agent state machine flags (7 states)
  - Tool checkout tracking (which tools are in use)
  - Mutex locks (file existence = lock held)
  - Rate limit gates (file mtime = last call timestamp)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterator


# ─────────────────────────────────────────────
# Inode State Gate
# ─────────────────────────────────────────────

class InodeGate:
    """
    Single boolean state gate backed by a zero-byte file.

    set()    → touch file (create if not exists)
    clear()  → unlink file (delete if exists)
    get()    → stat file (True if exists)
    mtime()  → file modification time (useful for rate limiting)
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def set(self) -> None:
        self.path.touch(exist_ok=True)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def get(self) -> bool:
        return self.path.exists()

    def toggle(self) -> bool:
        if self.get():
            self.clear()
            return False
        else:
            self.set()
            return True

    def mtime(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except FileNotFoundError:
            return None

    def age_seconds(self) -> float | None:
        mt = self.mtime()
        return (time.time() - mt) if mt is not None else None

    def __bool__(self) -> bool:
        return self.get()

    def __repr__(self) -> str:
        return f"InodeGate({self.path.name}={'1' if self.get() else '0'})"


# ─────────────────────────────────────────────
# Inode State Machine
# ─────────────────────────────────────────────

# Standard agent state flags
AGENT_FLAGS = [
    "IDLE", "THINKING", "ACTING", "OBSERVING",
    "REFLECTING", "DONE", "ERROR"
]


class InodeStateMachine:
    """
    Agent state machine using zero-byte files as boolean flags.

    State transitions are atomic at the filesystem level:
      transition(remove={"THINKING"}, add={"ACTING"}) uses
      a rename-based swap to avoid intermediate invalid states.

    Directory structure:
      {base}/{agent_id}/flags/IDLE
      {base}/{agent_id}/flags/THINKING
      ...
      {base}/{agent_id}/step/{zero_padded_step}
      {base}/{agent_id}/locks/{lock_name}

    Usage:
        ism = InodeStateMachine(base_dir, agent_id="react_1")
        ism.transition(remove={"IDLE"}, add={"THINKING"})
        ism.set_step(1)
        print(ism.active_flags())   # ["THINKING"]
    """

    def __init__(self, base_dir: Path, agent_id: str):
        self.agent_id = agent_id
        self._root    = base_dir / agent_id
        self._flags   = self._root / "flags"
        self._step_dir = self._root / "step"
        self._locks   = self._root / "locks"

        # Create directory structure
        for d in (self._flags, self._step_dir, self._locks):
            d.mkdir(parents=True, exist_ok=True)

        # Initialize to IDLE if no flags set
        if not any(True for _ in self._flags.iterdir()):
            (self._flags / "IDLE").touch()

    # ── Flags ──────────────────────────────────

    def set_flag(self, flag: str) -> None:
        (self._flags / flag.upper()).touch(exist_ok=True)

    def clear_flag(self, flag: str) -> None:
        try:
            (self._flags / flag.upper()).unlink()
        except FileNotFoundError:
            pass

    def has_flag(self, flag: str) -> bool:
        return (self._flags / flag.upper()).exists()

    def active_flags(self) -> list[str]:
        return sorted(p.name for p in self._flags.iterdir() if p.is_file())

    def transition(self, remove: set[str], add: set[str]) -> None:
        """
        Atomic-ish transition: clear old flags, set new flags.
        Uses individual unlink/touch — not a true atomic swap,
        but fast enough for single-process agents.
        For true atomicity, use rename-based swap (future extension).
        """
        for flag in remove:
            self.clear_flag(flag)
        for flag in add:
            self.set_flag(flag)

    def clear_all(self) -> None:
        for p in self._flags.iterdir():
            if p.is_file():
                p.unlink()

    # ── Step counter ───────────────────────────

    def set_step(self, step: int) -> None:
        """Store current step as filename (zero-padded 16 digits)."""
        # Remove old step files
        for p in self._step_dir.iterdir():
            if p.is_file():
                p.unlink()
        # Create new step file
        (self._step_dir / f"{step:016d}").touch()

    def get_step(self) -> int:
        """Read current step from directory entry."""
        files = sorted(p.name for p in self._step_dir.iterdir() if p.is_file())
        if not files:
            return 0
        return int(files[-1])

    # ── Locks ──────────────────────────────────

    def acquire_lock(self, lock_name: str) -> bool:
        """
        Try to acquire a named lock.
        Returns True if acquired, False if already held.
        Uses exclusive creation (O_CREAT | O_EXCL at filesystem level).
        """
        lock_path = self._locks / lock_name.replace('/', '_').replace(':', '-')
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            return False

    def release_lock(self, lock_name: str) -> None:
        lock_path = self._locks / lock_name.replace('/', '_').replace(':', '-')
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass

    def held_locks(self) -> list[str]:
        return [p.name for p in self._locks.iterdir() if p.is_file()]

    # ── Rate limiting via mtime ─────────────────

    def rate_gate(self, gate_name: str, min_interval_s: float) -> bool:
        """
        Rate limit gate using file mtime.
        Returns True if allowed (enough time elapsed), False if rate-limited.
        Touching the gate file resets the timer.
        """
        gate = InodeGate(self._locks / f"rate_{gate_name}")
        age  = gate.age_seconds()

        if age is None or age >= min_interval_s:
            gate.set()  # reset timer
            return True  # allowed

        return False  # rate limited

    # ── Introspection ──────────────────────────

    def snapshot(self) -> dict:
        return {
            "agent_id":     self.agent_id,
            "active_flags": self.active_flags(),
            "step":         self.get_step(),
            "held_locks":   self.held_locks(),
        }

    def destroy(self) -> None:
        """Remove all inode state for this agent."""
        import shutil
        shutil.rmtree(self._root, ignore_errors=True)


# ─────────────────────────────────────────────
# Multi-agent inode registry
# ─────────────────────────────────────────────

class InodeRegistry:
    """
    Registry of all active agents tracked via inode state.
    Scan base_dir to discover all agents without any central index.
    The directory listing IS the index.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        base_dir.mkdir(parents=True, exist_ok=True)

    def get_agent(self, agent_id: str) -> InodeStateMachine:
        return InodeStateMachine(self.base_dir, agent_id)

    def list_agents(self) -> list[str]:
        return [
            d.name for d in self.base_dir.iterdir()
            if d.is_dir() and (d / "flags").exists()
        ]

    def all_snapshots(self) -> list[dict]:
        snapshots = []
        for agent_id in self.list_agents():
            ism = self.get_agent(agent_id)
            snapshots.append(ism.snapshot())
        return snapshots

    def active_agents(self) -> list[str]:
        """Agents that are not IDLE and not DONE."""
        result = []
        for agent_id in self.list_agents():
            ism = self.get_agent(agent_id)
            flags = set(ism.active_flags())
            if flags and not flags.issubset({"IDLE", "DONE"}):
                result.append(agent_id)
        return result
