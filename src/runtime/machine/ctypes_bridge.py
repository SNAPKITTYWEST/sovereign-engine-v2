"""
ctypes_bridge.py — Low-level ctypes bridge for C interop.

Provides typed struct definitions, function bindings, memory arenas,
and C string handling for the sovereign engine's native layer.

Part of the SOVEREIGN_IR PYTHON_C_BRIDGE_IR pipeline.
Agent A (Cognition) — HyperKittyConstraintDSL v1.0
"""

from __future__ import annotations

import ctypes
import ctypes.util
import io
import math
import platform
import struct
import sys
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

class Platform(Enum):
    X86_64  = "x86_64"
    ARM64   = "arm64"
    X86_32  = "x86_32"
    UNKNOWN = "unknown"


class Endian(Enum):
    LITTLE = "little"
    BIG    = "big"


def detect_platform() -> Platform:
    machine = platform.machine().lower()
    if machine in ('x86_64', 'amd64'):
        return Platform.X86_64
    elif machine in ('aarch64', 'arm64'):
        return Platform.ARM64
    elif machine in ('i386', 'i686', 'x86'):
        return Platform.X86_32
    return Platform.UNKNOWN


def detect_endian() -> Endian:
    if sys.byteorder == 'little':
        return Endian.LITTLE
    return Endian.BIG


CURRENT_PLATFORM = detect_platform()
CURRENT_ENDIAN   = detect_endian()
PTR_SIZE         = ctypes.sizeof(ctypes.c_void_p)


# ---------------------------------------------------------------------------
# C type info registry
# ---------------------------------------------------------------------------

@dataclass
class CTypeInfo:
    name: str
    c_type: type          # ctypes type (e.g. ctypes.c_int32)
    size: int             # sizeof in bytes
    alignment: int        # alignment requirement
    signed: bool          # True for signed types

    def zero(self) -> Any:
        """Return a zero-valued instance."""
        return self.c_type(0)

    def from_bytes(self, data: bytes) -> Any:
        """Decode from raw bytes."""
        return self.c_type.from_buffer_copy(data)

    def to_bytes(self, value: Any) -> bytes:
        """Encode to raw bytes."""
        inst = self.c_type(value)
        return bytes(inst)


# Build the canonical C types dictionary
C_TYPES: dict[str, CTypeInfo] = {
    "int8":    CTypeInfo("int8",    ctypes.c_int8,    1, 1,  True),
    "uint8":   CTypeInfo("uint8",   ctypes.c_uint8,   1, 1,  False),
    "int16":   CTypeInfo("int16",   ctypes.c_int16,   2, 2,  True),
    "uint16":  CTypeInfo("uint16",  ctypes.c_uint16,  2, 2,  False),
    "int32":   CTypeInfo("int32",   ctypes.c_int32,   4, 4,  True),
    "uint32":  CTypeInfo("uint32",  ctypes.c_uint32,  4, 4,  False),
    "int64":   CTypeInfo("int64",   ctypes.c_int64,   8, 8,  True),
    "uint64":  CTypeInfo("uint64",  ctypes.c_uint64,  8, 8,  False),
    "float32": CTypeInfo("float32", ctypes.c_float,   4, 4,  True),
    "float64": CTypeInfo("float64", ctypes.c_double,  8, 8,  True),
    "bool":    CTypeInfo("bool",    ctypes.c_bool,    1, 1,  False),
    "char":    CTypeInfo("char",    ctypes.c_char,    1, 1,  False),
    "ptr":     CTypeInfo("ptr",     ctypes.c_void_p,  PTR_SIZE, PTR_SIZE, False),
    "size_t":  CTypeInfo("size_t",  ctypes.c_size_t,  PTR_SIZE, PTR_SIZE, False),
    "ssize_t": CTypeInfo("ssize_t", ctypes.c_ssize_t, PTR_SIZE, PTR_SIZE, True),
    "wchar":   CTypeInfo("wchar",   ctypes.c_wchar,   ctypes.sizeof(ctypes.c_wchar), ctypes.sizeof(ctypes.c_wchar), False),
}

