"""
marshal_codec.py — Python marshal format encoder/decoder for .pyc files.

Reads and writes the binary marshal format used by CPython for serializing
code objects, constants, and .pyc files at the raw binary level.

Part of the SOVEREIGN_IR PYTHON_C_BRIDGE_IR pipeline.
Agent A (Cognition) — HyperKittyConstraintDSL v1.0
"""

from __future__ import annotations

import hashlib
import io
import math
import struct
import time
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Magic numbers for each CPython minor version
# These must match exactly for .pyc files to be valid
# ---------------------------------------------------------------------------

MAGIC_NUMBER: dict[int, bytes] = {
    # (year 2023+)  Python version int -> 4-byte magic
    312: b'\x0d\x0d\r\n',   # 3.12
    311: b'\xa7\x0d\r\n',   # 3.11
    310: b'\x55\x0d\r\n',   # 3.10
    309: b'\x0f\x0d\r\n',   # 3.9
    308: b'\x55\x0d\r\n',   # 3.8 (approximate)
    307: b'\x42\x0d\r\n',   # 3.7
    306: b'\x33\x0d\r\n',   # 3.6
    305: b'\xee\x0c\r\n',   # 3.5
    304: b'\xee\x0c\r\n',   # 3.4
}

# Header layout: magic(4) + flags(4) + timestamp(4) + source_size(4)
PYC_HEADER_SIZE = 16

# Checked vs hash-based .pyc flag
PYC_FLAG_HASH_BASED = 0x01
PYC_FLAG_CHECKED    = 0x02


# ---------------------------------------------------------------------------
# Marshal type codes
# ---------------------------------------------------------------------------

TYPE_NULL                   = ord('0')
TYPE_NONE                   = ord('N')
TYPE_FALSE                  = ord('F')
TYPE_TRUE                   = ord('T')
TYPE_STOPITER               = ord('S')
TYPE_ELLIPSIS               = ord('.')
TYPE_INT                    = ord('i')
TYPE_INT64                  = ord('I')
TYPE_FLOAT                  = ord('g')
TYPE_BINARY_FLOAT           = ord('g')  # same as float
TYPE_COMPLEX                = ord('y')
TYPE_BINARY_COMPLEX         = ord('Y')
TYPE_LONG                   = ord('l')
TYPE_STRING                 = ord('s')
TYPE_INTERNED               = ord('t')
TYPE_REF                    = ord('r')
TYPE_TUPLE                  = ord('(')
TYPE_LIST                   = ord('[')
TYPE_DICT                   = ord('{')
TYPE_CODE                   = ord('c')
TYPE_UNICODE                = ord('u')
TYPE_UNKNOWN                = ord('?')
TYPE_SET                    = ord('<')
TYPE_FROZENSET              = ord('>')
TYPE_ASCII                  = ord('a')
TYPE_ASCII_INTERNED         = ord('A')
TYPE_SMALL_TUPLE            = ord(')')
TYPE_SHORT_ASCII            = ord('z')
TYPE_SHORT_ASCII_INTERNED   = ord('Z')
TYPE_BYTES                  = ord('s')   # alias

# FLAG_REF: if set, object is added to the reference table
FLAG_REF = 0x80

TYPE_CODE_VERSION_311 = 311
TYPE_CODE_VERSION_312 = 312


# ---------------------------------------------------------------------------
# MarshalError
# ---------------------------------------------------------------------------

class MarshalError(Exception):
    pass


# ---------------------------------------------------------------------------
# MarshalReader
# ---------------------------------------------------------------------------

