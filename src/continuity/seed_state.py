"""
Paradigm 2: Functional Seed Continuity
Part of SOVEREIGN PYTHON LLM ENGINE

Instead of storing what happened, store HOW TO GET THERE.

Core idea:
  - Every agent state transition is a deterministic function of a seed
  - History compresses to: (seed: int, step: int)
  - To restore state at step N: evaluate f(seed, 0..N)
  - Entire ledger = one 64-bit integer + one 64-bit counter

Two components:

  SeedChain:
    Deterministic PRNG chain. Each step derives next state from
    current state via BLAKE2b(seed || step || operation).
    Output is a 256-bit hash used as the next state vector.

  SeedLedger:
    Minimal persistence — stores only (seed, step, checksum) in
    a 24-byte binary flat file. No JSONL, no struct chains.
    Recovery = re-derive from step 0 to current step.

  OperationLog:
    Stores the SEQUENCE of operations (not their full state).
    Operations are short codes: "THINK", "ACT:tool_id", "OBS", etc.
    Combined with seed, fully deterministic replay is possible
    for pure-math agents (routing pipeline, constraint eval, etc.)

Caveat (Ahmad's note):
  Works perfectly for deterministic subsystems:
    - MoE routing pipeline (pure math)
    - Constraint evaluation
    - Symbolic graph / Jordan analysis
    - State machine transitions

  For LLM calls (non-deterministic):
    Cache model outputs alongside the operation log.
    Seed continuity handles everything else;
    model outputs are the only non-reproducible artifact.
"""

from __future__ import annotations

import hashlib
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# ─────────────────────────────────────────────
# Seed derivation
# ─────────────────────────────────────────────

def _derive(seed: int, step: int, op: bytes) -> bytes:
    """
    Derive next state hash from seed + step + operation.
    Pure function — same inputs always produce same output.
    """
    h = hashlib.blake2b(
        struct.pack('>QQ', seed, step) + op,
        digest_size=32
    )
    return h.digest()


def _derive_seed(seed: int, step: int, op: bytes) -> int:
    """Derive next seed integer."""
    raw = _derive(seed, step, op)
    return struct.unpack('>Q', raw[:8])[0]


# ─────────────────────────────────────────────
# Seed Chain
# ─────────────────────────────────────────────

@dataclass
class ChainState:
    seed:       int
    step:       int
    state_hash: bytes   # 32-byte current state vector
    op:         str     # operation that produced this state


class SeedChain:
    """
    Deterministic state chain driven by a single 64-bit seed.

    Each transition:
      new_state = BLAKE2b(current_seed || step || op_bytes)

    The chain is:
      - Deterministic: same seed + same ops = same history
      - Compact: full history = (initial_seed, [ops])
      - Verifiable: any step can be recomputed from scratch
      - Fork-able: different op sequences from same seed = different timelines

    Usage:
        chain = SeedChain(seed=0xDEADBEEFCAFEBABE)
        chain.advance("THINK")
        chain.advance("ACT:filesystem.read")
        chain.advance("OBS")

        # Serialize to 8 bytes
        seed_bytes = chain.export_seed()

        # Restore — re-derive to current step
        chain2 = SeedChain.from_seed(seed_bytes, ops=chain.ops)
        assert chain2.current_hash == chain.current_hash
    """

    def __init__(self, seed: int | None = None):
        if seed is None:
            seed = struct.unpack('>Q', hashlib.blake2b(
                struct.pack('>Q', time.time_ns()), digest_size=8
            ).digest())[0]

        self._initial_seed = seed
        self._seed         = seed
        self._step         = 0
        self._state_hash   = _derive(seed, 0, b'INIT')
        self._ops: list[str] = []

    def advance(self, op: str) -> ChainState:
        op_bytes = op.encode('utf-8')
        self._seed       = _derive_seed(self._seed, self._step, op_bytes)
        self._step      += 1
        self._state_hash = _derive(self._seed, self._step, op_bytes)
        self._ops.append(op)

        return ChainState(
            seed=self._seed,
            step=self._step,
            state_hash=self._state_hash,
            op=op
        )

    def state_at(self, step: int) -> bytes:
        """Recompute state hash at a specific step (O(step) recomputation)."""
        seed = self._initial_seed
        state = _derive(seed, 0, b'INIT')
        for i, op in enumerate(self._ops[:step]):
            op_bytes = op.encode('utf-8')
            seed  = _derive_seed(seed, i, op_bytes)
            state = _derive(seed, i + 1, op_bytes)
        return state

    def fork(self, from_step: int | None = None) -> 'SeedChain':
        """
        Create a new chain branching from a given step.
        The fork shares history up to from_step, then diverges.
        """
        step = from_step if from_step is not None else self._step
        new_chain = SeedChain(seed=self._initial_seed)
        for op in self._ops[:step]:
            new_chain.advance(op)
        return new_chain

    def export_seed(self) -> bytes:
        """Export initial seed as 8 bytes."""
        return struct.pack('>Q', self._initial_seed)

    def export_compact(self) -> bytes:
        """
        Export minimal recovery payload: initial_seed(8) + step(8).
        Ops must be stored separately to enable full replay.
        """
        return struct.pack('>QQ', self._initial_seed, self._step)

    @classmethod
    def from_seed(cls, seed_bytes: bytes, ops: list[str] | None = None) -> 'SeedChain':
        seed = struct.unpack('>Q', seed_bytes[:8])[0]
        chain = cls(seed=seed)
        for op in (ops or []):
            chain.advance(op)
        return chain

    @property
    def current_hash(self) -> bytes:
        return self._state_hash

    @property
    def current_seed(self) -> int:
        return self._seed

    @property
    def step(self) -> int:
        return self._step

    @property
    def ops(self) -> list[str]:
        return list(self._ops)

    @property
    def initial_seed(self) -> int:
        return self._initial_seed