# Aliases
C_TYPES["byte"]   = C_TYPES["uint8"]
C_TYPES["ubyte"]  = C_TYPES["uint8"]
C_TYPES["short"]  = C_TYPES["int16"]
C_TYPES["ushort"] = C_TYPES["uint16"]
C_TYPES["int"]    = C_TYPES["int32"]
C_TYPES["uint"]   = C_TYPES["uint32"]
C_TYPES["long"]   = C_TYPES["int64"]
C_TYPES["ulong"]  = C_TYPES["uint64"]
C_TYPES["float"]  = C_TYPES["float32"]
C_TYPES["double"] = C_TYPES["float64"]


# ---------------------------------------------------------------------------
# StructField
# ---------------------------------------------------------------------------

@dataclass
class StructField:
    name: str
    type_name: str
    offset: int
    size: int
    array_count: int = 1

    @property
    def total_size(self) -> int:
        return self.size * self.array_count

    def get_ctype(self) -> type:
        info = C_TYPES.get(self.type_name)
        if info is None:
            raise CTypesBridgeError(f"Unknown C type: {self.type_name}")
        if self.array_count > 1:
            return info.c_type * self.array_count
        return info.c_type


class CTypesBridgeError(Exception):
    pass


# ---------------------------------------------------------------------------
# CStructBuilder
# ---------------------------------------------------------------------------

