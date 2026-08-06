"""
Paradigm 1: Unix Environment State Machine
Part of SOVEREIGN PYTHON LLM ENGINE

Agent state persisted in OS environment variables and inherited file
descriptors. The kernel holds the state — zero disk I/O.

Two mechanisms:
  A. EnvStateMachine   — serialize/deserialize agent state as bitmask env var
  B. DaemonRestarter   — hot-restart a daemon via os.execv, passing state
                         through the process environment so the replacement
                         process inherits full context with no disk read

Bitmask encoding:
  State flags packed into a single base64url string stored in
  SOVEREIGN_STATE env var. Each flag is one bit. Up to 64 flags
  in a single 8-byte (uint64) integer.

  Example:
    THINKING=0, ACTING=1, OBSERVING=2, REFLECTING=3, DONE=4, ERROR=5
    Active flags {ACTING, OBSERVING} → bitmask = 0b000110 = 6
    Encoded: SOVEREIGN_STATE=AAAAAAAAAAY=
"""

from __future__ import annotations

import base64
import os
import struct
import sys
from dataclasses import dataclass, field
from typing import Any


# ─────────────────────────────────────────────
# Bitmask state encoding
# ─────────────────────────────────────────────

ENV_KEY          = "SOVEREIGN_STATE"
ENV_META_KEY     = "SOVEREIGN_META"
ENV_AGENT_KEY    = "SOVEREIGN_AGENT_ID"
ENV_STEP_KEY     = "SOVEREIGN_STEP"
ENV_VERSION_KEY  = "SOVEREIGN_VERSION"

# Built-in flag indices (0-based bit positions)
FLAG_IDLE        = 0
FLAG_THINKING    = 1
FLAG_ACTING      = 2
FLAG_OBSERVING   = 3
FLAG_REFLECTING  = 4
FLAG_DONE        = 5
FLAG_ERROR       = 6

FLAG_NAMES = {
    FLAG_IDLE:       "IDLE",
    FLAG_THINKING:   "THINKING",
    FLAG_ACTING:     "ACTING",
    FLAG_OBSERVING:  "OBSERVING",
    FLAG_REFLECTING: "REFLECTING",
    FLAG_DONE:       "DONE",
    FLAG_ERROR:      "ERROR",
}


def _encode_bitmask(flags: set[int]) -> str:
    """Encode set of flag indices → base64url string (8 bytes)."""
    mask = 0
    for f in flags:
        if 0 <= f < 64:
            mask |= (1 << f)
    return base64.urlsafe_b64encode(struct.pack('>Q', mask)).decode('ascii')


def _decode_bitmask(encoded: str) -> set[int]:
    """Decode base64url string → set of active flag indices."""
    try:
        raw = base64.urlsafe_b64decode(encoded.encode('ascii'))
        mask = struct.unpack('>Q', raw[:8])[0]
        return {i for i in range(64) if mask & (1 << i)}
    except Exception:
        return set()


# ─────────────────────────────────────────────
# Env State Machine
# ─────────────────────────────────────────────

@dataclass
class EnvSnapshot:
    agent_id:   str
    step:       int
    flags:      set[int]
    version:    int
    raw_env:    dict[str, str] = field(default_factory=dict)

    def flag_names(self) -> list[str]:
        return [FLAG_NAMES.get(f, f"FLAG_{f}") for f in sorted(self.flags)]

    def has_flag(self, flag: int) -> bool:
        return flag in self.flags


