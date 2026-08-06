"""
Native IPC Tool Router — Zero-copy shared memory dispatch
Part of SOVEREIGN PYTHON LLM ENGINE

Bypasses the HTTP bridge for local tool execution.  The C dispatcher
(native/dispatcher/ipc_core.c) and this Python worker share the same
named memory-mapped region so tool calls never cross a socket.

Ring buffer layout (64 KiB default):
  ┌──────────────────────────────────────────┐  offset 0
  │  Dispatch header  (12 bytes)             │
  │    magic[4]  b'DISP'                     │
  │    opcode    uint16 big-endian           │
  │    flags     uint16 big-endian           │
  │    plen      uint32 big-endian           │
  ├──────────────────────────────────────────┤  offset 12
  │  Payload   (variable, up to 1012 bytes)  │
  ├──────────────────────────────────────────┤  offset 1024
  │  Response header (12 bytes)              │
  │    magic[4]  b'RESP'                     │
  │    status    uint16 big-endian (0=ok)    │
  │    flags     uint16 big-endian           │
  │    rlen      uint32 big-endian           │
  ├──────────────────────────────────────────┤  offset 1036
  │  Response payload (variable)             │
  └──────────────────────────────────────────┘

Flag bits (dispatch):
  0x0001  ASYNC  — caller does not wait for response
  0x0002  ACK    — worker should set ack bit in flags before processing

Flag bits (response):
  0x0001  ERROR  — payload contains UTF-8 error string
  0x0002  TRUNC  — response was truncated to fit the buffer

Platform notes:
  Windows  — uses mmap.mmap(-1, size, tagname=name) (named section object)
  POSIX    — uses /dev/shm/name via os.open + mmap.mmap(fd, size)
  Both paths produce an identical memory view; only the open call differs.

Checksum:
  Fletcher-16 over the payload bytes.  Chosen for speed (two 8-bit
  accumulators, no multiplication) and reasonable error coverage.
"""

from __future__ import annotations

import asyncio
import json
import mmap
import os
import struct
import sys
import time
import logging
from typing import Any, Callable, Awaitable

from .opcode_registry import (
    OPCODE_TABLE,
    TOOL_OPCODES,
    get_opcode as _static_get_opcode,
    get_tool_id as _static_get_tool_id,
    register_dynamic,
    list_opcodes,
)
from .registry import ToolRegistry

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DISP_MAGIC        = b'DISP'
RESP_MAGIC        = b'RESP'

# Header format: magic(4s) opcode(H) flags(H) payload_len(I) — 12 bytes, big-endian
HEADER_FMT        = '>4sHHI'
HEADER_SIZE: int  = struct.calcsize(HEADER_FMT)   # 12

RESPONSE_OFFSET   = 1024                           # response starts at byte 1024
MAX_PAYLOAD       = RESPONSE_OFFSET - HEADER_SIZE  # 1012 bytes max inbound payload
MAX_RESPONSE      = 63 * 1024                      # 63 KiB max response (64K buf - 1K dispatch slot)

# Default shared memory region size
DEFAULT_SHM_SIZE  = 65536  # 64 KiB

# Dispatch flags
FLAG_ASYNC        = 0x0001
FLAG_ACK          = 0x0002

# Response flags
RFLAG_ERROR       = 0x0001
RFLAG_TRUNC       = 0x0002

# Poll interval — 500 µs expressed in seconds for asyncio.sleep
POLL_INTERVAL_S   = 0.0005

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Fletcher-16 checksum
# ─────────────────────────────────────────────────────────────────────────────

def _fletcher16(data: bytes) -> int:
    """Compute Fletcher-16 checksum over *data*.  Returns 16-bit integer."""
    a = 0
    b = 0
    for byte in data:
        a = (a + byte) % 255
        b = (b + a) % 255
    return (b << 8) | a


# ─────────────────────────────────────────────────────────────────────────────
# Shared memory helpers — platform-specific open/create
# ─────────────────────────────────────────────────────────────────────────────

def _open_shm(name: str, size: int) -> mmap.mmap:
    """
    Open or create a named shared memory region of *size* bytes.

    Windows:  uses CreateFileMapping via mmap.mmap(-1, size, tagname=name)
    POSIX:    creates /dev/shm/<name> and maps it
    """
    if sys.platform == 'win32':
        # tagname= maps to a Windows named section object.
        # ACCESS_WRITE is the default when no access kwarg is given.
        shm = mmap.mmap(-1, size, tagname=name)
        return shm

    # POSIX path
    shm_path = '/dev/shm/' + name
    flags = os.O_CREAT | os.O_RDWR
    fd = os.open(shm_path, flags, 0o600)
    try:
        os.ftruncate(fd, size)
        shm = mmap.mmap(fd, size)
    finally:
        # fd can be closed after mmap — the mapping keeps the region alive
        os.close(fd)
    return shm