class CStructBuilder:
    """
    Dynamically builds ctypes.Structure subclasses with named fields.

    Supports all C primitive types, arrays, and proper alignment calculation.
    """

    def __init__(self, struct_name: str = "AnonymousStruct"):
        self._struct_name = struct_name
        self._fields: list[StructField] = []
        self._current_offset = 0
        self._max_alignment = 1
        self._built: Optional[type] = None

    def add_field(
        self,
        name: str,
        type_name: str,
        array_count: int = 1,
    ) -> 'CStructBuilder':
        """
        Add a field. Chain calls for fluent API.
        Automatically inserts padding for alignment.
        """
        if self._built is not None:
            raise CTypesBridgeError("Cannot add fields after build()")

        info = C_TYPES.get(type_name)
        if info is None:
            raise CTypesBridgeError(f"Unknown C type: {type_name}")

        # Align current offset
        align = info.alignment
        if align > 1:
            remainder = self._current_offset % align
            if remainder:
                self._current_offset += align - remainder

        self._max_alignment = max(self._max_alignment, align)
        field = StructField(
            name=name,
            type_name=type_name,
            offset=self._current_offset,
            size=info.size,
            array_count=array_count,
        )
        self._fields.append(field)
        self._current_offset += info.size * array_count
        return self

    def add_padding(self, n: int) -> 'CStructBuilder':
        """Explicitly add n bytes of padding."""
        field = StructField(
            name=f"_pad_{self._current_offset}",
            type_name="uint8",
            offset=self._current_offset,
            size=1,
            array_count=n,
        )
        self._fields.append(field)
        self._current_offset += n
        return self

    def _align_to(self, n: int) -> int:
        """Align current offset to n bytes."""
        rem = self._current_offset % n
        if rem:
            self._current_offset += n - rem
        return self._current_offset

    def build(self) -> type:
        """
        Build and return a ctypes.Structure subclass.
        Caches the result.
        """
        if self._built is not None:
            return self._built

        # Final struct size must be multiple of max alignment
        self._align_to(self._max_alignment)

        fields_spec = []
        for f in self._fields:
            ctype = f.get_ctype()
            fields_spec.append((f.name, ctype))

        struct_class = type(
            self._struct_name,
            (ctypes.Structure,),
            {
                '_fields_': fields_spec,
                '_pack_': 1,  # We handle alignment manually
            }
        )
        self._built = struct_class
        return struct_class

    def sizeof(self) -> int:
        """Return total struct size in bytes."""
        if self._built is not None:
            return ctypes.sizeof(self._built)
        return self._current_offset

    def field_offset(self, name: str) -> int:
        """Return byte offset of a named field."""
        for f in self._fields:
            if f.name == name:
                return f.offset
        raise KeyError(f"Field {name!r} not found in {self._struct_name}")

    def field_info(self, name: str) -> StructField:
        for f in self._fields:
            if f.name == name:
                return f
        raise KeyError(f"Field {name!r} not found")

    def pack(self, values: dict) -> bytes:
        """Pack a dict of field values into raw bytes."""
        cls = self.build()
        inst = cls()
        for name, value in values.items():
            if hasattr(inst, name):
                try:
                    setattr(inst, name, value)
                except TypeError:
                    # Array field — assign element by element
                    field_info = self.field_info(name)
                    attr = getattr(inst, name)
                    if hasattr(value, '__iter__'):
                        for i, v in enumerate(value):
                            attr[i] = v
        return bytes(inst)

    def unpack(self, data: bytes) -> dict:
        """Unpack raw bytes into a dict of field values."""
        cls = self.build()
        if len(data) < ctypes.sizeof(cls):
            raise CTypesBridgeError(
                f"Data too short: {len(data)} < {ctypes.sizeof(cls)}"
            )
        inst = cls.from_buffer_copy(data[:ctypes.sizeof(cls)])
        result = {}
        for f in self._fields:
            if f.name.startswith('_pad_'):
                continue
            value = getattr(inst, f.name)
            if f.array_count > 1:
                # Convert ctypes array to list
                result[f.name] = list(value)
            else:
                result[f.name] = value
        return result

    def describe(self) -> str:
        """Return human-readable field layout."""
        lines = [f"struct {self._struct_name} ({self.sizeof()} bytes):"]
        for f in self._fields:
            if f.name.startswith('_pad_'):
                lines.append(f"  +{f.offset:4d}  [padding: {f.total_size} bytes]")
            else:
                arr = f"[{f.array_count}]" if f.array_count > 1 else ""
                lines.append(
                    f"  +{f.offset:4d}  {f.type_name}{arr:<10} {f.name}"
                    f"  ({f.total_size} bytes)"
                )
        return '\n'.join(lines)

    def copy(self) -> 'CStructBuilder':
        """Return a copy of this builder (fields only, not built class)."""
        new = CStructBuilder(self._struct_name)
        new._fields = list(self._fields)
        new._current_offset = self._current_offset
        new._max_alignment = self._max_alignment
        return new


# ---------------------------------------------------------------------------
# MemoryArena — fixed-size bump allocator
# ---------------------------------------------------------------------------