class EnvStateMachine:
    """
    Persist agent state in process environment variables.

    State survives across os.execv() restarts because child processes
    inherit the parent's environment. No disk I/O required.

    Usage:
        esm = EnvStateMachine(agent_id="react_1")
        esm.set_flags({FLAG_THINKING})
        esm.set_step(5)

        # On daemon restart via exec:
        snapshot = EnvStateMachine.load_from_env()
        if snapshot:
            esm.restore(snapshot)
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._flags: set[int] = {FLAG_IDLE}
        self._step: int = 0
        self._version: int = 0

    # ── Write ──────────────────────────────────

    def set_flags(self, flags: set[int]) -> None:
        self._flags = flags
        self._flush()

    def add_flag(self, flag: int) -> None:
        self._flags.add(flag)
        self._flush()

    def remove_flag(self, flag: int) -> None:
        self._flags.discard(flag)
        self._flush()

    def set_step(self, step: int) -> None:
        self._step = step
        self._flush()

    def transition(self, remove: set[int], add: set[int]) -> None:
        self._flags -= remove
        self._flags |= add
        self._version += 1
        self._flush()

    def _flush(self) -> None:
        os.environ[ENV_KEY]         = _encode_bitmask(self._flags)
        os.environ[ENV_AGENT_KEY]   = self.agent_id
        os.environ[ENV_STEP_KEY]    = str(self._step)
        os.environ[ENV_VERSION_KEY] = str(self._version)

    # ── Read ───────────────────────────────────

    @staticmethod
    def load_from_env(env: dict[str, str] | None = None) -> EnvSnapshot | None:
        """
        Load snapshot from current process environment (or supplied dict).
        Returns None if no state found in environment.
        """
        e = env if env is not None else dict(os.environ)
        encoded = e.get(ENV_KEY)
        if not encoded:
            return None

        return EnvSnapshot(
            agent_id=e.get(ENV_AGENT_KEY, "unknown"),
            step=int(e.get(ENV_STEP_KEY, "0")),
            flags=_decode_bitmask(encoded),
            version=int(e.get(ENV_VERSION_KEY, "0")),
            raw_env={k: v for k, v in e.items() if k.startswith("SOVEREIGN_")}
        )

    def restore(self, snapshot: EnvSnapshot) -> None:
        self._flags   = snapshot.flags
        self._step    = snapshot.step
        self._version = snapshot.version
        self._flush()

    def snapshot(self) -> EnvSnapshot:
        return EnvSnapshot(
            agent_id=self.agent_id,
            step=self._step,
            flags=set(self._flags),
            version=self._version
        )

    # ── Properties ─────────────────────────────

    @property
    def current_flags(self) -> set[int]:
        return set(self._flags)

    @property
    def step(self) -> int:
        return self._step

    @property
    def is_idle(self)      -> bool: return FLAG_IDLE      in self._flags
    @property
    def is_thinking(self)  -> bool: return FLAG_THINKING  in self._flags
    @property
    def is_acting(self)    -> bool: return FLAG_ACTING    in self._flags
    @property
    def is_done(self)      -> bool: return FLAG_DONE      in self._flags
    @property
    def is_error(self)     -> bool: return FLAG_ERROR     in self._flags


# ─────────────────────────────────────────────
# Daemon hot-restart via execv
# ─────────────────────────────────────────────

class DaemonRestarter:
    """
    Hot-restart a Python daemon via os.execv, passing state through
    the process environment. The replacement process starts with full
    context inherited — zero disk reads required.

    Usage:
        restarter = DaemonRestarter()

        # Before restart — flush state to env
        esm.set_step(current_step)
        esm.set_flags(current_flags)

        # Restart — replaces current process image
        restarter.exec_restart()

        # In new process — check for inherited state
        snapshot = EnvStateMachine.load_from_env()
        if snapshot:
            print(f"Resumed from step {snapshot.step}")
    """

    RESTART_FLAG = "SOVEREIGN_RESTARTED"

    def exec_restart(
        self,
        argv: list[str] | None = None,
        extra_env: dict[str, str] | None = None
    ) -> None:
        """
        Replace current process with fresh copy of same script.
        State in os.environ is inherited automatically.

        Args:
            argv: Command to exec (defaults to current sys.argv)
            extra_env: Additional env vars to set before exec
        """
        os.environ[self.RESTART_FLAG] = "1"
        if extra_env:
            os.environ.update(extra_env)

        args = argv or sys.argv
        executable = sys.executable

        # os.execv replaces current process — no return
        os.execv(executable, [executable] + args)

    @staticmethod
    def is_restarted() -> bool:
        return os.environ.get(DaemonRestarter.RESTART_FLAG) == "1"

    @staticmethod
    def clear_restart_flag() -> None:
        os.environ.pop(DaemonRestarter.RESTART_FLAG, None)


# ─────────────────────────────────────────────
# Pipe-based state transfer (parent→child)
# ─────────────────────────────────────────────

class PipeStateTransfer:
    """
    Transfer agent state to child process via inherited pipe fd.
    Child reads state from fd before doing any work.

    Parent:
        pst = PipeStateTransfer()
        pid, fd_write = pst.spawn_with_state(cmd, state_bytes)

    Child (reads from fd 3 by convention):
        state_bytes = PipeStateTransfer.read_from_fd(3)
    """

    STATE_FD = 3  # fd 3 by convention (0=stdin, 1=stdout, 2=stderr)

    def spawn_with_state(
        self,
        cmd: list[str],
        state_bytes: bytes
    ) -> tuple[int, int]:
        """
        Spawn child process, passing state_bytes via inherited pipe.

        Returns:
            (pid, write_fd) — write_fd is the write end (parent owns it)
        """
        import subprocess

        r_fd, w_fd = os.pipe()

        # Write state to pipe before spawning
        os.write(w_fd, struct.pack('>I', len(state_bytes)))
        os.write(w_fd, state_bytes)

        proc = subprocess.Popen(
            cmd,
            close_fds=False,          # allow fd inheritance
            pass_fds=(r_fd,)
        )

        os.close(r_fd)  # parent closes read end
        return proc.pid, w_fd

    @staticmethod
    def read_from_fd(fd: int = STATE_FD) -> bytes | None:
        """
        Child reads state from inherited fd.
        Returns None if fd not available.
        """
        try:
            length_bytes = os.read(fd, 4)
            if len(length_bytes) < 4:
                return None
            length = struct.unpack('>I', length_bytes)[0]
            data = b''
            while len(data) < length:
                chunk = os.read(fd, length - len(data))
                if not chunk:
                    break
                data += chunk
            os.close(fd)
            return data if len(data) == length else None
        except OSError:
            return None