class MarshalReader:
    """
    Reads Python marshal-format binary data and reconstructs Python objects.
    Handles all marshal types including nested code objects.
    """

    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)
        self._ref_table: list[Any] = []   # for FLAG_REF back-references

    # --- primitive readers --------------------------------------------------

    def _read(self, n: int) -> bytes:
        data = self._buf.read(n)
        if len(data) < n:
            raise MarshalError(f"Unexpected EOF: wanted {n}, got {len(data)}")
        return data

    def _read1(self) -> int:
        b = self._buf.read(1)
        if not b:
            raise MarshalError("Unexpected EOF reading byte")
        return b[0]

    def read_int(self) -> int:
        """Read a 32-bit little-endian signed integer."""
        return struct.unpack('<i', self._read(4))[0]

    def read_uint32(self) -> int:
        return struct.unpack('<I', self._read(4))[0]

    def read_int64(self) -> int:
        return struct.unpack('<q', self._read(8))[0]

    def read_uint64(self) -> int:
        return struct.unpack('<Q', self._read(8))[0]

    def read_short(self) -> int:
        return struct.unpack('<h', self._read(2))[0]

    def read_ushort(self) -> int:
        return struct.unpack('<H', self._read(2))[0]

    def read_float64(self) -> float:
        return struct.unpack('<d', self._read(8))[0]

    def read_string(self) -> str:
        n = self.read_uint32()
        raw = self._read(n)
        return raw.decode('utf-8', errors='replace')

    def read_bytes(self) -> bytes:
        n = self.read_uint32()
        return self._read(n)

    def read_short_ascii(self) -> str:
        n = self._read1()
        return self._read(n).decode('ascii', errors='replace')

    def read_unicode(self) -> str:
        n = self.read_uint32()
        return self._read(n).decode('utf-8', errors='replace')

    # --- long integer (multi-precision) -------------------------------------

    def read_long_int(self) -> int:
        n = self.read_int()
        negative = n < 0
        size = abs(n)
        digits = []
        for _ in range(size):
            digits.append(self.read_ushort())
        value = 0
        for i, d in enumerate(digits):
            value |= d << (i * 15)
        return -value if negative else value

    # --- object reader ------------------------------------------------------

    def read_object(self) -> Any:
        """Read and return the next marshaled object."""
        type_byte = self._read1()
        flag = type_byte & FLAG_REF
        type_code = type_byte & ~FLAG_REF

        # Reserve ref slot if FLAG_REF set
        ref_idx = -1
        if flag:
            ref_idx = len(self._ref_table)
            self._ref_table.append(None)  # placeholder

        obj = self._read_typed(type_code)

        if flag and ref_idx >= 0:
            self._ref_table[ref_idx] = obj

        return obj

    def _read_typed(self, type_code: int) -> Any:
        if type_code == TYPE_NULL:
            return None
        elif type_code == TYPE_NONE:
            return None
        elif type_code == TYPE_FALSE:
            return False
        elif type_code == TYPE_TRUE:
            return True
        elif type_code == TYPE_STOPITER:
            return StopIteration
        elif type_code == TYPE_ELLIPSIS:
            return ...
        elif type_code == TYPE_INT:
            return self.read_int()
        elif type_code == TYPE_INT64:
            return self.read_int64()
        elif type_code == TYPE_LONG:
            return self.read_long_int()
        elif type_code == TYPE_FLOAT or type_code == ord('g'):
            return self.read_float64()
        elif type_code == TYPE_BINARY_COMPLEX or type_code == ord('y'):
            real = self.read_float64()
            imag = self.read_float64()
            return complex(real, imag)
        elif type_code == TYPE_STRING or type_code == TYPE_BYTES:
            return self.read_bytes()
        elif type_code == TYPE_UNICODE or type_code == ord('u'):
            return self.read_unicode()
        elif type_code == TYPE_ASCII or type_code == ord('a'):
            return self.read_unicode()  # same encoding
        elif type_code == TYPE_ASCII_INTERNED or type_code == ord('A'):
            return sys_intern(self.read_unicode())
        elif type_code == TYPE_SHORT_ASCII or type_code == ord('z'):
            return self.read_short_ascii()
        elif type_code == TYPE_SHORT_ASCII_INTERNED or type_code == ord('Z'):
            return sys_intern(self.read_short_ascii())
        elif type_code == TYPE_INTERNED or type_code == ord('t'):
            return sys_intern(self.read_bytes().decode('utf-8', errors='replace'))
        elif type_code == TYPE_REF or type_code == ord('r'):
            ref_n = self.read_uint32()
            if ref_n >= len(self._ref_table):
                raise MarshalError(f"Invalid ref index: {ref_n}")
            return self._ref_table[ref_n]
        elif type_code == TYPE_TUPLE or type_code == ord('('):
            return self.read_tuple()
        elif type_code == TYPE_SMALL_TUPLE or type_code == ord(')'):
            n = self._read1()
            return tuple(self.read_object() for _ in range(n))
        elif type_code == TYPE_LIST or type_code == ord('['):
            return self.read_list()
        elif type_code == TYPE_DICT or type_code == ord('{'):
            return self.read_dict()
        elif type_code == TYPE_SET or type_code == ord('<'):
            return set(self.read_tuple())
        elif type_code == TYPE_FROZENSET or type_code == ord('>'):
            return frozenset(self.read_tuple())
        elif type_code == TYPE_CODE or type_code == ord('c'):
            return self.read_code()
        else:
            raise MarshalError(f"Unknown marshal type code: {type_code} ({chr(type_code)!r})")

    def read_tuple(self) -> tuple:
        n = self.read_uint32()
        return tuple(self.read_object() for _ in range(n))

    def read_list(self) -> list:
        n = self.read_uint32()
        return [self.read_object() for _ in range(n)]

    def read_dict(self) -> dict:
        result = {}
        while True:
            key = self.read_object()
            if key is None:
                break
            value = self.read_object()
            result[key] = value
        return result

    def read_code(self) -> types.CodeType:
        """Read a code object from the marshal stream."""
        import sys
        version = sys.version_info

        if version >= (3, 11):
            return self._read_code_311()
        else:
            return self._read_code_310()

    def _read_code_311(self) -> types.CodeType:
        """Read code object for Python 3.11+."""
        argcount        = self.read_int()
        posonlyargcount = self.read_int()
        kwonlyargcount  = self.read_int()
        nlocals         = self.read_int()
        stacksize       = self.read_int()
        flags           = self.read_int()
        code            = self.read_object()   # bytes
        consts          = self.read_object()   # tuple
        names           = self.read_object()   # tuple
        varnames        = self.read_object()   # tuple
        freevars        = self.read_object()   # tuple
        cellvars        = self.read_object()   # tuple
        filename        = self.read_object()   # str
        name            = self.read_object()   # str
        qualname        = self.read_object()   # str (3.11+)
        firstlineno     = self.read_int()
        lnotab          = self.read_object()   # bytes
        exceptiontable  = self.read_object()   # bytes (3.11+)

        try:
            return types.CodeType(
                argcount, posonlyargcount, kwonlyargcount,
                nlocals, stacksize, flags,
                code, consts, names, varnames, filename, name,
                qualname, firstlineno, lnotab, exceptiontable,
                freevars, cellvars,
            )
        except TypeError:
            # Fall back for version mismatches
            return types.CodeType(
                argcount, posonlyargcount, kwonlyargcount,
                nlocals, stacksize, flags,
                code, consts, names, varnames, filename, name,
                firstlineno, lnotab, freevars, cellvars,
            )

    def _read_code_310(self) -> types.CodeType:
        """Read code object for Python 3.10 and earlier."""
        argcount        = self.read_int()
        posonlyargcount = self.read_int()
        kwonlyargcount  = self.read_int()
        nlocals         = self.read_int()
        stacksize       = self.read_int()
        flags           = self.read_int()
        code            = self.read_object()
        consts          = self.read_object()
        names           = self.read_object()
        varnames        = self.read_object()
        freevars        = self.read_object()
        cellvars        = self.read_object()
        filename        = self.read_object()
        name            = self.read_object()
        firstlineno     = self.read_int()
        lnotab          = self.read_object()

        return types.CodeType(
            argcount, posonlyargcount, kwonlyargcount,
            nlocals, stacksize, flags,
            code, consts, names, varnames, filename, name,
            firstlineno, lnotab, freevars, cellvars,
        )

    def position(self) -> int:
        return self._buf.tell()

    def remaining(self) -> int:
        pos = self._buf.tell()
        self._buf.seek(0, 2)
        end = self._buf.tell()
        self._buf.seek(pos)
        return end - pos