class MemoryArena:
    """
    Fixed-size bump allocator backed by a ctypes byte array.
    Thread-unsafe; designed for single-threaded use.
    """

    def __init__(self, size: int):
        self._size = size
        self._buffer = (ctypes.c_uint8 * size)()
        self._cursor = 0

    def alloc(self, size: int, alignment: int = 8) -> int:
        """
        Allocate `size` bytes with given alignment.
        Returns byte offset within the arena.
        Raises MemoryError if insufficient space.
        """
        # Align cursor
        if alignment > 1:
            rem = self._cursor % alignment
            if rem:
                self._cursor += alignment - rem

        if self._cursor + size > self._size:
            raise MemoryError(
                f"Arena out of memory: need {size}, have {self._size - self._cursor}"
            )

        offset = self._cursor
        self._cursor += size
        return offset

    def free_all(self) -> None:
        """Reset the arena, logically freeing all allocations."""
        self._cursor = 0
        # Zero the buffer
        ctypes.memset(self._buffer, 0, self._size)

    def get_ptr(self, offset: int) -> ctypes.c_void_p:
        """Return a void pointer to the given offset."""
        self._validate_offset(offset)
        addr = ctypes.addressof(self._buffer) + offset
        return ctypes.c_void_p(addr)

    def write_bytes(self, offset: int, data: bytes) -> None:
        """Write bytes at the given offset."""
        if offset + len(data) > self._size:
            raise CTypesBridgeError(
                f"Write out of bounds: offset={offset}, len={len(data)}, size={self._size}"
            )
        for i, b in enumerate(data):
            self._buffer[offset + i] = b

    def read_bytes(self, offset: int, size: int) -> bytes:
        """Read bytes from the given offset."""
        if offset + size > self._size:
            raise CTypesBridgeError(
                f"Read out of bounds: offset={offset}, size={size}"
            )
        return bytes(self._buffer[offset:offset + size])

    def write_uint32(self, offset: int, value: int) -> None:
        data = struct.pack('<I', value & 0xFFFFFFFF)
        self.write_bytes(offset, data)

    def read_uint32(self, offset: int) -> int:
        data = self.read_bytes(offset, 4)
        return struct.unpack('<I', data)[0]

    def write_uint64(self, offset: int, value: int) -> None:
        data = struct.pack('<Q', value & 0xFFFFFFFFFFFFFFFF)
        self.write_bytes(offset, data)

    def read_uint64(self, offset: int) -> int:
        data = self.read_bytes(offset, 8)
        return struct.unpack('<Q', data)[0]

    def remaining(self) -> int:
        return self._size - self._cursor

    def used(self) -> int:
        return self._cursor

    def capacity(self) -> int:
        return self._size

    def utilization(self) -> float:
        return self._cursor / self._size if self._size > 0 else 0.0

    def _validate_offset(self, offset: int) -> None:
        if offset < 0 or offset >= self._size:
            raise CTypesBridgeError(
                f"Invalid arena offset: {offset} (size={self._size})"
            )

    def as_bytearray(self) -> bytearray:
        return bytearray(self._buffer[:self._cursor])

    def hexdump(self, start: int = 0, length: int | None = None, width: int = 16) -> str:
        end = min(start + (length or self._cursor), self._cursor)
        lines = []
        for off in range(start, end, width):
            chunk = self.read_bytes(off, min(width, end - off))
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'{off:08x}  {hex_part:<{width * 3}}  |{ascii_part}|')
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# C string helpers
# ---------------------------------------------------------------------------

def cstr_to_bytes(ptr: ctypes.c_char_p, max_len: int = 4096) -> bytes:
    """Read a null-terminated C string from a c_char_p pointer."""
    if not ptr:
        return b''
    result = bytearray()
    i = 0
    buf = ctypes.string_at(ptr, max_len)
    while i < len(buf) and buf[i] != 0:
        result.append(buf[i])
        i += 1
    return bytes(result)


def bytes_to_cstr(data: bytes) -> ctypes.c_char_p:
    """Create a null-terminated C string from Python bytes."""
    return ctypes.c_char_p(data + b'\x00')


def pack_cstr(data: bytes, buffer_size: int) -> bytes:
    """Pack bytes into a fixed-size null-terminated buffer."""
    truncated = data[:buffer_size - 1]
    return truncated + b'\x00' * (buffer_size - len(truncated))


# ---------------------------------------------------------------------------
# Pointer arithmetic helpers
# ---------------------------------------------------------------------------

def ptr_add(base: int, offset: int) -> int:
    """Add byte offset to a pointer value."""
    return (base + offset) & ((1 << (PTR_SIZE * 8)) - 1)


def ptr_align(ptr: int, alignment: int) -> int:
    """Align a pointer value up to the given alignment."""
    rem = ptr % alignment
    if rem:
        return ptr + (alignment - rem)
    return ptr


def ptr_is_aligned(ptr: int, alignment: int) -> bool:
    return (ptr % alignment) == 0


def ptr_diff(a: int, b: int) -> int:
    """Compute signed difference between two pointer values."""
    diff = a - b
    # Sign-extend if necessary
    bits = PTR_SIZE * 8
    if diff >= (1 << (bits - 1)):
        diff -= (1 << bits)
    return diff


