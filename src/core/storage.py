"""
Binary append-only storage using Python struct.
Part of SOVEREIGN PYTHON LLM ENGINE

Two record types:
  WORMRecord    — evidence ledger entries  (magic b'WORM')
  CheckpointRec — agent state checkpoints  (magic b'CKPT')

Format philosophy:
  - Pure Python stdlib: struct, hashlib, pathlib, io
  - Fixed-width binary headers — no text, no injection surface
  - Append-only file mode ('ab') — OS enforces it
  - Every record self-describing — magic + version + lengths
  - Reader scans forward only — corrupt tail = truncate, not corrupt head
  - Zero external deps

WORM Record wire layout (152 bytes fixed header + variable body):
  Offset  Len  Type        Field
  0       4    bytes       MAGIC = b'WORM'
  4       1    uint8       VERSION = 1
  5       1    uint8       FLAGS (reserved, 0x00)
  6       2    uint16 BE   event_type length
  8       4    uint32 BE   payload length
  12      4    uint32 BE   metadata length
  16      8    uint64 BE   timestamp (unix nanoseconds)
  24      32   bytes       prev_hash (zeros if first record)
  56      32   bytes       content_hash (blake2b-256 of payload)
  88      64   bytes       signature (Ed25519, or zeros if no key)
  152     var  utf-8       event_type string
  152+E   var  bytes       payload
  152+E+P var  bytes       metadata (caller-encoded, raw bytes)

Checkpoint Record wire layout (128 bytes fixed header + variable body):
  Offset  Len  Type        Field
  0       4    bytes       MAGIC = b'CKPT'
  4       1    uint8       VERSION = 1
  5       1    uint8       FLAGS (reserved, 0x00)
  6       2    uint16 BE   checkpoint_id length
  8       2    uint16 BE   agent_id length
  10      2    uint16 BE   prev_id length (0 if first)
  12      4    uint32 BE   state length
  16      8    uint64 BE   step number
  24      8    uint64 BE   timestamp (unix nanoseconds)
  32      32   bytes       content_hash (blake2b-256 of state)
  64      64   bytes       signature (Ed25519, or zeros if no key)
  128     var  utf-8       checkpoint_id
  128+C   var  utf-8       agent_id
  128+C+A var  utf-8       prev_id
  128+C+A+V var bytes      state (raw bytes, caller encodes)
"""

from __future__ import annotations

import hashlib
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

WORM_MAGIC   = b'WORM'
CKPT_MAGIC   = b'CKPT'
VERSION      = 0x01
FLAGS        = 0x00
ZERO_HASH    = b'\x00' * 32
ZERO_SIG     = b'\x00' * 64

# struct format strings (big-endian)
# WORM fixed header: magic(4) ver(1) flags(1) elen(2) dlen(4) mlen(4) ts(8) prev(32) hash(32) sig(64)
WORM_HDR_FMT  = '>4sBBHIIQ32s32s64s'
WORM_HDR_SIZE = struct.calcsize(WORM_HDR_FMT)   # 152

# CKPT fixed header: magic(4) ver(1) flags(1) cid_len(2) aid_len(2) pid_len(2) slen(4) step(8) ts(8) hash(32) sig(64)
CKPT_HDR_FMT  = '>4sBBHHHIQQ32s64s'
CKPT_HDR_SIZE = struct.calcsize(CKPT_HDR_FMT)   # 128

assert WORM_HDR_SIZE == 152, f"WORM header size mismatch: {WORM_HDR_SIZE}"
assert CKPT_HDR_SIZE == 128, f"CKPT header size mismatch: {CKPT_HDR_SIZE}"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _now_ns() -> int:
    return time.time_ns()

def _blake2b(data: bytes) -> bytes:
    return hashlib.blake2b(data, digest_size=32).digest()

def _sign(signing_key, data: bytes) -> bytes:
    if signing_key is None:
        return ZERO_SIG
    try:
        return signing_key.sign(data)[:64]
    except Exception:
        return ZERO_SIG


# ─────────────────────────────────────────────
# WORM Record
# ─────────────────────────────────────────────