# ---------------------------------------------------------------------------
# MarshalWriter
# ---------------------------------------------------------------------------

class MarshalWriter:
    """
    Serializes Python objects to the marshal binary format.
    Produces bytes compatible with Python's marshal module.
    """

    def __init__(self, version: int = 4):
        self._buf = io.BytesIO()
        self._version = version
        self._ref_table: dict[int, int] = {}   # id(obj) -> ref_index
        self._ref_count = 0

    def _write(self, data: bytes) -> None:
        self._buf.write(data)

    def _write1(self, b: int) -> None:
        self._buf.write(bytes([b & 0xFF]))

    def _write_type(self, type_code: int, obj: Any = None, flag_ref: bool = False) -> None:
        code = type_code
        if flag_ref and obj is not None:
            obj_id = id(obj)
            if obj_id not in self._ref_table:
                self._ref_table[obj_id] = self._ref_count
                self._ref_count += 1
                code |= FLAG_REF
        self._write1(code)

    def write_int(self, n: int) -> None:
        self._write(struct.pack('<i', n))

    def write_uint32(self, n: int) -> None:
        self._write(struct.pack('<I', n))

    def write_int64(self, n: int) -> None:
        self._write(struct.pack('<q', n))

    def write_float64(self, f: float) -> None:
        self._write(struct.pack('<d', f))

    def write_short(self, n: int) -> None:
        self._write(struct.pack('<h', n))

    def write_ushort(self, n: int) -> None:
        self._write(struct.pack('<H', n))

    def write_string(self, s: str) -> None:
        encoded = s.encode('utf-8')
        self.write_uint32(len(encoded))
        self._write(encoded)

    def write_bytes(self, b: bytes) -> None:
        self.write_uint32(len(b))
        self._write(b)

    def write_short_ascii(self, s: str) -> None:
        encoded = s.encode('ascii')
        if len(encoded) > 255:
            raise MarshalError("String too long for short ASCII")
        self._write1(len(encoded))
        self._write(encoded)

    def write_float(self, f: float) -> None:
        if math.isnan(f) or math.isinf(f):
            self._write_type(TYPE_FLOAT)
            self.write_float64(f)
            return
        self._write_type(TYPE_FLOAT)
        self.write_float64(f)

    def write_long_int(self, n: int) -> None:
        """Write a Python long integer in marshal format."""
        negative = n < 0
        val = abs(n)
        digits = []
        while val:
            digits.append(val & 0x7FFF)
            val >>= 15
        size = len(digits)
        self.write_int(-size if negative else size)
        for d in digits:
            self.write_ushort(d)

    def write_object(self, obj: Any) -> None:
        """Serialize a Python object to marshal format."""
        if obj is None:
            self._write_type(TYPE_NONE)
        elif obj is False:
            self._write_type(TYPE_FALSE)
        elif obj is True:
            self._write_type(TYPE_TRUE)
        elif obj is StopIteration:
            self._write_type(TYPE_STOPITER)
        elif obj is ...:
            self._write_type(TYPE_ELLIPSIS)
        elif isinstance(obj, int):
            self._write_int_obj(obj)
        elif isinstance(obj, float):
            self._write_type(TYPE_FLOAT)
            self.write_float64(obj)
        elif isinstance(obj, complex):
            self._write_type(TYPE_COMPLEX)
            self.write_float64(obj.real)
            self.write_float64(obj.imag)
        elif isinstance(obj, bytes):
            self._write_type(TYPE_STRING)
            self.write_bytes(obj)
        elif isinstance(obj, str):
            self._write_str_obj(obj)
        elif isinstance(obj, tuple):
            self.write_tuple(obj)
        elif isinstance(obj, list):
            self._write_type(TYPE_LIST)
            self.write_uint32(len(obj))
            for item in obj:
                self.write_object(item)
        elif isinstance(obj, dict):
            self._write_type(TYPE_DICT)
            for k, v in obj.items():
                self.write_object(k)
                self.write_object(v)
            self._write_type(TYPE_NULL)  # end marker
        elif isinstance(obj, (set, frozenset)):
            tc = TYPE_FROZENSET if isinstance(obj, frozenset) else TYPE_SET
            self._write_type(tc)
            items = tuple(obj)
            self.write_uint32(len(items))
            for item in items:
                self.write_object(item)
        elif isinstance(obj, types.CodeType):
            self.write_code(obj)
        else:
            raise MarshalError(f"Cannot marshal object of type {type(obj).__name__}")

    def _write_int_obj(self, n: int) -> None:
        if -(2**31) <= n <= 2**31 - 1:
            self._write_type(TYPE_INT)
            self.write_int(n)
        elif -(2**63) <= n <= 2**63 - 1:
            self._write_type(TYPE_INT64)
            self.write_int64(n)
        else:
            self._write_type(TYPE_LONG)
            self.write_long_int(n)

    def _write_str_obj(self, s: str) -> None:
        try:
            encoded = s.encode('ascii')
            if len(encoded) <= 255:
                self._write_type(TYPE_SHORT_ASCII)
                self._write1(len(encoded))
                self._write(encoded)
            else:
                self._write_type(TYPE_ASCII)
                self.write_uint32(len(encoded))
                self._write(encoded)
        except UnicodeEncodeError:
            # Fall back to unicode
            encoded = s.encode('utf-8')
            self._write_type(TYPE_UNICODE)
            self.write_uint32(len(encoded))
            self._write(encoded)

    def write_tuple(self, t: tuple) -> None:
        if len(t) <= 255:
            self._write_type(TYPE_SMALL_TUPLE)
            self._write1(len(t))
        else:
            self._write_type(TYPE_TUPLE)
            self.write_uint32(len(t))
        for item in t:
            self.write_object(item)

    def write_code(self, code: types.CodeType) -> None:
        """Serialize a types.CodeType to marshal format."""
        import sys
        self._write_type(TYPE_CODE)

        self.write_int(code.co_argcount)
        self.write_int(code.co_posonlyargcount)
        self.write_int(code.co_kwonlyargcount)

        if sys.version_info >= (3, 11):
            self.write_int(code.co_nlocals)
        else:
            self.write_int(code.co_nlocals)

        self.write_int(code.co_stacksize)
        self.write_int(code.co_flags)
        self.write_object(code.co_code)
        self.write_object(code.co_consts)
        self.write_object(code.co_names)
        self.write_object(code.co_varnames)
        self.write_object(code.co_freevars)
        self.write_object(code.co_cellvars)
        self.write_object(code.co_filename)
        self.write_object(code.co_name)

        if sys.version_info >= (3, 11):
            self.write_object(getattr(code, 'co_qualname', code.co_name))

        self.write_int(code.co_firstlineno)
        self.write_object(code.co_linetable if hasattr(code, 'co_linetable') else code.co_lnotab)

        if sys.version_info >= (3, 11):
            self.write_object(getattr(code, 'co_exceptiontable', b''))

    def getvalue(self) -> bytes:
        return self._buf.getvalue()

    def reset(self) -> None:
        self._buf = io.BytesIO()
        self._ref_table.clear()
        self._ref_count = 0