# ---------------------------------------------------------------------------
# FunctionBinding — dynamic library function binding
# ---------------------------------------------------------------------------

class FunctionBinding:
    """
    Binds C functions from a shared library using ctypes.

    Supports lazy loading and caching of bound functions.
    """

    def __init__(self, lib_path: str | None = None):
        self._lib_path = lib_path
        self._lib: Optional[ctypes.CDLL] = None
        self._bound: dict[str, Any] = {}

    def _ensure_loaded(self) -> ctypes.CDLL:
        if self._lib is None:
            if self._lib_path is None:
                # Load the C runtime
                if sys.platform == 'win32':
                    self._lib = ctypes.CDLL("msvcrt")
                elif sys.platform == 'darwin':
                    self._lib = ctypes.CDLL("libc.dylib")
                else:
                    self._lib = ctypes.CDLL("libc.so.6")
            else:
                self._lib = ctypes.CDLL(self._lib_path)
        return self._lib

    def bind(
        self,
        func_name: str,
        restype: Any,
        argtypes: list,
    ) -> Callable:
        """
        Bind a C function by name with explicit type signatures.
        Returns a callable.
        """
        lib = self._ensure_loaded()
        try:
            func = getattr(lib, func_name)
        except AttributeError:
            raise CTypesBridgeError(f"Function not found in library: {func_name}")

        func.restype = restype
        func.argtypes = argtypes
        self._bound[func_name] = func
        return func

    def call(self, func_name: str, *args) -> Any:
        """Call a previously bound function."""
        func = self._bound.get(func_name)
        if func is None:
            raise CTypesBridgeError(f"Function not bound: {func_name}")
        return func(*args)

    def is_bound(self, func_name: str) -> bool:
        return func_name in self._bound

    def list_bound(self) -> list[str]:
        return list(self._bound.keys())


# ---------------------------------------------------------------------------
# struct_pack_unpack helpers
# ---------------------------------------------------------------------------

def pack_fields(format_string: str, **fields) -> bytes:
    """
    Pack named fields using a struct format string.
    Fields must be in the same order as format_string.
    """
    values = list(fields.values())
    return struct.pack(format_string, *values)


def unpack_fields(format_string: str, data: bytes, field_names: list[str]) -> dict:
    """
    Unpack bytes using format_string, return dict with field_names.
    """
    values = struct.unpack(format_string, data[:struct.calcsize(format_string)])
    return dict(zip(field_names, values))


def struct_sizeof(format_string: str) -> int:
    return struct.calcsize(format_string)


# ---------------------------------------------------------------------------
# Pre-defined C structs for the IPC system
# These must match native/dispatcher/ipc_core.c
# ---------------------------------------------------------------------------

# IPCHeader: 12 bytes
#   magic:       char[4]   — 'SOVR'
#   opcode:      uint16    — dispatch opcode
#   flags:       uint16    — control flags
#   payload_len: uint32    — bytes following this header

_ipc_header_builder = CStructBuilder("IPCHeader")
_ipc_header_builder \
    .add_field("magic",       "char",   array_count=4) \
    .add_field("opcode",      "uint16") \
    .add_field("flags",       "uint16") \
    .add_field("payload_len", "uint32")

IPCHeaderStruct = _ipc_header_builder.build()
IPC_HEADER_SIZE = ctypes.sizeof(IPCHeaderStruct)  # 12 bytes

IPC_MAGIC      = b'SOVR'
IPC_FLAG_REPLY = 0x0001
IPC_FLAG_ERROR = 0x0002
IPC_FLAG_ACK   = 0x0004
IPC_FLAG_ASYNC = 0x0008


def encode_ipc_header(opcode: int, flags: int, payload_len: int) -> bytes:
    """Encode an IPC header to 12 raw bytes."""
    return _ipc_header_builder.pack({
        'magic':       IPC_MAGIC,
        'opcode':      opcode,
        'flags':       flags,
        'payload_len': payload_len,
    })