@dataclass
class WORMRecord:
    event_type:   str
    payload:      bytes
    metadata:     bytes          # raw bytes — caller decides encoding
    timestamp_ns: int
    prev_hash:    bytes          # 32 bytes
    content_hash: bytes          # 32 bytes blake2b of payload
    signature:    bytes          # 64 bytes Ed25519 (or zeros)

    @property
    def timestamp_s(self) -> float:
        return self.timestamp_ns / 1_000_000_000


class WORMFile:
    """
    Append-only binary WORM ledger.

    Usage:
        wf = WORMFile(Path("ledger.worm"), signing_key=key)
        wf.append("tool_call", b"raw payload", b"meta bytes")
        for record in wf.scan():
            print(record.event_type)
    """

    def __init__(self, path: Path, signing_key=None):
        self.path = path
        self.signing_key = signing_key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash: bytes = ZERO_HASH
        self._record_count: int = 0
        self._init_chain()

    def _init_chain(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        # Scan to find last hash — only reads headers
        for rec in self.scan():
            self._last_hash = rec.content_hash
            self._record_count += 1

    def append(
        self,
        event_type: str,
        payload: bytes,
        metadata: bytes = b''
    ) -> WORMRecord:
        event_bytes  = event_type.encode('utf-8')
        ts           = _now_ns()
        content_hash = _blake2b(payload)

        # Sign: prev_hash || content_hash || timestamp_ns || event_type
        sign_input = (
            self._last_hash +
            content_hash +
            struct.pack('>Q', ts) +
            event_bytes
        )
        sig = _sign(self.signing_key, sign_input)

        hdr = struct.pack(
            WORM_HDR_FMT,
            WORM_MAGIC,
            VERSION,
            FLAGS,
            len(event_bytes),
            len(payload),
            len(metadata),
            ts,
            self._last_hash,
            content_hash,
            sig
        )

        # 'ab' — append binary, atomic at OS level
        with open(self.path, 'ab') as f:
            f.write(hdr)
            f.write(event_bytes)
            f.write(payload)
            f.write(metadata)

        rec = WORMRecord(
            event_type=event_type,
            payload=payload,
            metadata=metadata,
            timestamp_ns=ts,
            prev_hash=self._last_hash,
            content_hash=content_hash,
            signature=sig
        )
        self._last_hash = content_hash
        self._record_count += 1
        return rec

    def scan(self) -> Iterator[WORMRecord]:
        if not self.path.exists():
            return
        with open(self.path, 'rb') as f:
            while True:
                hdr_bytes = f.read(WORM_HDR_SIZE)
                if not hdr_bytes:
                    break
                if len(hdr_bytes) < WORM_HDR_SIZE:
                    break  # truncated tail — stop cleanly

                (magic, ver, flags, elen, dlen, mlen,
                 ts, prev_hash, content_hash, sig) = struct.unpack(
                    WORM_HDR_FMT, hdr_bytes
                )

                if magic != WORM_MAGIC:
                    break  # corrupt record — stop

                event_bytes = f.read(elen)
                payload     = f.read(dlen)
                metadata    = f.read(mlen)

                if len(event_bytes) < elen or len(payload) < dlen:
                    break  # truncated body

                yield WORMRecord(
                    event_type=event_bytes.decode('utf-8', errors='replace'),
                    payload=payload,
                    metadata=metadata,
                    timestamp_ns=ts,
                    prev_hash=prev_hash,
                    content_hash=content_hash,
                    signature=sig
                )

    def verify_chain(self) -> tuple[bool, int]:
        """
        Verify hash chain integrity.
        Returns (is_valid, records_checked).
        Does NOT verify signatures (requires public key).
        """
        prev = ZERO_HASH
        count = 0
        for rec in self.scan():
            if rec.prev_hash != prev:
                return False, count
            expected = _blake2b(rec.payload)
            if rec.content_hash != expected:
                return False, count
            prev = rec.content_hash
            count += 1
        return True, count

    def scan_by_type(self, event_type: str) -> Iterator[WORMRecord]:
        for rec in self.scan():
            if rec.event_type == event_type:
                yield rec

    def count(self) -> int:
        return self._record_count

    @property
    def last_hash(self) -> bytes:
        return self._last_hash


# ─────────────────────────────────────────────
# Checkpoint Record
# ─────────────────────────────────────────────

@dataclass
class CheckpointRecord:
    checkpoint_id: str
    agent_id:      str
    prev_id:       str           # empty string if first
    state:         bytes         # raw bytes — caller encodes
    step:          int
    timestamp_ns:  int
    content_hash:  bytes         # 32 bytes blake2b of state
    signature:     bytes         # 64 bytes

    @property
    def timestamp_s(self) -> float:
        return self.timestamp_ns / 1_000_000_000


class CheckpointFile:
    """
    Append-only binary checkpoint store.

    One file per agent: {agent_id}.ckpt
    Records are append-only — old checkpoints are never overwritten.

    Usage:
        cf = CheckpointFile(Path("checkpoints/agent_1.ckpt"), signing_key=key)
        cf.append("ckpt_uuid", "agent_1", "", state_bytes, step=0)
        for rec in cf.scan():
            print(rec.checkpoint_id, rec.step)
    """

    def __init__(self, path: Path, signing_key=None):
        self.path = path
        self.signing_key = signing_key
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        checkpoint_id: str,
        agent_id:      str,
        prev_id:       str,
        state:         bytes,
        step:          int
    ) -> CheckpointRecord:
        cid_bytes  = checkpoint_id.encode('utf-8')
        aid_bytes  = agent_id.encode('utf-8')
        pid_bytes  = prev_id.encode('utf-8')
        ts         = _now_ns()
        content_hash = _blake2b(state)

        sign_input = (
            cid_bytes +
            aid_bytes +
            struct.pack('>QQ', step, ts) +
            content_hash
        )
        sig = _sign(self.signing_key, sign_input)

        hdr = struct.pack(
            CKPT_HDR_FMT,
            CKPT_MAGIC,
            VERSION,
            FLAGS,
            len(cid_bytes),
            len(aid_bytes),
            len(pid_bytes),
            len(state),
            step,
            ts,
            content_hash,
            sig
        )

        with open(self.path, 'ab') as f:
            f.write(hdr)
            f.write(cid_bytes)
            f.write(aid_bytes)
            f.write(pid_bytes)
            f.write(state)

        return CheckpointRecord(
            checkpoint_id=checkpoint_id,
            agent_id=agent_id,
            prev_id=prev_id,
            state=state,
            step=step,
            timestamp_ns=ts,
            content_hash=content_hash,
            signature=sig
        )

    def scan(self) -> Iterator[CheckpointRecord]:
        if not self.path.exists():
            return
        with open(self.path, 'rb') as f:
            while True:
                hdr_bytes = f.read(CKPT_HDR_SIZE)
                if not hdr_bytes:
                    break
                if len(hdr_bytes) < CKPT_HDR_SIZE:
                    break

                (magic, ver, flags, cid_len, aid_len, pid_len,
                 slen, step, ts, content_hash, sig) = struct.unpack(
                    CKPT_HDR_FMT, hdr_bytes
                )

                if magic != CKPT_MAGIC:
                    break

                cid_bytes = f.read(cid_len)
                aid_bytes = f.read(aid_len)
                pid_bytes = f.read(pid_len)
                state     = f.read(slen)

                if len(state) < slen:
                    break

                yield CheckpointRecord(
                    checkpoint_id=cid_bytes.decode('utf-8', errors='replace'),
                    agent_id=aid_bytes.decode('utf-8', errors='replace'),
                    prev_id=pid_bytes.decode('utf-8', errors='replace'),
                    state=state,
                    step=step,
                    timestamp_ns=ts,
                    content_hash=content_hash,
                    signature=sig
                )

    def get_by_id(self, checkpoint_id: str) -> CheckpointRecord | None:
        for rec in self.scan():
            if rec.checkpoint_id == checkpoint_id:
                return rec
        return None

    def get_by_step(self, step: int) -> CheckpointRecord | None:
        for rec in self.scan():
            if rec.step == step:
                return rec
        return None

    def get_latest(self) -> CheckpointRecord | None:
        last = None
        for rec in self.scan():
            last = rec
        return last

    def list_ids(self) -> list[tuple[str, int]]:
        """Returns list of (checkpoint_id, step) pairs."""
        return [(rec.checkpoint_id, rec.step) for rec in self.scan()]

    def verify_chain(self) -> tuple[bool, int]:
        count = 0
        for rec in self.scan():
            expected = _blake2b(rec.state)
            if rec.content_hash != expected:
                return False, count
            count += 1
        return True, count