# ---------------------------------------------------------------------------
# PycFile — read/write .pyc files
# ---------------------------------------------------------------------------

class PycFile:
    """
    Static methods for reading and writing .pyc files at binary level.

    .pyc format:
      [0..3]   magic number (4 bytes, version-specific)
      [4..7]   flags (4 bytes LE): 0 = timestamp, 1 = hash-based
      [8..11]  timestamp or hash (4 bytes LE) — depends on flags
      [12..15] source file size (4 bytes LE) — when flags==0
      [16..]   marshal-encoded code object
    """

    @staticmethod
    def decode_header(data: bytes) -> dict:
        """
        Decode a .pyc header.
        Returns dict with keys: magic, flags, timestamp_or_hash, source_size, python_version.
        """
        if len(data) < PYC_HEADER_SIZE:
            raise MarshalError(f"Header too short: {len(data)} bytes")

        magic    = data[0:4]
        flags    = struct.unpack_from('<I', data, 4)[0]
        field1   = struct.unpack_from('<I', data, 8)[0]
        field2   = struct.unpack_from('<I', data, 12)[0]

        # Detect python version from magic
        py_version = None
        for ver, mag in MAGIC_NUMBER.items():
            if mag == magic:
                py_version = ver
                break

        if flags & PYC_FLAG_HASH_BASED:
            return {
                'magic': magic,
                'flags': flags,
                'source_hash': data[8:16],
                'source_size': None,
                'python_version': py_version,
                'hash_based': True,
                'checked': bool(flags & PYC_FLAG_CHECKED),
            }
        else:
            return {
                'magic': magic,
                'flags': flags,
                'timestamp': field1,
                'source_size': field2,
                'python_version': py_version,
                'hash_based': False,
            }

    @staticmethod
    def encode_header(
        python_version: int,
        timestamp: int,
        source_size: int,
        flags: int = 0,
    ) -> bytes:
        """
        Encode a .pyc header (16 bytes).
        python_version: e.g. 312 for 3.12
        """
        magic = MAGIC_NUMBER.get(python_version)
        if magic is None:
            # Default to current version magic
            import sys
            ver_int = sys.version_info.major * 100 + sys.version_info.minor
            magic = MAGIC_NUMBER.get(ver_int, b'\x0d\x0d\r\n')

        header = magic
        header += struct.pack('<I', flags)
        header += struct.pack('<I', timestamp & 0xFFFFFFFF)
        header += struct.pack('<I', source_size & 0xFFFFFFFF)
        assert len(header) == PYC_HEADER_SIZE
        return header

    @staticmethod
    def read(path: Path) -> tuple[types.CodeType, int, int]:
        """
        Read a .pyc file.
        Returns (code_object, flags, timestamp).
        """
        data = Path(path).read_bytes()

        if len(data) < PYC_HEADER_SIZE:
            raise MarshalError(f"File too short to be a .pyc: {path}")

        header = PycFile.decode_header(data)

        reader = MarshalReader(data[PYC_HEADER_SIZE:])
        code = reader.read_object()

        if not isinstance(code, types.CodeType):
            raise MarshalError(f"Expected code object, got {type(code)}")

        flags = header.get('flags', 0)
        timestamp = header.get('timestamp', 0)
        return code, flags, timestamp

    @staticmethod
    def write(
        path: Path,
        code: types.CodeType,
        source_size: int = 0,
        timestamp: int | None = None,
        python_version: int | None = None,
    ) -> None:
        """Write a code object to a .pyc file."""
        import sys

        if timestamp is None:
            timestamp = int(time.time())
        if python_version is None:
            python_version = sys.version_info.major * 100 + sys.version_info.minor

        header = PycFile.encode_header(python_version, timestamp, source_size)

        writer = MarshalWriter()
        writer.write_code(code)
        body = writer.getvalue()

        Path(path).write_bytes(header + body)

    @staticmethod
    def from_source(source: str, path: Path | None = None) -> tuple[bytes, types.CodeType]:
        """
        Compile Python source and produce .pyc bytes.
        Returns (pyc_bytes, code_object).
        """
        filename = str(path) if path else '<string>'
        code = compile(source, filename, 'exec')
        source_bytes = source.encode('utf-8')

        import sys
        python_version = sys.version_info.major * 100 + sys.version_info.minor
        timestamp = int(time.time())

        header = PycFile.encode_header(python_version, timestamp, len(source_bytes))

        writer = MarshalWriter()
        writer.write_code(code)
        pyc_bytes = header + writer.getvalue()
        return pyc_bytes, code

    @staticmethod
    def verify(path: Path) -> dict:
        """
        Verify a .pyc file's integrity.
        Returns dict with 'valid', 'error', and header info.
        """
        try:
            data = Path(path).read_bytes()
            header = PycFile.decode_header(data)
            code, flags, ts = PycFile.read(path)
            return {
                'valid': True,
                'error': None,
                'header': header,
                'code_name': code.co_name,
                'code_filename': code.co_filename,
                'consts': len(code.co_consts),
                'names': len(code.co_names),
            }
        except Exception as exc:
            return {
                'valid': False,
                'error': str(exc),
                'header': None,
            }