def decode_ipc_header(data: bytes) -> dict:
    """Decode 12 bytes to IPC header dict."""
    if len(data) < IPC_HEADER_SIZE:
        raise CTypesBridgeError(f"Header too short: {len(data)}")
    return _ipc_header_builder.unpack(data)


# DispatchPacket: header + variable payload
# (Use encode_dispatch_packet / decode_dispatch_packet for full packets)

def encode_dispatch_packet(opcode: int, flags: int, payload: bytes) -> bytes:
    """Build a complete IPC dispatch packet."""
    header = encode_ipc_header(opcode, flags, len(payload))
    return header + payload


def decode_dispatch_packet(data: bytes) -> tuple[dict, bytes]:
    """Split data into (header_dict, payload_bytes)."""
    header = decode_ipc_header(data)
    payload = data[IPC_HEADER_SIZE:IPC_HEADER_SIZE + header['payload_len']]
    return header, payload


# ---------------------------------------------------------------------------
# RoutingTableEntry — fixed-size routing entry for kernel dispatch
# ---------------------------------------------------------------------------

_routing_entry_builder = CStructBuilder("RoutingTableEntry")
_routing_entry_builder \
    .add_field("agent_id",     "uint16") \
    .add_field("opcode_mask",  "uint32") \
    .add_field("handler_ptr",  "ptr") \
    .add_field("priority",     "uint8") \
    .add_field("flags",        "uint8") \
    .add_padding(2)             # align to 8 bytes

RoutingTableEntryStruct = _routing_entry_builder.build()
ROUTING_ENTRY_SIZE = ctypes.sizeof(RoutingTableEntryStruct)


# ---------------------------------------------------------------------------
# AgentStateRecord — per-agent state snapshot
# ---------------------------------------------------------------------------

_agent_state_builder = CStructBuilder("AgentStateRecord")
_agent_state_builder \
    .add_field("agent_id",    "uint16") \
    .add_field("status",      "uint8") \
    .add_field("flags",       "uint8") \
    .add_field("entropy",     "float32") \
    .add_field("call_count",  "uint32") \
    .add_field("last_opcode", "uint16") \
    .add_field("session_id",  "uint16") \
    .add_field("timestamp",   "uint64") \
    .add_padding(4)

AgentStateRecordStruct = _agent_state_builder.build()
AGENT_STATE_SIZE = ctypes.sizeof(AgentStateRecordStruct)

AGENT_STATUS_IDLE    = 0
AGENT_STATUS_RUNNING = 1
AGENT_STATUS_BLOCKED = 2
AGENT_STATUS_ERROR   = 3


# ---------------------------------------------------------------------------
# WORMBlock — Write-Once-Read-Many commitment block
# ---------------------------------------------------------------------------

_worm_block_builder = CStructBuilder("WORMBlock")
_worm_block_builder \
    .add_field("magic",      "char",   array_count=4) \
    .add_field("seq",        "uint64") \
    .add_field("timestamp",  "uint64") \
    .add_field("data_len",   "uint32") \
    .add_field("checksum",   "uint8",  array_count=32) \
    .add_padding(4)

WORMBlockStruct = _worm_block_builder.build()
WORM_BLOCK_SIZE = ctypes.sizeof(WORMBlockStruct)
WORM_MAGIC = b'WORM'


def encode_worm_block(seq: int, timestamp: int, data: bytes, checksum: bytes) -> bytes:
    """Encode a WORM block header (without data payload)."""
    if len(checksum) != 32:
        raise CTypesBridgeError(f"Checksum must be 32 bytes, got {len(checksum)}")
    return _worm_block_builder.pack({
        'magic':     WORM_MAGIC,
        'seq':       seq,
        'timestamp': timestamp,
        'data_len':  len(data),
        'checksum':  list(checksum),
    })