# ─────────────────────────────────────────────
# Seed Ledger — 24-byte flat file
# ─────────────────────────────────────────────

# Layout: initial_seed(8) | current_step(8) | checksum(8)
SEED_LEDGER_SIZE = 24
SEED_LEDGER_FMT  = '>QQQ'


class SeedLedger:
    """
    Minimal persistence for seed continuity.

    Stores only 24 bytes on disk:
      - initial_seed (8 bytes)
      - current_step (8 bytes)
      - checksum     (8 bytes, first 8 of BLAKE2b(seed || step))

    Recovery: read seed + step, re-derive from ops log.
    The ops log is stored separately (OpLog) or reconstructed
    from the WORM binary ledger.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, chain: SeedChain) -> None:
        seed = chain.initial_seed
        step = chain.step
        checksum_raw = hashlib.blake2b(
            struct.pack('>QQ', seed, step), digest_size=8
        ).digest()
        checksum = struct.unpack('>Q', checksum_raw)[0]

        with open(self.path, 'wb') as f:
            f.write(struct.pack(SEED_LEDGER_FMT, seed, step, checksum))

    def load(self) -> tuple[int, int] | None:
        """
        Returns (initial_seed, step) or None if file missing/corrupt.
        """
        if not self.path.exists():
            return None
        try:
            raw = self.path.read_bytes()
            if len(raw) < SEED_LEDGER_SIZE:
                return None
            seed, step, stored_checksum = struct.unpack(SEED_LEDGER_FMT, raw[:24])
            # Verify checksum
            expected_raw = hashlib.blake2b(
                struct.pack('>QQ', seed, step), digest_size=8
            ).digest()
            expected = struct.unpack('>Q', expected_raw)[0]
            if stored_checksum != expected:
                return None
            return seed, step
        except Exception:
            return None

    def file_size(self) -> int:
        return SEED_LEDGER_SIZE  # always 24 bytes


# ─────────────────────────────────────────────
# Operation Log — compact op sequence store
# ─────────────────────────────────────────────

class OpLog:
    """
    Append-only log of operation codes.
    Stored as length-prefixed UTF-8 strings in a binary flat file.

    Format per entry:
      length(2 bytes uint16 BE) | op_string(utf-8)

    Combined with SeedLedger, enables full deterministic replay.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, op: str) -> None:
        op_bytes = op.encode('utf-8')
        with open(self.path, 'ab') as f:
            f.write(struct.pack('>H', len(op_bytes)))
            f.write(op_bytes)

    def read_all(self) -> list[str]:
        if not self.path.exists():
            return []
        ops = []
        with open(self.path, 'rb') as f:
            while True:
                length_bytes = f.read(2)
                if not length_bytes or len(length_bytes) < 2:
                    break
                length = struct.unpack('>H', length_bytes)[0]
                op_bytes = f.read(length)
                if len(op_bytes) < length:
                    break
                ops.append(op_bytes.decode('utf-8', errors='replace'))
        return ops

    def read_up_to(self, step: int) -> list[str]:
        return self.read_all()[:step]

    def count(self) -> int:
        return len(self.read_all())