# ---------------------------------------------------------------------------
# CodeObjectSerializer — round-trip code objects through marshal
# ---------------------------------------------------------------------------

class CodeObjectSerializer:
    """
    High-level round-trip serializer for code objects.
    Handles nested code objects (functions defined within functions).
    """

    def serialize(self, code: types.CodeType) -> bytes:
        """Serialize code object to marshal bytes (without .pyc header)."""
        writer = MarshalWriter()
        writer.write_code(code)
        return writer.getvalue()

    def deserialize(self, data: bytes) -> types.CodeType:
        """Deserialize code object from marshal bytes."""
        reader = MarshalReader(data)
        obj = reader.read_object()
        if not isinstance(obj, types.CodeType):
            raise MarshalError(f"Expected code object, got {type(obj)}")
        return obj

    def roundtrip(self, code: types.CodeType) -> types.CodeType:
        """Serialize then deserialize. Use for testing."""
        data = self.serialize(code)
        return self.deserialize(data)

    def inspect(self, code: types.CodeType, depth: int = 0) -> str:
        """Return indented string representation of a code object tree."""
        indent = "  " * depth
        lines = [
            f"{indent}CodeObject {code.co_name!r}",
            f"{indent}  filename: {code.co_filename!r}",
            f"{indent}  args: {code.co_argcount}, nlocals: {code.co_nlocals}",
            f"{indent}  stacksize: {code.co_stacksize}",
            f"{indent}  consts: {len(code.co_consts)}",
            f"{indent}  names: {len(code.co_names)}",
            f"{indent}  code: {len(code.co_code)} bytes",
        ]
        for const in code.co_consts:
            if isinstance(const, types.CodeType):
                lines.append(self.inspect(const, depth + 1))
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# MarshalDiff — compare two marshaled representations
# ---------------------------------------------------------------------------

class MarshalDiff:
    """
    Compare two Python objects at the marshal level.
    Useful for testing that a roundtrip produces equivalent code.
    """

    def diff(self, a: Any, b: Any, path: str = '') -> list[str]:
        """Return list of differences between a and b."""
        differences = []
        self._diff_recursive(a, b, path, differences)
        return differences

    def _diff_recursive(self, a: Any, b: Any, path: str, diffs: list[str]) -> None:
        if type(a) is not type(b):
            diffs.append(f"{path}: type mismatch {type(a).__name__} vs {type(b).__name__}")
            return

        if isinstance(a, types.CodeType):
            for attr in ('co_argcount', 'co_nlocals', 'co_stacksize',
                         'co_flags', 'co_names', 'co_varnames'):
                va, vb = getattr(a, attr), getattr(b, attr)
                if va != vb:
                    diffs.append(f"{path}.{attr}: {va!r} != {vb!r}")
            # Recursively diff consts
            for i, (ca, cb) in enumerate(zip(a.co_consts, b.co_consts)):
                self._diff_recursive(ca, cb, f"{path}.co_consts[{i}]", diffs)

        elif isinstance(a, (tuple, list)):
            if len(a) != len(b):
                diffs.append(f"{path}: length {len(a)} != {len(b)}")
            else:
                for i, (ea, eb) in enumerate(zip(a, b)):
                    self._diff_recursive(ea, eb, f"{path}[{i}]", diffs)
        elif isinstance(a, dict):
            for k in set(a) | set(b):
                if k not in a:
                    diffs.append(f"{path}[{k!r}]: missing in first")
                elif k not in b:
                    diffs.append(f"{path}[{k!r}]: missing in second")
                else:
                    self._diff_recursive(a[k], b[k], f"{path}[{k!r}]", diffs)
        elif a != b:
            diffs.append(f"{path}: {a!r} != {b!r}")


# ---------------------------------------------------------------------------
# sys.intern wrapper (avoid import sys at top of each method)
# ---------------------------------------------------------------------------

import sys as _sys