# ---------------------------------------------------------------------------
# NativeCallConvention — wrap native call sequences
# ---------------------------------------------------------------------------

class NativeCallConvention(Enum):
    CDECL    = "cdecl"
    STDCALL  = "stdcall"
    FASTCALL = "fastcall"
    THISCALL = "thiscall"


def make_callback(func_type, python_fn: Callable) -> Any:
    """
    Create a ctypes callback function that wraps a Python callable.
    func_type: a ctypes CFUNCTYPE or WINFUNCTYPE factory result.
    """
    return func_type(python_fn)


# Common callback types
CFUNC_VOID_VOID    = ctypes.CFUNCTYPE(None)
CFUNC_INT_INT      = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)
CFUNC_INT_VOIDP    = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
CFUNC_VOIDP_VOIDP  = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
CFUNC_INT_VOIDP_INT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int)


# ---------------------------------------------------------------------------
# TypedMemoryView — typed view over a raw buffer
# ---------------------------------------------------------------------------

class TypedMemoryView:
    """
    Provides typed access to a region of memory (ctypes buffer or bytes).
    """

    def __init__(self, data: bytes | bytearray | ctypes.Array):
        if isinstance(data, (bytes, bytearray)):
            self._buf = (ctypes.c_uint8 * len(data))(*data)
        else:
            self._buf = data
        self._size = len(self._buf)

    def read_u8(self, offset: int) -> int:
        self._check(offset, 1)
        return self._buf[offset]

    def read_u16_le(self, offset: int) -> int:
        self._check(offset, 2)
        return self._buf[offset] | (self._buf[offset + 1] << 8)

    def read_u32_le(self, offset: int) -> int:
        self._check(offset, 4)
        return struct.unpack_from('<I', self._buf, offset)[0]

    def read_u64_le(self, offset: int) -> int:
        self._check(offset, 8)
        return struct.unpack_from('<Q', self._buf, offset)[0]

    def read_f32_le(self, offset: int) -> float:
        self._check(offset, 4)
        return struct.unpack_from('<f', self._buf, offset)[0]

    def read_f64_le(self, offset: int) -> float:
        self._check(offset, 8)
        return struct.unpack_from('<d', self._buf, offset)[0]

    def read_bytes(self, offset: int, n: int) -> bytes:
        self._check(offset, n)
        return bytes(self._buf[offset:offset + n])

    def write_u8(self, offset: int, value: int) -> None:
        self._check(offset, 1)
        self._buf[offset] = value & 0xFF

    def write_u16_le(self, offset: int, value: int) -> None:
        self._check(offset, 2)
        data = struct.pack('<H', value & 0xFFFF)
        for i, b in enumerate(data):
            self._buf[offset + i] = b

    def write_u32_le(self, offset: int, value: int) -> None:
        self._check(offset, 4)
        data = struct.pack('<I', value & 0xFFFFFFFF)
        for i, b in enumerate(data):
            self._buf[offset + i] = b

    def write_u64_le(self, offset: int, value: int) -> None:
        self._check(offset, 8)
        data = struct.pack('<Q', value & 0xFFFFFFFFFFFFFFFF)
        for i, b in enumerate(data):
            self._buf[offset + i] = b

    def write_bytes(self, offset: int, data: bytes) -> None:
        self._check(offset, len(data))
        for i, b in enumerate(data):
            self._buf[offset + i] = b

    def size(self) -> int:
        return self._size

    def _check(self, offset: int, n: int) -> None:
        if offset < 0 or offset + n > self._size:
            raise CTypesBridgeError(
                f"Out of bounds: offset={offset}, n={n}, size={self._size}"
            )

    def as_bytes(self) -> bytes:
        return bytes(self._buf)


# ---------------------------------------------------------------------------
# PackedArray — pack/unpack arrays of C primitives
# ---------------------------------------------------------------------------

