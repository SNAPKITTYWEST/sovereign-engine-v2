"""
Paradigm 4: Cyclic Bitmaps & Shared Memory (ctypes + multiprocessing)
Part of SOVEREIGN PYTHON LLM ENGINE

Zero-copy state sharing between orchestrator and daemon processes.
RAM-speed, no serialization, no disk I/O, no TCP overhead.

Two backends:
  A. ctypes.create_string_buffer()
     - Single process / multiple threads
     - Direct memory pointer sharing
     - Fastest possible: byte mutation at array index

  B. multiprocessing.shared_memory (Python 3.8+ stdlib)
     - Cross-process on same machine
     - Named shared memory block, accessible by name
     - Survives across process restarts (by name)

Memory layout (fixed 4KB block):
  Offset  Size  Field
  0       8     MAGIC = b'SOVSTATE'
  8       8     version (uint64 BE) — incremented on every write
  16      8     agent_id hash (uint64 BE) — FNV-1a of agent_id string
  24      8     step (uint64 BE)
  32      8     timestamp_ns (uint64 BE)
  40      8     bitmask (uint64 BE) — 64 boolean flags
  48      8     sequence (uint64 BE) — monotonic write counter
  56      8     checksum (uint64 BE) — FNV-1a of bytes 0-55
  64      960   payload (raw bytes, caller-defined)
  1024    3072  reserved

Total fixed block = 4096 bytes (one memory page)
"""

from __future__ import annotations

import ctypes
import struct
import time
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

BLOCK_SIZE   = 4096
HEADER_SIZE  = 64
PAYLOAD_SIZE = 960
MAGIC        = b'SOVSTATE'

HDR_FMT      = '>8sQQQQQQQ'   # magic(8) ver(8) id_hash(8) step(8) ts(8) mask(8) seq(8) chk(8)
HDR_BYTES    = struct.calcsize(HDR_FMT)  # should be 64

assert HDR_BYTES == HEADER_SIZE, f"Header size mismatch: {HDR_BYTES}"


# ─────────────────────────────────────────────
# FNV-1a hash (fast, no imports)
# ─────────────────────────────────────────────

def _fnv1a_64(data: bytes) -> int:
    h = 0xcbf29ce484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


# ─────────────────────────────────────────────
# Shared State Block (in-process, ctypes buffer)
# ─────────────────────────────────────────────

class SharedStateBlock:
    """
    Single 4KB memory block for agent state.
    Uses ctypes.create_string_buffer — works within one process
    across threads with no locking needed for reads
    (writes are single-byte atomic on x86/ARM).

    Usage (single process, multiple threads):
        block = SharedStateBlock(agent_id="react_1")
        block.set_flag(2)         # set bit 2
        block.set_step(5)
        block.write_payload(b"custom data")

        # From another thread:
        print(block.get_flags())  # fast bitmask read
        print(block.get_step())
    """

    def __init__(self, agent_id: str, block_size: int = BLOCK_SIZE):
        self._agent_id   = agent_id
        self._id_hash    = _fnv1a_64(agent_id.encode('utf-8'))
        self._version    = 0
        self._sequence   = 0
        self._buf        = ctypes.create_string_buffer(block_size)
        self._block_size = block_size
        self._flush_header(mask=0, step=0)

    def _flush_header(self, mask: int, step: int) -> None:
        self._version  += 1
        self._sequence += 1
        ts = time.time_ns()

        # Build header without checksum first
        hdr_no_chk = struct.pack(
            '>8sQQQQQQ',
            MAGIC,
            self._version,
            self._id_hash,
            step,
            ts,
            mask,
            self._sequence
        )
        checksum = _fnv1a_64(hdr_no_chk)
        hdr = hdr_no_chk + struct.pack('>Q', checksum)

        # Write to ctypes buffer
        self._buf[:HEADER_SIZE] = hdr

    def _read_header(self) -> tuple | None:
        raw = bytes(self._buf[:HEADER_SIZE])
        try:
            (magic, ver, id_hash, step, ts, mask, seq, chk) = struct.unpack(HDR_FMT, raw)
            if magic != MAGIC:
                return None
            # Verify checksum
            expected = _fnv1a_64(raw[:56])
            if chk != expected:
                return None
            return (ver, id_hash, step, ts, mask, seq)
        except Exception:
            return None

    # ── Flag operations ────────────────────────

    def set_flag(self, bit: int) -> None:
        hdr = self._read_header()
        mask = hdr[4] if hdr else 0
        step = hdr[2] if hdr else 0
        mask |= (1 << (bit & 63))
        self._flush_header(mask=mask, step=step)

    def clear_flag(self, bit: int) -> None:
        hdr = self._read_header()
        mask = hdr[4] if hdr else 0
        step = hdr[2] if hdr else 0
        mask &= ~(1 << (bit & 63))
        self._flush_header(mask=mask, step=step)

    def get_flags(self) -> int:
        hdr = self._read_header()
        return hdr[4] if hdr else 0

    def has_flag(self, bit: int) -> bool:
        return bool(self.get_flags() & (1 << (bit & 63)))

    def set_flags_from_set(self, bits: set[int]) -> None:
        mask = sum(1 << (b & 63) for b in bits)
        hdr = self._read_header()
        step = hdr[2] if hdr else 0
        self._flush_header(mask=mask, step=step)

    def active_bits(self) -> set[int]:
        mask = self.get_flags()
        return {i for i in range(64) if mask & (1 << i)}

    # ── Step ────────────────────────────────────

    def set_step(self, step: int) -> None:
        hdr = self._read_header()
        mask = hdr[4] if hdr else 0
        self._flush_header(mask=mask, step=step)

    def get_step(self) -> int:
        hdr = self._read_header()
        return hdr[2] if hdr else 0

    # ── Payload ─────────────────────────────────

    def write_payload(self, data: bytes) -> None:
        n = min(len(data), PAYLOAD_SIZE)
        self._buf[HEADER_SIZE:HEADER_SIZE + n] = data[:n]
        # Zero rest
        if n < PAYLOAD_SIZE:
            self._buf[HEADER_SIZE + n:HEADER_SIZE + PAYLOAD_SIZE] = b'\x00' * (PAYLOAD_SIZE - n)

    def read_payload(self, length: int | None = None) -> bytes:
        n = length if length is not None else PAYLOAD_SIZE
        n = min(n, PAYLOAD_SIZE)
        return bytes(self._buf[HEADER_SIZE:HEADER_SIZE + n])

    # ── Snapshot ────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        hdr = self._read_header()
        if not hdr:
            return {"valid": False}
        ver, id_hash, step, ts, mask, seq = hdr
        return {
            "valid":       True,
            "agent_id":    self._agent_id,
            "version":     ver,
            "step":        step,
            "timestamp_ns": ts,
            "flags_mask":  mask,
            "active_bits": list(self.active_bits()),
            "sequence":    seq,
        }

    def raw_bytes(self) -> bytes:
        return bytes(self._buf[:self._block_size])