def _close_shm(shm: mmap.mmap, name: str) -> None:
    """Close and (on POSIX) unlink the shared memory region."""
    try:
        shm.close()
    except Exception:
        pass

    if sys.platform != 'win32':
        shm_path = '/dev/shm/' + name
        try:
            os.unlink(shm_path)
        except FileNotFoundError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# NativeToolRouter
# ─────────────────────────────────────────────────────────────────────────────

class NativeToolRouter:
    """
    Zero-copy IPC tool dispatcher backed by a shared memory ring buffer.

    Opcodes are 16-bit integers that map directly to tool handlers without
    any string lookup on the hot path.  The opcode → handler array is a
    plain Python list so dispatch is a single index operation.

    Typical usage
    -------------
    router = NativeToolRouter("sovereign_disp")
    router.assign_opcodes(registry)          # wire up all 34 tools
    await router.poll_dispatch_loop()        # blocks — run in task

    For direct (in-process) calls without the shared memory path:
    result_bytes = await router.dispatch(0x0001, payload_bytes)
    """

    # ── Slot capacity: 16-bit opcode space ────────────────────────────────────
    _SLOT_COUNT = 0x10000  # 65536

    def __init__(self, shm_name: str, registry_size: int = DEFAULT_SHM_SIZE):
        """
        Initialise the router and attach to shared memory.

        Args:
            shm_name:      Name of the shared memory region.  On Windows this
                           becomes a named section object; on POSIX it becomes
                           /dev/shm/<shm_name>.
            registry_size: Size in bytes of the shared memory region.
                           Must be at least RESPONSE_OFFSET + 12 (= 1036).
        """
        if registry_size < RESPONSE_OFFSET + HEADER_SIZE:
            raise ValueError(
                f"registry_size must be >= {RESPONSE_OFFSET + HEADER_SIZE} bytes"
            )

        self._name          = shm_name
        self._size          = registry_size

        # Handler table — indexed by opcode for O(1) lookup.
        # Slot 0 is reserved (null opcode).  Unregistered slots are None.
        self._handlers: list[Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None] = \
            [None] * self._SLOT_COUNT

        # opcode ↔ tool_id mirrors (extend opcode_registry at runtime)
        self._opcode_to_id: dict[int, str] = {}
        self._id_to_opcode: dict[str, int] = {}

        # Running flag — set to False to stop poll_dispatch_loop()
        self._running = False

        # Dispatch counter for diagnostics
        self._dispatch_count = 0

        # Lazy SHM — opened on first use of poll_dispatch_loop or explicit open()
        self._shm: mmap.mmap | None = None

        logger.debug("NativeToolRouter created (shm=%s, size=%d)", shm_name, registry_size)

    # ── Shared memory lifecycle ────────────────────────────────────────────────

    def open(self) -> None:
        """Open / attach to the shared memory region.  Idempotent."""
        if self._shm is not None:
            return
        self._shm = _open_shm(self._name, self._size)
        # Zero the dispatch header so the C core sees a clean slate
        self._shm.seek(0)
        self._shm.write(b'\x00' * HEADER_SIZE)
        self._shm.flush()
        logger.info("Opened shared memory: %s (%d bytes)", self._name, self._size)

    def close(self) -> None:
        """Stop the dispatch loop and release shared memory."""
        self._running = False
        if self._shm is not None:
            _close_shm(self._shm, self._name)
            self._shm = None
        logger.info("Closed shared memory: %s", self._name)

    # ── Registration ──────────────────────────────────────────────────────────

    def register_opcode(
        self,
        opcode: int,
        tool_id: str,
        func: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
    ) -> None:
        """
        Bind a callable to an opcode.

        Args:
            opcode:  16-bit opcode (0x0001-0xFFFF; 0x0000 is reserved)
            tool_id: Fully-qualified tool identifier string
            func:    Async callable with signature (dict) -> dict

        Raises:
            ValueError: If opcode is 0x0000 or > 0xFFFF
        """
        if opcode == 0 or opcode > 0xFFFF:
            raise ValueError(f"Opcode must be in range 0x0001-0xFFFF, got 0x{opcode:04X}")

        self._handlers[opcode] = func
        self._opcode_to_id[opcode] = tool_id
        self._id_to_opcode[tool_id] = opcode
        logger.debug("Registered opcode 0x%04X → %s", opcode, tool_id)

    def assign_opcodes(self, tool_registry: ToolRegistry) -> dict[str, int]:
        """
        Auto-assign 16-bit opcodes to every tool in *tool_registry*.

        Tools whose tool_id appears in the static OPCODE_TABLE get their
        pre-assigned opcode.  Unknown tools get the next dynamic opcode
        via opcode_registry.register_dynamic().

        Args:
            tool_registry: Populated ToolRegistry instance

        Returns:
            Mapping of tool_id → assigned opcode for all registered tools
        """
        assignments: dict[str, int] = {}

        for tool_def in tool_registry.list_all():
            tid = tool_def.tool_id

            # Resolve opcode — static first, then dynamic
            if tid in TOOL_OPCODES:
                opcode = TOOL_OPCODES[tid]
            else:
                opcode = register_dynamic(tid)

            self.register_opcode(opcode, tid, tool_def.handler)
            assignments[tid] = opcode

        logger.info(
            "assign_opcodes: wired %d tools into opcode table", len(assignments)
        )
        return assignments

    # ── Encoding / decoding ───────────────────────────────────────────────────

    def encode_call(self, opcode: int, args: dict[str, Any]) -> bytes:
        """
        Encode a tool call into a binary IPC frame.

        Frame layout:
          Header (12 bytes): magic(4) opcode(2) flags(2) payload_len(4)
          Payload: JSON-encoded args (UTF-8)

        The overall frame must fit within MAX_PAYLOAD + HEADER_SIZE (1024)
        bytes so it lands entirely within the dispatch half of the buffer.

        Args:
            opcode: 16-bit opcode
            args:   Argument dictionary (JSON-serialisable)

        Returns:
            Packed bytes ready to write into shared memory at offset 0

        Raises:
            ValueError: If the encoded payload exceeds MAX_PAYLOAD bytes
        """
        payload = json.dumps(args, separators=(',', ':')).encode('utf-8')

        if len(payload) > MAX_PAYLOAD:
            raise ValueError(
                f"Encoded args too large: {len(payload)} bytes "
                f"(max {MAX_PAYLOAD})"
            )

        header = struct.pack(HEADER_FMT, DISP_MAGIC, opcode, 0, len(payload))
        return header + payload

    def decode_response(self, raw: bytes) -> dict[str, Any]:
        """
        Decode a response frame read from the shared memory response slot.

        Frame layout (starting at RESPONSE_OFFSET):
          Header (12 bytes): magic(4) status(2) flags(2) rlen(4)
          Payload: JSON-encoded result (UTF-8)

        Args:
            raw: Bytes starting at RESPONSE_OFFSET (must be >= HEADER_SIZE)

        Returns:
            Decoded result dictionary

        Raises:
            ValueError: On bad magic, truncated frame, or JSON decode error
        """
        if len(raw) < HEADER_SIZE:
            raise ValueError(f"Response frame too short: {len(raw)} bytes")

        magic, status, flags, rlen = struct.unpack_from(HEADER_FMT, raw, 0)

        if magic != RESP_MAGIC:
            raise ValueError(
                f"Bad response magic: {magic!r} (expected {RESP_MAGIC!r})"
            )

        body = raw[HEADER_SIZE: HEADER_SIZE + rlen]

        if len(body) < rlen:
            raise ValueError(
                f"Response body truncated: got {len(body)} bytes, "
                f"expected {rlen}"
            )

        if flags & RFLAG_ERROR:
            error_msg = body.decode('utf-8', errors='replace')
            return {"ok": False, "error": error_msg, "status": status}

        try:
            result = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Response JSON decode failed: {exc}") from exc

        return {"ok": True, "result": result, "status": status}

    # ── Direct dispatch (in-process, no SHM) ─────────────────────────────────

    async def dispatch(self, opcode: int, payload: bytes) -> bytes:
        """
        Dispatch a tool call directly without going through shared memory.

        This is the hot path for in-process callers.  The handler is invoked
        directly using the opcode table (no string lookup).

        Args:
            opcode:  16-bit opcode
            payload: JSON-encoded argument bytes

        Returns:
            Encoded response bytes (same layout as the SHM response slot)

        Raises:
            KeyError:  If no handler is registered for *opcode*
            Exception: Propagated from the tool handler
        """
        handler = self._handlers[opcode] if 0 <= opcode < self._SLOT_COUNT else None

        if handler is None:
            error_msg = f"No handler for opcode 0x{opcode:04X}"
            rlen = len(error_msg)
            return struct.pack(HEADER_FMT, RESP_MAGIC, 1, RFLAG_ERROR, rlen) + \
                   error_msg.encode('utf-8')

        try:
            args: dict[str, Any] = json.loads(payload.decode('utf-8')) if payload else {}
        except json.JSONDecodeError as exc:
            error_msg = f"Payload JSON decode failed: {exc}"
            rlen = len(error_msg)
            return struct.pack(HEADER_FMT, RESP_MAGIC, 2, RFLAG_ERROR, rlen) + \
                   error_msg.encode('utf-8')

        try:
            result = await handler(args)
        except Exception as exc:
            error_msg = f"Handler error for 0x{opcode:04X}: {exc}"
            logger.exception("Handler error for opcode 0x%04X", opcode)
            rlen = len(error_msg)
            return struct.pack(HEADER_FMT, RESP_MAGIC, 3, RFLAG_ERROR, rlen) + \
                   error_msg.encode('utf-8')

        self._dispatch_count += 1

        try:
            body = json.dumps(result, separators=(',', ':')).encode('utf-8')
        except (TypeError, ValueError) as exc:
            error_msg = f"Result JSON encode failed: {exc}"
            rlen = len(error_msg)
            return struct.pack(HEADER_FMT, RESP_MAGIC, 4, RFLAG_ERROR, rlen) + \
                   error_msg.encode('utf-8')

        flags = RFLAG_TRUNC if len(body) > MAX_RESPONSE else 0
        body = body[:MAX_RESPONSE]
        return struct.pack(HEADER_FMT, RESP_MAGIC, 0, flags, len(body)) + body

    # ── Shared memory poll loop ───────────────────────────────────────────────

    async def poll_dispatch_loop(self) -> None:
        """
        Sub-millisecond shared memory poll loop.

        Opens shared memory if not already open, then spins polling the
        dispatch header at offset 0.  When a packet with magic == b'DISP'
        and opcode != 0 is detected, the tool is dispatched and the
        response is written at RESPONSE_OFFSET.  The dispatch header is
        then zeroed so the C side sees the slot is free.

        Stops when self._running is set to False (call close() or set it
        directly from another task).

        This coroutine yields to the event loop between polls via
        asyncio.sleep(POLL_INTERVAL_S) so other tasks remain responsive.
        """
        if self._shm is None:
            self.open()

        self._running = True
        logger.info(
            "poll_dispatch_loop started (shm=%s, interval=%.3f ms)",
            self._name, POLL_INTERVAL_S * 1000
        )

        while self._running:
            # Read header — 12 bytes at offset 0
            self._shm.seek(0)
            raw_header = self._shm.read(HEADER_SIZE)

            if len(raw_header) < HEADER_SIZE:
                await asyncio.sleep(POLL_INTERVAL_S)
                continue

            magic, opcode, flags, plen = struct.unpack(HEADER_FMT, raw_header)

            if magic != DISP_MAGIC or opcode == 0:
                # No pending packet — yield and re-poll
                await asyncio.sleep(POLL_INTERVAL_S)
                continue

            # ── ACK immediately so the C side knows we saw the packet ──────
            if flags & FLAG_ACK:
                self._shm.seek(6)  # flags field offset within header
                self._shm.write(struct.pack('>H', flags | 0x8000))  # set bit 15 as ack
                self._shm.flush()

            # Read payload
            payload_len = min(plen, MAX_PAYLOAD)
            self._shm.seek(HEADER_SIZE)
            payload = self._shm.read(payload_len)

            # ── Clear dispatch slot so C side can submit the next call ─────
            self._shm.seek(0)
            self._shm.write(b'\x00' * HEADER_SIZE)
            self._shm.flush()

            # ── Dispatch ──────────────────────────────────────────────────
            t0 = time.monotonic_ns()
            response_bytes = await self.dispatch(opcode, payload)
            elapsed_us = (time.monotonic_ns() - t0) // 1000

            logger.debug(
                "Dispatched opcode 0x%04X plen=%d → rlen=%d in %d µs",
                opcode, payload_len, len(response_bytes), elapsed_us
            )

            # ── Write response ─────────────────────────────────────────────
            # Truncate to available response space
            max_resp = self._size - RESPONSE_OFFSET
            resp_data = response_bytes[:max_resp]

            self._shm.seek(RESPONSE_OFFSET)
            self._shm.write(resp_data)
            self._shm.flush()

        logger.info("poll_dispatch_loop stopped")

    # ── SHM write helper (for callers that send calls via SHM) ───────────────

    def write_call(self, opcode: int, args: dict[str, Any]) -> None:
        """
        Encode and write a call frame to the shared memory dispatch slot.

        The C dispatcher (or another process) can then read the packet,
        while this process's poll_dispatch_loop handles the other direction.

        Typically used in tests or by the daemon bridge.

        Args:
            opcode: 16-bit opcode
            args:   Argument dictionary (JSON-serialisable)

        Raises:
            RuntimeError: If shared memory is not open (call open() first)
        """
        if self._shm is None:
            raise RuntimeError("Shared memory not open — call open() first")

        frame = self.encode_call(opcode, args)
        self._shm.seek(0)
        self._shm.write(frame)
        self._shm.flush()

    def read_response(self) -> dict[str, Any] | None:
        """
        Read and decode the response from the shared memory response slot.

        Returns None if no response is available yet (magic != b'RESP').

        Returns:
            Decoded response dict, or None if slot is empty
        """
        if self._shm is None:
            raise RuntimeError("Shared memory not open — call open() first")

        self._shm.seek(RESPONSE_OFFSET)
        raw = self._shm.read(HEADER_SIZE)

        if len(raw) < HEADER_SIZE:
            return None

        magic = raw[:4]
        if magic != RESP_MAGIC:
            return None

        _, _, _, rlen = struct.unpack(HEADER_FMT, raw)

        self._shm.seek(RESPONSE_OFFSET)
        full_resp = self._shm.read(HEADER_SIZE + rlen)

        return self.decode_response(full_resp)

    # ── Opcode introspection ──────────────────────────────────────────────────

    def get_opcode(self, tool_id: str) -> int | None:
        """
        Return the opcode registered for *tool_id*, or None if not found.

        Searches the router's local table first (which may include tools
        registered via assign_opcodes but not in the static table), then
        falls back to the static opcode_registry.

        Args:
            tool_id: Fully-qualified tool identifier

        Returns:
            16-bit opcode integer, or None
        """
        if tool_id in self._id_to_opcode:
            return self._id_to_opcode[tool_id]
        try:
            return _static_get_opcode(tool_id)
        except KeyError:
            return None

    def get_tool_id(self, opcode: int) -> str | None:
        """
        Return the tool_id registered for *opcode*, or None if not found.

        Args:
            opcode: 16-bit opcode

        Returns:
            tool_id string, or None
        """
        if opcode in self._opcode_to_id:
            return self._opcode_to_id[opcode]
        try:
            return _static_get_tool_id(opcode)
        except KeyError:
            return None

    def opcode_table(self) -> dict[int, str]:
        """
        Return a snapshot of the complete opcode → tool_id mapping for
        this router instance (local registrations only).

        Returns:
            Dict mapping opcode integers to tool_id strings
        """
        return dict(self._opcode_to_id)

    # ── Diagnostics ───────────────────────────────────────────────────────────

    @property
    def dispatch_count(self) -> int:
        """Total successful dispatches since this instance was created."""
        return self._dispatch_count

    @property
    def is_open(self) -> bool:
        """True if the shared memory region is currently open."""
        return self._shm is not None

    @property
    def is_running(self) -> bool:
        """True if poll_dispatch_loop() is actively polling."""
        return self._running

    def stats(self) -> dict[str, Any]:
        """
        Return a diagnostic snapshot.

        Returns:
            Dict with shm_name, size, registered_tools, dispatch_count,
            is_open, is_running, platform
        """
        return {
            "shm_name":        self._name,
            "size_bytes":      self._size,
            "registered_tools": len(self._opcode_to_id),
            "dispatch_count":  self._dispatch_count,
            "is_open":         self.is_open,
            "is_running":      self.is_running,
            "platform":        sys.platform,
            "header_size":     HEADER_SIZE,
            "response_offset": RESPONSE_OFFSET,
            "max_payload":     MAX_PAYLOAD,
            "max_response":    MAX_RESPONSE,
            "poll_interval_ms": POLL_INTERVAL_S * 1000,
        }

    def __repr__(self) -> str:
        return (
            f"NativeToolRouter(shm={self._name!r}, "
            f"tools={len(self._opcode_to_id)}, "
            f"open={self.is_open})"
        )

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "NativeToolRouter":
        self.open()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