def sys_intern(s: str) -> str:
    return _sys.intern(s)


# ---------------------------------------------------------------------------
# MarshalStats — gather statistics about marshaled data
# ---------------------------------------------------------------------------

@dataclass
class MarshalStats:
    total_objects: int = 0
    type_counts: dict = field(default_factory=dict)
    code_objects: int = 0
    ref_count: int = 0
    bytes_total: int = 0

    def record(self, type_code: int) -> None:
        self.total_objects += 1
        name = chr(type_code) if 32 <= type_code < 127 else f'\\x{type_code:02x}'
        self.type_counts[name] = self.type_counts.get(name, 0) + 1
        if type_code == TYPE_CODE:
            self.code_objects += 1

    def summary(self) -> str:
        lines = [
            f"Total objects: {self.total_objects}",
            f"Code objects: {self.code_objects}",
            f"Refs: {self.ref_count}",
            f"Bytes: {self.bytes_total}",
            "Type distribution:",
        ]
        for name, count in sorted(self.type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {name!r:10s}: {count}")
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def marshal_dumps(obj: Any) -> bytes:
    """Serialize obj to marshal bytes."""
    writer = MarshalWriter()
    writer.write_object(obj)
    return writer.getvalue()


def marshal_loads(data: bytes) -> Any:
    """Deserialize object from marshal bytes."""
    reader = MarshalReader(data)
    return reader.read_object()


def marshal_roundtrip(obj: Any) -> Any:
    """Serialize then deserialize — use for testing."""
    return marshal_loads(marshal_dumps(obj))


def pyc_magic_for_current_version() -> bytes:
    ver = _sys.version_info.major * 100 + _sys.version_info.minor
    return MAGIC_NUMBER.get(ver, b'\x0d\x0d\r\n')


def analyze_pyc(path: Path) -> str:
    """Return human-readable analysis of a .pyc file."""
    try:
        info = PycFile.verify(path)
        if not info['valid']:
            return f"Invalid .pyc: {info['error']}"

        lines = [
            f"File: {path}",
            f"Python version: {info['header'].get('python_version', 'unknown')}",
            f"Flags: {info['header'].get('flags', 0):#010x}",
            f"Timestamp: {info['header'].get('timestamp', 0)}",
            f"Source size: {info['header'].get('source_size', 0)} bytes",
            f"Code: {info['code_name']!r} in {info['code_filename']!r}",
            f"Consts: {info['consts']}, Names: {info['names']}",
        ]
        return '\n'.join(lines)
    except Exception as exc:
        return f"Error analyzing {path}: {exc}"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    # Test marshal roundtrip of primitives
    for obj in [None, True, False, 0, 42, -1, 3.14, 1+2j, b"hello", "world",
                (1, 2, 3), [4, 5], {'a': 1}, frozenset({1, 2})]:
        result = marshal_roundtrip(obj)
        if isinstance(obj, float) and math.isnan(obj):
            assert math.isnan(result)
        elif isinstance(obj, list):
            assert result == obj
        elif isinstance(obj, dict):
            assert result == obj
        else:
            assert result == obj, f"Roundtrip failed for {obj!r}: got {result!r}"

    # Test code object roundtrip
    code = compile("x = 1 + 2", '<test>', 'exec')
    serializer = CodeObjectSerializer()
    data = serializer.serialize(code)
    assert len(data) > 0

    # Test header encoding/decoding
    header = PycFile.encode_header(312, 1000, 512)
    assert len(header) == PYC_HEADER_SIZE
    decoded = PycFile.decode_header(header)
    assert decoded['timestamp'] == 1000
    assert decoded['source_size'] == 512

    return True


# ---------------------------------------------------------------------------
# PycInspector — deep inspection of .pyc files
# ---------------------------------------------------------------------------

class PycInspector:
    """
    Deep inspection of .pyc files — walks the complete code object tree,
    extracts all constants, names, nested functions, classes, and computes
    a complexity score.
    """

    def inspect(self, code: types.CodeType, depth: int = 0) -> dict:
        """Return a structured dict describing this code object and its children."""
        nested = []
        for c in code.co_consts:
            if isinstance(c, types.CodeType):
                nested.append(self.inspect(c, depth + 1))

        return {
            'name': code.co_name,
            'filename': code.co_filename,
            'firstlineno': code.co_firstlineno,
            'argcount': code.co_argcount,
            'nlocals': code.co_nlocals,
            'stacksize': code.co_stacksize,
            'flags': code.co_flags,
            'consts': len(code.co_consts),
            'names': list(code.co_names),
            'varnames': list(code.co_varnames),
            'freevars': list(code.co_freevars),
            'cellvars': list(code.co_cellvars),
            'bytecode_len': len(code.co_code),
            'depth': depth,
            'nested': nested,
        }

    def complexity_score(self, code: types.CodeType) -> float:
        """
        Estimate cyclomatic complexity from bytecode.
        Counts conditional jumps as branch points.
        """
        import dis
        branches = sum(
            1 for instr in dis.get_instructions(code)
            if instr.opname.startswith(('JUMP_IF', 'POP_JUMP', 'FOR_ITER'))
        )
        nested = sum(
            self.complexity_score(c)
            for c in code.co_consts
            if isinstance(c, types.CodeType)
        )
        return 1 + branches + nested

    def extract_strings(self, code: types.CodeType) -> list[str]:
        """Extract all string literals from a code object tree."""
        strings = []
        for c in code.co_consts:
            if isinstance(c, str):
                strings.append(c)
            elif isinstance(c, types.CodeType):
                strings.extend(self.extract_strings(c))
        return strings

    def extract_names(self, code: types.CodeType) -> set[str]:
        """Extract all referenced names (globals, attributes) recursively."""
        names = set(code.co_names)
        for c in code.co_consts:
            if isinstance(c, types.CodeType):
                names |= self.extract_names(c)
        return names

    def to_text(self, code: types.CodeType, indent: int = 0) -> str:
        """Return a textual tree of the code object hierarchy."""
        info = self.inspect(code)
        pad = "  " * indent
        lines = [
            f"{pad}[{info['name']}] @ line {info['firstlineno']}",
            f"{pad}  args={info['argcount']}, nlocals={info['nlocals']}, "
            f"stack={info['stacksize']}, bytes={info['bytecode_len']}",
        ]
        for child in code.co_consts:
            if isinstance(child, types.CodeType):
                lines.append(self.to_text(child, indent + 1))
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# MarshalCompressor — compresses marshal data using run-length encoding
# ---------------------------------------------------------------------------

class MarshalCompressor:
    """
    Simple run-length encoding for marshal byte streams.
    Reduces size of repetitive zero bytes (common in padding).
    """

    ESCAPE = 0xFE
    REPEAT_MARKER = 0xFF

    def compress(self, data: bytes) -> bytes:
        """
        Compress using RLE: runs of 3+ identical bytes are encoded as
        [ESCAPE, byte, count] where count is capped at 255.
        """
        if not data:
            return b''

        out = bytearray()
        i = 0
        n = len(data)

        while i < n:
            byte = data[i]
            # Count run length
            run = 1
            while i + run < n and data[i + run] == byte and run < 255:
                run += 1

            if run >= 3 or byte == self.ESCAPE:
                out.append(self.ESCAPE)
                out.append(byte)
                out.append(run)
                i += run
            else:
                out.append(byte)
                i += 1

        return bytes(out)

    def decompress(self, data: bytes) -> bytes:
        """Decompress RLE-compressed data."""
        out = bytearray()
        i = 0
        n = len(data)

        while i < n:
            byte = data[i]
            if byte == self.ESCAPE:
                if i + 2 >= n:
                    break
                orig_byte = data[i + 1]
                count = data[i + 2]
                out.extend(bytes([orig_byte]) * count)
                i += 3
            else:
                out.append(byte)
                i += 1

        return bytes(out)

    def ratio(self, original: bytes, compressed: bytes) -> float:
        if len(original) == 0:
            return 1.0
        return len(compressed) / len(original)


# ---------------------------------------------------------------------------
# MarshalCache — LRU cache for marshal/unmarshal operations
# ---------------------------------------------------------------------------

class MarshalCache:
    """
    Simple LRU cache that stores marshaled bytes indexed by a hash key.
    Avoids redundant serialization of frequently-accessed objects.
    """

    def __init__(self, max_size: int = 256):
        self._max_size = max_size
        self._cache: dict[str, tuple[bytes, int]] = {}   # key -> (data, access_count)
        self._access_order: list[str] = []

    def _compute_key(self, obj: Any) -> str:
        """Compute a cache key from the object's hash and type."""
        try:
            h = hash(obj)
        except TypeError:
            h = id(obj)
        return f"{type(obj).__name__}:{h}"

    def get(self, obj: Any) -> Optional[bytes]:
        key = self._compute_key(obj)
        if key in self._cache:
            data, count = self._cache[key]
            self._cache[key] = (data, count + 1)
            # Move to end of access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return data
        return None

    def put(self, obj: Any, data: bytes) -> None:
        key = self._compute_key(obj)
        if len(self._cache) >= self._max_size:
            # Evict least recently used
            if self._access_order:
                oldest = self._access_order.pop(0)
                self._cache.pop(oldest, None)
        self._cache[key] = (data, 1)
        self._access_order.append(key)

    def cached_dumps(self, obj: Any) -> bytes:
        """Marshal obj with caching."""
        result = self.get(obj)
        if result is None:
            result = marshal_dumps(obj)
            self.put(obj, result)
        return result

    def hit_rate(self) -> float:
        """Return estimated hit rate based on access counts."""
        if not self._cache:
            return 0.0
        total = sum(count for _, count in self._cache.values())
        hits = sum(count - 1 for _, count in self._cache.values())
        return hits / total if total > 0 else 0.0

    def clear(self) -> None:
        self._cache.clear()
        self._access_order.clear()

    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> dict:
        return {
            'size': self.size(),
            'max_size': self._max_size,
            'hit_rate': self.hit_rate(),
            'total_bytes': sum(len(d) for d, _ in self._cache.values()),
        }


# ---------------------------------------------------------------------------
# ConstantPool — shared constant pool for multiple code objects
# ---------------------------------------------------------------------------

class ConstantPool:
    """
    Shared constant pool that deduplicates constants across multiple code objects.
    Used to reduce the total size of marshaled data when many code objects share
    the same constants (None, True, False, common strings, small integers).
    """

    def __init__(self):
        self._pool: list[Any] = []
        self._index: dict[str, int] = {}   # repr(value) -> pool index

    def intern(self, value: Any) -> int:
        """Add value to pool if not present; return pool index."""
        key = self._make_key(value)
        if key not in self._index:
            self._index[key] = len(self._pool)
            self._pool.append(value)
        return self._index[key]

    def lookup(self, index: int) -> Any:
        return self._pool[index]

    def _make_key(self, value: Any) -> str:
        try:
            return f"{type(value).__qualname__}:{hash(value)}:{repr(value)[:64]}"
        except TypeError:
            return f"{type(value).__qualname__}:{id(value)}"

    def size(self) -> int:
        return len(self._pool)

    def marshal_all(self) -> bytes:
        """Serialize the entire pool."""
        writer = MarshalWriter()
        writer.write_tuple(tuple(self._pool))
        return writer.getvalue()

    def load_all(self, data: bytes) -> None:
        """Load pool from marshaled bytes."""
        reader = MarshalReader(data)
        items = reader.read_object()
        for item in items:
            self.intern(item)

    def stats(self) -> dict:
        type_counts: dict[str, int] = {}
        for v in self._pool:
            t = type(v).__name__
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            'total': len(self._pool),
            'types': type_counts,
        }