# ─────────────────────────────────────────────
# Cross-process shared memory (multiprocessing.shared_memory)
# ─────────────────────────────────────────────

class SharedMemoryState:
    """
    Cross-process state block using Python 3.8+ multiprocessing.shared_memory.

    The memory block is identified by name — any process on the same
    machine can attach to it by name.

    Survives process restarts: if the block already exists,
    the new process attaches and reads existing state.

    Usage:
        # Process A (orchestrator)
        sm = SharedMemoryState("sovereign_react_1", create=True)
        sm.set_step(5)
        sm.set_flag(2)

        # Process B (daemon) — attaches to existing block
        sm2 = SharedMemoryState("sovereign_react_1", create=False)
        print(sm2.get_step())   # 5
        print(sm2.has_flag(2))  # True
    """

    def __init__(self, name: str, create: bool = True, size: int = BLOCK_SIZE):
        from multiprocessing import shared_memory

        self._name = name
        self._size = size

        try:
            if create:
                try:
                    self._shm = shared_memory.SharedMemory(name=name, create=True, size=size)
                    # Initialize with zeros
                    self._shm.buf[:size] = b'\x00' * size
                except FileExistsError:
                    # Already exists — attach
                    self._shm = shared_memory.SharedMemory(name=name, create=False, size=size)
            else:
                self._shm = shared_memory.SharedMemory(name=name, create=False, size=size)
        except Exception as e:
            # Fallback to ctypes buffer if shared memory unavailable
            self._shm = None
            self._fallback = ctypes.create_string_buffer(size)
            self._fallback_mode = True
            return

        self._fallback_mode = False

    def _read(self, offset: int, length: int) -> bytes:
        if self._fallback_mode:
            return bytes(self._fallback[offset:offset + length])
        return bytes(self._shm.buf[offset:offset + length])

    def _write(self, offset: int, data: bytes) -> None:
        if self._fallback_mode:
            self._fallback[offset:offset + len(data)] = data
        else:
            self._shm.buf[offset:offset + len(data)] = data

    def set_step(self, step: int) -> None:
        self._write(24, struct.pack('>Q', step))

    def get_step(self) -> int:
        raw = self._read(24, 8)
        return struct.unpack('>Q', raw)[0]

    def set_flag(self, bit: int) -> None:
        raw = self._read(40, 8)
        mask = struct.unpack('>Q', raw)[0]
        mask |= (1 << (bit & 63))
        self._write(40, struct.pack('>Q', mask))

    def clear_flag(self, bit: int) -> None:
        raw = self._read(40, 8)
        mask = struct.unpack('>Q', raw)[0]
        mask &= ~(1 << (bit & 63))
        self._write(40, struct.pack('>Q', mask))

    def has_flag(self, bit: int) -> bool:
        raw = self._read(40, 8)
        mask = struct.unpack('>Q', raw)[0]
        return bool(mask & (1 << (bit & 63)))

    def get_flags(self) -> int:
        raw = self._read(40, 8)
        return struct.unpack('>Q', raw)[0]

    def write_payload(self, data: bytes) -> None:
        n = min(len(data), PAYLOAD_SIZE)
        self._write(HEADER_SIZE, data[:n])

    def read_payload(self, length: int | None = None) -> bytes:
        n = length if length is not None else PAYLOAD_SIZE
        return self._read(HEADER_SIZE, min(n, PAYLOAD_SIZE))

    def close(self) -> None:
        if not self._fallback_mode and self._shm:
            self._shm.close()

    def unlink(self) -> None:
        if not self._fallback_mode and self._shm:
            self._shm.unlink()

    @property
    def name(self) -> str:
        return self._name