class PackedArray:
    """
    Pack/unpack arrays of a single C primitive type.
    Useful for passing buffers to C functions.
    """

    def __init__(self, type_name: str, count: int):
        info = C_TYPES.get(type_name)
        if info is None:
            raise CTypesBridgeError(f"Unknown C type: {type_name}")
        self._info = info
        self._count = count
        self._arr_type = info.c_type * count
        self._arr = self._arr_type()

    def __setitem__(self, index: int, value: Any) -> None:
        self._arr[index] = value

    def __getitem__(self, index: int) -> Any:
        return self._arr[index]

    def __len__(self) -> int:
        return self._count

    def as_bytes(self) -> bytes:
        return bytes(self._arr)

    def from_bytes(self, data: bytes) -> None:
        size = ctypes.sizeof(self._arr)
        if len(data) < size:
            raise CTypesBridgeError(f"Data too short: {len(data)} < {size}")
        ctypes.memmove(self._arr, data, size)

    def pointer(self) -> ctypes.c_void_p:
        return ctypes.cast(self._arr, ctypes.c_void_p)

    def total_bytes(self) -> int:
        return self._info.size * self._count

    def fill(self, value: Any) -> None:
        for i in range(self._count):
            self._arr[i] = value

    def to_list(self) -> list:
        return [self._arr[i] for i in range(self._count)]

    def from_list(self, values: list) -> None:
        for i, v in enumerate(values[:self._count]):
            self._arr[i] = v


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    # Platform detection
    assert CURRENT_PLATFORM in Platform

    # CTypeInfo
    info = C_TYPES["uint32"]
    assert info.size == 4
    assert not info.signed

    # CStructBuilder
    builder = CStructBuilder("TestStruct")
    builder.add_field("x", "uint32")
    builder.add_field("y", "float32")
    builder.add_field("z", "uint8")

    cls = builder.build()
    assert ctypes.sizeof(cls) >= 9

    packed = builder.pack({'x': 42, 'y': 3.14, 'z': 7})
    unpacked = builder.unpack(packed)
    assert unpacked['x'] == 42
    assert abs(unpacked['y'] - 3.14) < 1e-5
    assert unpacked['z'] == 7

    # MemoryArena
    arena = MemoryArena(1024)
    off1 = arena.alloc(16, alignment=8)
    assert off1 == 0
    off2 = arena.alloc(8, alignment=8)
    assert off2 == 16

    arena.write_bytes(off1, b"hello world!!!!!")
    data = arena.read_bytes(off1, 11)
    assert data == b"hello world"

    arena.free_all()
    assert arena.used() == 0

    # IPC header
    header_bytes = encode_ipc_header(0x0042, IPC_FLAG_REPLY, 256)
    assert len(header_bytes) == IPC_HEADER_SIZE
    decoded = decode_ipc_header(header_bytes)
    assert decoded['opcode'] == 0x0042
    assert decoded['payload_len'] == 256

    # PackedArray
    arr = PackedArray("uint32", 4)
    arr.from_list([10, 20, 30, 40])
    assert arr[2] == 30
    data = arr.as_bytes()
    assert len(data) == 16

    # TypedMemoryView
    mv = TypedMemoryView(b'\x01\x02\x03\x04\x05\x06\x07\x08')
    assert mv.read_u8(0) == 0x01
    assert mv.read_u16_le(0) == 0x0201
    assert mv.read_u32_le(0) == 0x04030201

    return True


if __name__ == "__main__":
    assert _self_test(), "Self-test failed"
    print("ctypes_bridge.py: all self-tests passed")

    # Demo: describe IPC header layout
    print("\nIPCHeader layout:")
    print(_ipc_header_builder.describe())
    print(f"\nWORMBlock layout:")
    print(_worm_block_builder.describe())
    print(f"\nAgentStateRecord layout:")
    print(_agent_state_builder.describe())
    print(f"\nCurrent platform: {CURRENT_PLATFORM.value}, endian: {CURRENT_ENDIAN.value}")
    print(f"Pointer size: {PTR_SIZE} bytes")