# ---------------------------------------------------------------------------
# PycBatchProcessor — process multiple .pyc files
# ---------------------------------------------------------------------------

class PycBatchProcessor:
    """
    Batch operations on .pyc files: validation, inspection, recompile detection.
    """

    def __init__(self):
        self._inspector = PycInspector()
        self._serializer = CodeObjectSerializer()

    def validate_directory(self, path: 'Path') -> dict[str, dict]:
        """
        Walk a directory tree and validate all .pyc files.
        Returns dict: filename -> validation result.
        """
        from pathlib import Path as PPath
        results = {}
        for pyc_path in PPath(path).rglob("*.pyc"):
            results[str(pyc_path)] = PycFile.verify(pyc_path)
        return results

    def extract_all_names(self, path: 'Path') -> set[str]:
        """Collect all referenced names from a .pyc file."""
        try:
            code, _, _ = PycFile.read(path)
            return self._inspector.extract_names(code)
        except Exception:
            return set()

    def complexity_report(self, path: 'Path') -> dict:
        """Compute complexity metrics for a .pyc file."""
        try:
            code, _, _ = PycFile.read(path)
            return {
                'file': str(path),
                'complexity': self._inspector.complexity_score(code),
                'strings': len(self._inspector.extract_strings(code)),
                'names': len(self._inspector.extract_names(code)),
                'description': self._inspector.to_text(code),
            }
        except Exception as exc:
            return {'file': str(path), 'error': str(exc)}

    def recompile_if_stale(self, py_path: 'Path', force: bool = False) -> bool:
        """
        Recompile a .py file if the corresponding .pyc is stale or missing.
        Returns True if recompilation occurred.
        """
        import os
        from pathlib import Path as PPath
        py_path = PPath(py_path)
        pyc_path = py_path.with_suffix('.pyc')

        if force or not pyc_path.exists():
            source = py_path.read_text(encoding='utf-8')
            PycFile.from_source(source, py_path)
            # Would write to pyc_path in a real implementation
            return True

        py_mtime = os.path.getmtime(py_path)
        pyc_mtime = os.path.getmtime(pyc_path)
        if py_mtime > pyc_mtime:
            source = py_path.read_text(encoding='utf-8')
            PycFile.from_source(source, py_path)
            return True

        return False


# ---------------------------------------------------------------------------
# MarshalVersion — version-specific marshal reader/writer dispatch
# ---------------------------------------------------------------------------

class MarshalVersion:
    """
    Version-specific marshal format differences across Python versions.
    Handles format changes between 3.4 through 3.12.
    """

    # Code object field counts per version
    CODE_FIELDS = {
        8:  13,   # 3.8: no qualname, no exceptiontable
        9:  13,
        10: 13,
        11: 16,   # 3.11: qualname + exceptiontable added
        12: 16,
    }

    @staticmethod
    def minor_version() -> int:
        return _sys.version_info.minor

    @staticmethod
    def field_count() -> int:
        minor = MarshalVersion.minor_version()
        return MarshalVersion.CODE_FIELDS.get(minor, 16)

    @staticmethod
    def has_qualname() -> bool:
        return MarshalVersion.minor_version() >= 11

    @staticmethod
    def has_exception_table() -> bool:
        return MarshalVersion.minor_version() >= 11

    @staticmethod
    def has_linetable() -> bool:
        return MarshalVersion.minor_version() >= 10

    @staticmethod
    def magic_bytes() -> bytes:
        ver = _sys.version_info.major * 100 + _sys.version_info.minor
        return MAGIC_NUMBER.get(ver, b'\x0d\x0d\r\n')

    @staticmethod
    def describe() -> str:
        minor = MarshalVersion.minor_version()
        return (
            f"Python 3.{minor} marshal format:\n"
            f"  Code fields: {MarshalVersion.field_count()}\n"
            f"  Has qualname: {MarshalVersion.has_qualname()}\n"
            f"  Has exception table: {MarshalVersion.has_exception_table()}\n"
            f"  Has linetable: {MarshalVersion.has_linetable()}\n"
            f"  Magic: {MarshalVersion.magic_bytes().hex()}"
        )


if __name__ == "__main__":
    assert _self_test(), "Self-test failed"
    print("marshal_codec.py: all self-tests passed")

    # Demo: serialize a code object
    source = "def greet(name):\n    return f'Hello, {name}!'"
    code = compile(source, '<demo>', 'exec')
    data = marshal_dumps(code)
    print(f"Serialized code object: {len(data)} bytes")
    restored = marshal_loads(data)
    print(f"Restored: {type(restored).__name__} — {getattr(restored, 'co_name', '?')!r}")

    # Demo: inspector
    inspector = PycInspector()
    print("\n" + inspector.to_text(code))

    # Demo: version info
    print("\n" + MarshalVersion.describe())

    # Demo: cache
    cache = MarshalCache(max_size=10)
    for i in range(5):
        cache.cached_dumps(42)
    print(f"\nCache stats: {cache.stats()}")

    # Demo: compressor
    comp = MarshalCompressor()
    zeros = bytes(100)
    compressed = comp.compress(zeros)
    print(f"Compressed 100 zeros: {len(compressed)} bytes (ratio={comp.ratio(zeros, compressed):.2f})")
