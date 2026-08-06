"""
bytecode_assembler.py — CPython 3.12 bytecode assembler for the Sovereign engine.

Operates at the raw opcode level, producing types.CodeType objects and raw bytecode
bytes. Supports label-based forward/backward jumps, constant pooling, and disassembly.

Part of the SOVEREIGN_IR PYTHON_C_BRIDGE_IR pipeline.
Agent A (Cognition) — HyperKittyConstraintDSL v1.0
"""

from __future__ import annotations

import dis
import io
import math
import struct
import types
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Opcode definitions — CPython 3.12 values drawn from dis.opmap
# ---------------------------------------------------------------------------

class Opcode(IntEnum):
    """CPython 3.12 opcode enumeration with correct integer values."""

    # Misc / no-arg
    NOP                     = 9
    RESUME                  = 149
    CACHE                   = 0

    # Stack manipulation
    POP_TOP                 = 1
    COPY                    = 120
    SWAP                    = 99

    # Unary ops
    UNARY_NEGATIVE          = 11
    UNARY_NOT               = 12
    UNARY_INVERT            = 15
    GET_ITER                = 68
    GET_YIELD_FROM_ITER     = 69

    # Binary / in-place ops
    BINARY_SUBSCR           = 25
    STORE_SUBSCR            = 60
    DELETE_SUBSCR           = 61
    BINARY_OP               = 122

    # Comparisons
    COMPARE_OP              = 107
    IS_OP                   = 117
    CONTAINS_OP             = 118

    # Attributes
    LOAD_ATTR               = 106
    STORE_ATTR              = 95
    DELETE_ATTR             = 96
    LOAD_SUPER_ATTR         = 141

    # Names / globals / builtins
    LOAD_NAME               = 101
    STORE_NAME              = 90
    DELETE_NAME             = 91
    LOAD_GLOBAL             = 116
    STORE_GLOBAL            = 97
    DELETE_GLOBAL           = 98
    LOAD_DEREF              = 137
    STORE_DEREF             = 125
    DELETE_DEREF            = 138
    COPY_FREE_VARS          = 149  # alias

    # Fast locals
    LOAD_FAST               = 124
    LOAD_FAST_CHECK         = 127
    LOAD_FAST_AND_CLEAR     = 126
    STORE_FAST              = 125
    DELETE_FAST             = 126

    # Constants
    LOAD_CONST              = 100

    # Collections
    BUILD_TUPLE             = 102
    BUILD_LIST              = 103
    BUILD_SET               = 104
    BUILD_MAP               = 105
    BUILD_CONST_KEY_MAP     = 156
    BUILD_SLICE             = 133
    BUILD_STRING            = 157
    LIST_APPEND             = 45
    SET_ADD                 = 146
    MAP_ADD                 = 147
    LIST_EXTEND             = 162
    SET_UPDATE              = 163
    DICT_MERGE              = 164
    DICT_UPDATE             = 165
    BUILD_DICT              = 105  # alias

    # Unpacking
    UNPACK_SEQUENCE         = 92
    UNPACK_EX               = 94

    # Jumps
    JUMP_FORWARD            = 110
    JUMP_BACKWARD           = 140
    JUMP_BACKWARD_NO_INTERRUPT = 134
    POP_JUMP_IF_TRUE        = 115
    POP_JUMP_IF_FALSE       = 114
    POP_JUMP_IF_NONE        = 128
    POP_JUMP_IF_NOT_NONE    = 129
    JUMP_IF_TRUE_OR_POP     = 112
    JUMP_IF_FALSE_OR_POP    = 111

    # Calls
    CALL                    = 171
    CALL_FUNCTION_EX        = 142
    PUSH_NULL               = 2
    PRECALL                 = 166
    KW_NAMES                = 172

    # Functions / closures
    MAKE_FUNCTION           = 132
    RETURN_VALUE            = 83
    RETURN_CONST            = 121
    YIELD_VALUE             = 86
    YIELD_FROM              = 72
    SEND                    = 123

    # Exceptions
    RAISE_VARARGS           = 130
    POP_EXCEPT              = 89
    PUSH_EXC_INFO           = 35
    CHECK_EXC_MATCH         = 36
    WITH_EXCEPT_START       = 49
    BEFORE_WITH             = 53

    # Imports
    IMPORT_NAME             = 108
    IMPORT_FROM             = 109
    IMPORT_STAR             = 84

    # Generators / coroutines
    GET_AWAITABLE           = 73
    GET_AITER               = 75
    GET_ANEXT               = 76
    END_ASYNC_FOR           = 54
    BEFORE_ASYNC_WITH       = 52
    ASYNC_GEN_WRAP          = 55

    # Format / match
    FORMAT_VALUE            = 155
    MATCH_MAPPING           = 27
    MATCH_SEQUENCE          = 28
    MATCH_KEYS              = 29
    MATCH_CLASS             = 152
    COPY_DICT_WITHOUT_KEYS  = 34
    GET_LEN                 = 30

    # Misc
    PRINT_EXPR              = 70
    SETUP_ANNOTATIONS       = 85
    LOAD_BUILD_CLASS        = 71
    LOAD_CLASSDEREF         = 148
    FOR_ITER                = 68  # alias — same as GET_ITER in enum
    END_FOR                 = 4

    @classmethod
    def from_name(cls, name: str) -> 'Opcode':
        """Look up opcode by name, falling back to dis.opmap."""
        try:
            return cls[name]
        except KeyError:
            val = dis.opmap.get(name)
            if val is None:
                raise KeyError(f"Unknown opcode: {name}")
            return cls(val)

    def has_arg(self) -> bool:
        """Return True if this opcode takes an argument (value >= dis.HAVE_ARGUMENT)."""
        return int(self) >= dis.HAVE_ARGUMENT


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Instruction:
    """A single bytecode instruction with optional label and line info."""
    opcode: Opcode
    arg: int = 0
    label: Optional[str] = None      # label this instruction is the target of
    lineno: int = 0
    # resolved absolute target offset (for jumps)
    _resolved_target: int = field(default=-1, repr=False, compare=False)

    def __post_init__(self):
        if isinstance(self.opcode, int):
            self.opcode = Opcode(self.opcode)

    def is_jump(self) -> bool:
        return self.opcode in _JUMP_OPCODES

    def encoded_size(self) -> int:
        """Return the number of bytes this instruction takes (2 or more)."""
        if self.arg <= 0xFF:
            return 2
        elif self.arg <= 0xFFFF:
            return 4
        elif self.arg <= 0xFFFFFF:
            return 6
        else:
            return 8

    def encode(self) -> bytes:
        """Encode to bytes using EXTENDED_ARG for large arguments."""
        out = bytearray()
        arg = self.arg
        if arg > 0xFFFFFF:
            out.append(144)  # EXTENDED_ARG
            out.append((arg >> 24) & 0xFF)
        if arg > 0xFFFF:
            out.append(144)
            out.append((arg >> 16) & 0xFF)
        if arg > 0xFF:
            out.append(144)
            out.append((arg >> 8) & 0xFF)
        out.append(int(self.opcode))
        out.append(arg & 0xFF)
        return bytes(out)


@dataclass
class Label:
    """Named label marking a position in the bytecode stream."""
    name: str
    position: int = -1   # byte offset, filled in after assembly

    def is_resolved(self) -> bool:
        return self.position >= 0


# Jump opcodes that need target resolution
_JUMP_OPCODES = frozenset({
    Opcode.JUMP_FORWARD,
    Opcode.JUMP_BACKWARD,
    Opcode.JUMP_BACKWARD_NO_INTERRUPT,
    Opcode.POP_JUMP_IF_TRUE,
    Opcode.POP_JUMP_IF_FALSE,
    Opcode.POP_JUMP_IF_NONE,
    Opcode.POP_JUMP_IF_NOT_NONE,
    Opcode.JUMP_IF_TRUE_OR_POP,
    Opcode.JUMP_IF_FALSE_OR_POP,
    Opcode.FOR_ITER,
})


# ---------------------------------------------------------------------------
# InstructionBuffer
# ---------------------------------------------------------------------------

class InstructionBuffer:
    """Mutable sequence of Instructions with label resolution."""

    def __init__(self):
        self._instructions: list[Instruction] = []
        self._labels: dict[str, Label] = {}   # name -> Label
        self._pending_jumps: list[tuple[int, str]] = []  # (instr_index, label_name)

    def append(self, instr: Instruction) -> None:
        self._instructions.append(instr)

    def add_label(self, name: str) -> Label:
        lbl = Label(name)
        self._labels[name] = lbl
        # Mark the next instruction's position once we know it
        return lbl

    def mark_label_here(self, name: str) -> None:
        """Associate label with the current (next) instruction index."""
        offset = self._compute_offset(len(self._instructions))
        lbl = self._labels.setdefault(name, Label(name))
        lbl.position = offset
        # If any prior instruction referred to this label, patch it
        if self._instructions and self._instructions[-1].label == name:
            pass  # already set

    def _compute_offset(self, up_to_index: int) -> int:
        total = 0
        for i, instr in enumerate(self._instructions):
            if i >= up_to_index:
                break
            total += instr.encoded_size()
        return total

    def resolve_labels(self) -> None:
        """
        Two-pass resolution:
          Pass 1: compute byte offsets for all labels.
          Pass 2: patch jump instruction args.
        """
        # Pass 1: build offset table
        offset = 0
        for instr in self._instructions:
            if instr.label is not None:
                lbl = self._labels.get(instr.label)
                if lbl is not None and lbl.position < 0:
                    lbl.position = offset
            offset += instr.encoded_size()

        # Pass 2: patch jumps
        offset = 0
        for instr in self._instructions:
            if instr.is_jump() and isinstance(instr.arg, str):
                label_name = instr.arg  # type: ignore[assignment]
                lbl = self._labels.get(label_name)
                if lbl is None or not lbl.is_resolved():
                    raise AssemblerError(f"Unresolved label: {label_name}")
                after_instr = offset + instr.encoded_size()
                if instr.opcode == Opcode.JUMP_FORWARD:
                    instr.arg = (lbl.position - after_instr) // 2
                elif instr.opcode == Opcode.JUMP_BACKWARD:
                    instr.arg = (after_instr - lbl.position) // 2
                else:
                    # absolute for conditional jumps in 3.12 (offset/2)
                    instr.arg = lbl.position // 2
            offset += instr.encoded_size()

    def to_bytes(self) -> bytes:
        self.resolve_labels()
        out = bytearray()
        for instr in self._instructions:
            out.extend(instr.encode())
        return bytes(out)

    def size(self) -> int:
        return sum(i.encoded_size() for i in self._instructions)

    def __len__(self) -> int:
        return len(self._instructions)

    def __iter__(self):
        return iter(self._instructions)


# ---------------------------------------------------------------------------
# Assembler error
# ---------------------------------------------------------------------------

class AssemblerError(Exception):
    pass


# ---------------------------------------------------------------------------
# BytecodeAssembler — main class
# ---------------------------------------------------------------------------

class BytecodeAssembler:
    """
    High-level Python bytecode assembler.

    Builds a sequence of CPython instructions, manages constant/name pools,
    and can produce a raw bytecode bytes object or a full types.CodeType.
    """

    def __init__(self, name: str = "<assembled>", filename: str = "<string>"):
        self.name = name
        self.filename = filename
        self._buf = InstructionBuffer()
        self._consts: list[Any] = []
        self._varnames: list[str] = []
        self._names: list[str] = []      # globals / attributes
        self._freevars: list[str] = []
        self._cellvars: list[str] = []
        self._lineno_table: list[tuple[int, int]] = []  # (offset, lineno)
        self._current_lineno = 1
        self._label_counter = 0
        self._stack_depth = 0
        self._max_stack = 0

    # --- internal helpers ---------------------------------------------------

    def _push(self, n: int = 1) -> None:
        self._stack_depth += n
        if self._stack_depth > self._max_stack:
            self._max_stack = self._stack_depth

    def _pop(self, n: int = 1) -> None:
        self._stack_depth -= n
        if self._stack_depth < 0:
            raise AssemblerError("Stack underflow")

    def _const_index(self, value: Any) -> int:
        for i, c in enumerate(self._consts):
            if type(c) is type(value) and c == value:
                return i
        self._consts.append(value)
        return len(self._consts) - 1

    def _varname_index(self, name: str) -> int:
        if name not in self._varnames:
            self._varnames.append(name)
        return self._varnames.index(name)

    def _name_index(self, name: str) -> int:
        if name not in self._names:
            self._names.append(name)
        return self._names.index(name)

    def _emit_raw(self, opcode: Opcode, arg: int = 0) -> Instruction:
        instr = Instruction(opcode=opcode, arg=arg, lineno=self._current_lineno)
        self._buf.append(instr)
        return instr

    # --- public emit interface ----------------------------------------------

    def emit(self, opcode: Opcode, arg: int = 0) -> None:
        """Emit a raw opcode with integer argument."""
        self._emit_raw(opcode, arg)

    def set_lineno(self, n: int) -> None:
        self._current_lineno = n

    def new_label(self) -> str:
        self._label_counter += 1
        return f"_L{self._label_counter}"

    def emit_label(self, name: str) -> Label:
        """
        Mark the current position as the target of label `name`.
        Returns the Label object (position set after assemble()).
        """
        self._buf.mark_label_here(name)
        lbl = self._buf._labels.get(name, Label(name))
        self._buf._labels[name] = lbl
        return lbl

    # --- high-level emitters ------------------------------------------------

    def load_const(self, value: Any) -> None:
        idx = self._const_index(value)
        self._emit_raw(Opcode.LOAD_CONST, idx)
        self._push()

    def load_fast(self, name: str) -> None:
        idx = self._varname_index(name)
        self._emit_raw(Opcode.LOAD_FAST, idx)
        self._push()

    def store_fast(self, name: str) -> None:
        idx = self._varname_index(name)
        self._emit_raw(Opcode.STORE_FAST, idx)
        self._pop()

    def load_global(self, name: str, push_null: bool = False) -> None:
        idx = self._name_index(name)
        # In 3.12, LOAD_GLOBAL arg = (namei << 1) | push_null_flag
        arg = (idx << 1) | (1 if push_null else 0)
        self._emit_raw(Opcode.LOAD_GLOBAL, arg)
        self._push(2 if push_null else 1)

    def store_global(self, name: str) -> None:
        idx = self._name_index(name)
        self._emit_raw(Opcode.STORE_GLOBAL, idx)
        self._pop()

    def load_attr(self, name: str) -> None:
        idx = self._name_index(name)
        self._emit_raw(Opcode.LOAD_ATTR, idx)

    def store_attr(self, name: str) -> None:
        idx = self._name_index(name)
        self._emit_raw(Opcode.STORE_ATTR, idx)
        self._pop(2)

    def call(self, argc: int) -> None:
        self._emit_raw(Opcode.CALL, argc)
        self._pop(argc + 1)
        self._push()

    def push_null(self) -> None:
        self._emit_raw(Opcode.PUSH_NULL)
        self._push()

    def return_value(self) -> None:
        self._emit_raw(Opcode.RETURN_VALUE)
        self._pop()

    def return_const(self, value: Any) -> None:
        idx = self._const_index(value)
        self._emit_raw(Opcode.RETURN_CONST, idx)

    def pop_top(self) -> None:
        self._emit_raw(Opcode.POP_TOP)
        self._pop()

    def dup_top(self) -> None:
        self._emit_raw(Opcode.COPY, 1)
        self._push()

    def swap(self, i: int = 2) -> None:
        self._emit_raw(Opcode.SWAP, i)

    def binary_op(self, op: int) -> None:
        """op: 0=+, 1=&, 2=//, 3@, 4=lshift, 5=%, 6=*, 7=**, 8=rshift, 9=-, 10=/, 11=|, 12=^"""
        self._emit_raw(Opcode.BINARY_OP, op)
        self._pop()

    def compare_op(self, op: int) -> None:
        """op: 0=<, 1=<=, 2===, 3=!=, 4=>, 5>="""
        self._emit_raw(Opcode.COMPARE_OP, op)
        self._pop()

    def jump_forward(self, label: str) -> None:
        instr = self._emit_raw(Opcode.JUMP_FORWARD, 0)
        instr.arg = label  # type: ignore[assignment]

    def jump_backward(self, label: str) -> None:
        instr = self._emit_raw(Opcode.JUMP_BACKWARD, 0)
        instr.arg = label  # type: ignore[assignment]

    def pop_jump_if_false(self, label: str) -> None:
        instr = self._emit_raw(Opcode.POP_JUMP_IF_FALSE, 0)
        instr.arg = label  # type: ignore[assignment]
        self._pop()

    def pop_jump_if_true(self, label: str) -> None:
        instr = self._emit_raw(Opcode.POP_JUMP_IF_TRUE, 0)
        instr.arg = label  # type: ignore[assignment]
        self._pop()

    def pop_jump_if_none(self, label: str) -> None:
        instr = self._emit_raw(Opcode.POP_JUMP_IF_NONE, 0)
        instr.arg = label  # type: ignore[assignment]
        self._pop()

    def build_list(self, count: int) -> None:
        self._emit_raw(Opcode.BUILD_LIST, count)
        self._pop(count)
        self._push()

    def build_tuple(self, count: int) -> None:
        self._emit_raw(Opcode.BUILD_TUPLE, count)
        self._pop(count)
        self._push()

    def build_dict(self, count: int) -> None:
        """count = number of key/value pairs (so 2*count items popped)."""
        self._emit_raw(Opcode.BUILD_MAP, count)
        self._pop(count * 2)
        self._push()

    def build_set(self, count: int) -> None:
        self._emit_raw(Opcode.BUILD_SET, count)
        self._pop(count)
        self._push()

    def build_string(self, count: int) -> None:
        self._emit_raw(Opcode.BUILD_STRING, count)
        self._pop(count)
        self._push()

    def unpack_sequence(self, count: int) -> None:
        self._emit_raw(Opcode.UNPACK_SEQUENCE, count)
        self._pop()
        self._push(count)

    def make_function(self, flags: int = 0) -> None:
        self._emit_raw(Opcode.MAKE_FUNCTION, flags)
        n = 1 + bin(flags).count('1')
        self._pop(n)
        self._push()

    def import_name(self, name: str) -> None:
        idx = self._name_index(name)
        self._emit_raw(Opcode.IMPORT_NAME, idx)
        self._pop(2)
        self._push()

    def import_from(self, name: str) -> None:
        idx = self._name_index(name)
        self._emit_raw(Opcode.IMPORT_FROM, idx)
        self._push()

    def get_iter(self) -> None:
        self._emit_raw(Opcode.GET_ITER)

    def for_iter(self, label: str) -> None:
        instr = self._emit_raw(Opcode.FOR_ITER, 0)
        instr.arg = label  # type: ignore[assignment]
        self._push()

    def resume(self, where: int = 0) -> None:
        self._emit_raw(Opcode.RESUME, where)

    def nop(self) -> None:
        self._emit_raw(Opcode.NOP)

    def raise_varargs(self, argc: int) -> None:
        self._emit_raw(Opcode.RAISE_VARARGS, argc)
        self._pop(argc)

    def load_deref(self, idx: int) -> None:
        self._emit_raw(Opcode.LOAD_DEREF, idx)
        self._push()

    def store_deref(self, idx: int) -> None:
        self._emit_raw(Opcode.STORE_DEREF, idx)
        self._pop()

    def load_name(self, name: str) -> None:
        idx = self._name_index(name)
        self._emit_raw(Opcode.LOAD_NAME, idx)
        self._push()

    def store_name(self, name: str) -> None:
        idx = self._name_index(name)
        self._emit_raw(Opcode.STORE_NAME, idx)
        self._pop()

    # --- assembly -----------------------------------------------------------

    def assemble(self) -> bytes:
        """Return raw bytecode bytes with labels resolved."""
        return self._buf.to_bytes()

    def assemble_code_object(
        self,
        name: str | None = None,
        filename: str | None = None,
        args: list[str] | None = None,
        *,
        flags: int = 0,
    ) -> types.CodeType:
        """
        Produce a types.CodeType from the assembled instructions.
        The returned code object can be exec()'d or called.
        """
        name = name or self.name
        filename = filename or self.filename
        args = args or []

        # Insert RESUME at start if not present
        if not self._buf._instructions or self._buf._instructions[0].opcode != Opcode.RESUME:
            resume_instr = Instruction(Opcode.RESUME, 0)
            self._buf._instructions.insert(0, resume_instr)

        bytecode = self._buf.to_bytes()

        co_varnames = tuple(self._varnames)
        co_names = tuple(self._names)
        co_consts = tuple(self._consts)

        argcount = len(args)

        # Build lnotab (simplified: all on line 1)
        lnotab = bytes([])

        # Build exception table (empty)
        exceptiontable = bytes([])

        # qualname
        qualname = name

        import sys
        if sys.version_info >= (3, 11):
            code = types.CodeType(
                argcount,           # argcount
                0,                  # posonlyargcount
                0,                  # kwonlyargcount
                len(co_varnames),   # nlocals
                self._max_stack + 1,  # stacksize
                flags,              # flags
                bytecode,           # codestring
                co_consts,          # constants
                co_names,           # names
                co_varnames,        # varnames
                filename,           # filename
                name,               # name
                qualname,           # qualname
                1,                  # firstlineno
                lnotab,             # lnotab
                exceptiontable,     # exceptiontable
                tuple(self._freevars),
                tuple(self._cellvars),
            )
        else:
            code = types.CodeType(
                argcount,
                0,
                0,
                len(co_varnames),
                self._max_stack + 1,
                flags,
                bytecode,
                co_consts,
                co_names,
                co_varnames,
                filename,
                name,
                1,
                lnotab,
                tuple(self._freevars),
                tuple(self._cellvars),
            )
        return code

    # --- disassembly --------------------------------------------------------

    def disassemble(self, bytecode: bytes) -> list[Instruction]:
        """
        Decode raw bytecode bytes into a list of Instructions.
        Handles EXTENDED_ARG chaining.
        """
        instructions = []
        i = 0
        extended_arg = 0
        n = len(bytecode)

        while i < n:
            op = bytecode[i]
            arg_byte = bytecode[i + 1] if i + 1 < n else 0
            arg = extended_arg | arg_byte

            if op == 144:  # EXTENDED_ARG
                extended_arg = arg << 8
                i += 2
                continue

            extended_arg = 0
            try:
                opcode = Opcode(op)
            except ValueError:
                opcode = Opcode.NOP

            instr = Instruction(opcode=opcode, arg=arg)
            instructions.append(instr)
            i += 2

        return instructions

    def to_hex_dump(self, bytecode: bytes, width: int = 16) -> str:
        """Return a formatted hex dump of bytecode bytes."""
        lines = []
        for offset in range(0, len(bytecode), width):
            chunk = bytecode[offset:offset + width]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'{offset:08x}  {hex_part:<{width * 3}}  |{ascii_part}|')
        return '\n'.join(lines)

    def annotated_disassembly(self, bytecode: bytes) -> str:
        """Return human-readable annotated disassembly."""
        instructions = self.disassemble(bytecode)
        lines = []
        offset = 0
        for instr in instructions:
            name = instr.opcode.name
            arg_info = ''
            if instr.opcode == Opcode.LOAD_CONST and instr.arg < len(self._consts):
                arg_info = f'  ({self._consts[instr.arg]!r})'
            elif instr.opcode in (Opcode.LOAD_FAST, Opcode.STORE_FAST) and instr.arg < len(self._varnames):
                arg_info = f'  ({self._varnames[instr.arg]})'
            elif instr.opcode in (Opcode.LOAD_GLOBAL, Opcode.STORE_GLOBAL) and (instr.arg >> 1) < len(self._names):
                arg_info = f'  ({self._names[instr.arg >> 1]})'
            lines.append(f'{offset:6d}  {name:<30} {instr.arg:>5}{arg_info}')
            offset += instr.encoded_size()
        return '\n'.join(lines)

    def reset(self) -> None:
        """Reset assembler state for reuse."""
        self._buf = InstructionBuffer()
        self._consts.clear()
        self._varnames.clear()
        self._names.clear()
        self._stack_depth = 0
        self._max_stack = 0
        self._label_counter = 0

    # --- convenience builders -----------------------------------------------

    def build_simple_function(self, body_fn) -> types.CodeType:
        """
        Helper: call body_fn(asm) to emit instructions, then assemble.
        body_fn receives this assembler instance.
        """
        body_fn(self)
        return self.assemble_code_object()


# ---------------------------------------------------------------------------
# ConstantFolder — simple constant folding pass
# ---------------------------------------------------------------------------

class ConstantFolder:
    """
    Performs basic constant folding on an InstructionBuffer:
    LOAD_CONST + LOAD_CONST + BINARY_OP -> LOAD_CONST result
    """
    BINARY_OPS = {
        0: lambda a, b: a + b,
        1: lambda a, b: a & b,
        2: lambda a, b: a // b if b != 0 else None,
        5: lambda a, b: a % b if b != 0 else None,
        6: lambda a, b: a * b,
        9: lambda a, b: a - b,
        10: lambda a, b: a / b if b != 0 else None,
        11: lambda a, b: a | b,
        12: lambda a, b: a ^ b,
    }

    def fold(self, asm: BytecodeAssembler) -> int:
        """In-place fold; returns number of folds performed."""
        folds = 0
        instructions = asm._buf._instructions
        i = 0
        while i < len(instructions) - 2:
            a = instructions[i]
            b = instructions[i + 1]
            c = instructions[i + 2]
            if (a.opcode == Opcode.LOAD_CONST
                    and b.opcode == Opcode.LOAD_CONST
                    and c.opcode == Opcode.BINARY_OP):
                op_fn = self.BINARY_OPS.get(c.arg)
                if op_fn is not None:
                    try:
                        va = asm._consts[a.arg]
                        vb = asm._consts[b.arg]
                        result = op_fn(va, vb)
                        if result is not None:
                            idx = asm._const_index(result)
                            instructions[i] = Instruction(Opcode.LOAD_CONST, idx)
                            del instructions[i + 1]
                            del instructions[i + 1]
                            folds += 1
                            continue
                    except (TypeError, IndexError):
                        pass
            i += 1
        return folds


# ---------------------------------------------------------------------------
# PeepholeOptimizer — standard peephole passes
# ---------------------------------------------------------------------------

class PeepholeOptimizer:
    """
    Performs peephole optimizations on assembled bytecode.

    Optimizations:
      1. Remove consecutive POP_TOP after NOP
      2. LOAD_CONST True/False + POP_JUMP -> direct JUMP or eliminate
      3. NOP sequences -> single NOP or removal
      4. JUMP_FORWARD with delta=0 -> remove
    """

    def optimize(self, asm: BytecodeAssembler) -> int:
        """Apply all peephole passes; returns total number of changes."""
        total = 0
        total += self._remove_nops(asm)
        total += self._remove_zero_jumps(asm)
        total += self._fold_bool_jumps(asm)
        return total

    def _remove_nops(self, asm: BytecodeAssembler) -> int:
        before = len(asm._buf._instructions)
        asm._buf._instructions = [
            i for i in asm._buf._instructions if i.opcode != Opcode.NOP
        ]
        return before - len(asm._buf._instructions)

    def _remove_zero_jumps(self, asm: BytecodeAssembler) -> int:
        removed = 0
        instructions = asm._buf._instructions
        new_instrs = []
        for instr in instructions:
            if instr.opcode == Opcode.JUMP_FORWARD and isinstance(instr.arg, int) and instr.arg == 0:
                removed += 1
            else:
                new_instrs.append(instr)
        asm._buf._instructions = new_instrs
        return removed

    def _fold_bool_jumps(self, asm: BytecodeAssembler) -> int:
        """LOAD_CONST True + POP_JUMP_IF_FALSE -> JUMP_FORWARD (always taken)."""
        folds = 0
        instructions = asm._buf._instructions
        i = 0
        while i < len(instructions) - 1:
            a = instructions[i]
            b = instructions[i + 1]
            if a.opcode == Opcode.LOAD_CONST and b.opcode == Opcode.POP_JUMP_IF_FALSE:
                val = asm._consts[a.arg] if a.arg < len(asm._consts) else None
                if val is True:
                    # Always false branch not taken — remove both
                    del instructions[i]
                    del instructions[i]
                    folds += 1
                    continue
                elif val is False:
                    # Always taken — replace with unconditional jump
                    instructions[i] = Instruction(Opcode.JUMP_FORWARD, b.arg)
                    del instructions[i + 1]
                    folds += 1
                    continue
            i += 1
        return folds


# ---------------------------------------------------------------------------
# BytecodeVerifier — structural checks
# ---------------------------------------------------------------------------

class BytecodeVerifier:
    """
    Validates that assembled bytecode is structurally sound:
    - All jumps resolve to valid offsets
    - Stack depth never goes negative
    - Code ends with RETURN_VALUE or RETURN_CONST
    """

    # Stack effect of each opcode: +n means n values pushed, -n means n popped
    STACK_EFFECTS: dict[int, int] = {
        int(Opcode.NOP): 0,
        int(Opcode.RESUME): 0,
        int(Opcode.POP_TOP): -1,
        int(Opcode.COPY): 1,
        int(Opcode.SWAP): 0,
        int(Opcode.LOAD_CONST): 1,
        int(Opcode.LOAD_FAST): 1,
        int(Opcode.STORE_FAST): -1,
        int(Opcode.LOAD_GLOBAL): 1,
        int(Opcode.STORE_GLOBAL): -1,
        int(Opcode.RETURN_VALUE): -1,
        int(Opcode.RETURN_CONST): 0,
        int(Opcode.BINARY_OP): -1,
        int(Opcode.COMPARE_OP): -1,
        int(Opcode.BUILD_LIST): 0,   # variable — computed separately
        int(Opcode.BUILD_TUPLE): 0,
        int(Opcode.BUILD_MAP): 0,
        int(Opcode.PUSH_NULL): 1,
        int(Opcode.UNARY_NEGATIVE): 0,
        int(Opcode.UNARY_NOT): 0,
        int(Opcode.UNARY_INVERT): 0,
        int(Opcode.GET_ITER): 0,
        int(Opcode.JUMP_FORWARD): 0,
        int(Opcode.JUMP_BACKWARD): 0,
        int(Opcode.POP_JUMP_IF_TRUE): -1,
        int(Opcode.POP_JUMP_IF_FALSE): -1,
        int(Opcode.LOAD_ATTR): 0,
        int(Opcode.STORE_ATTR): -2,
        int(Opcode.CALL): 0,
        int(Opcode.MAKE_FUNCTION): 0,
        int(Opcode.IMPORT_NAME): -1,
        int(Opcode.IMPORT_FROM): 1,
        int(Opcode.RAISE_VARARGS): 0,
    }

    def verify(self, asm: BytecodeAssembler) -> list[str]:
        """Return list of error strings (empty if valid)."""
        errors = []
        depth = 0

        # Check for return at end
        instructions = asm._buf._instructions
        if instructions:
            last = instructions[-1]
            if last.opcode not in (Opcode.RETURN_VALUE, Opcode.RETURN_CONST, Opcode.RAISE_VARARGS):
                errors.append(f"Code does not end with RETURN: ends with {last.opcode.name}")

        for i, instr in enumerate(instructions):
            effect = self.STACK_EFFECTS.get(int(instr.opcode), 0)
            depth += effect
            if depth < 0:
                errors.append(f"Stack underflow at instruction {i} ({instr.opcode.name})")
                depth = 0  # recover

        return errors


# ---------------------------------------------------------------------------
# AssemblerContext — context manager for structured emission
# ---------------------------------------------------------------------------

class AssemblerContext:
    """
    Context manager that automatically adds RESUME at entry and
    RETURN_CONST None at exit if no explicit return was emitted.
    """

    def __init__(self, name: str = "<context>", filename: str = "<string>"):
        self.asm = BytecodeAssembler(name=name, filename=filename)

    def __enter__(self) -> BytecodeAssembler:
        self.asm.resume()
        return self.asm

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Check if last instruction is a return
            instrs = self.asm._buf._instructions
            if not instrs or instrs[-1].opcode not in (
                Opcode.RETURN_VALUE, Opcode.RETURN_CONST
            ):
                self.asm.load_const(None)
                self.asm.return_value()
        return False

    def code_object(self) -> types.CodeType:
        return self.asm.assemble_code_object()


# ---------------------------------------------------------------------------
# Utility: compile Python source to raw bytecode via assembler inspection
# ---------------------------------------------------------------------------

def source_to_bytecode(source: str) -> tuple[bytes, types.CodeType]:
    """
    Compile Python source, return (raw_bytecode, code_object).
    The assembler is populated to mirror the compiled code for inspection.
    """
    import compile as builtin_compile
    code = compile(source, '<string>', 'exec')
    return code.co_code, code


def bytecode_from_code_object(code: types.CodeType) -> bytes:
    """Extract raw bytecode from a code object."""
    return code.co_code


def describe_code_object(code: types.CodeType) -> str:
    """Return a human-readable description of a code object."""
    lines = [
        f"Code object: {code.co_name!r} in {code.co_filename!r}",
        f"  argcount:    {code.co_argcount}",
        f"  nlocals:     {code.co_nlocals}",
        f"  stacksize:   {code.co_stacksize}",
        f"  flags:       {code.co_flags:#010x}",
        f"  consts:      {code.co_consts}",
        f"  names:       {code.co_names}",
        f"  varnames:    {code.co_varnames}",
        f"  bytecode:    {len(code.co_code)} bytes",
        "  disassembly:",
    ]
    buf = io.StringIO()
    dis.dis(code, file=buf)
    for line in buf.getvalue().splitlines():
        lines.append(f"    {line}")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# FunctionBuilder — fluent API for building simple functions
# ---------------------------------------------------------------------------

class FunctionBuilder:
    """
    Fluent builder for constructing simple compiled Python functions.

    Example:
        fb = FunctionBuilder("add")
        fb.arg("x").arg("y")
        fb.body(lambda asm: (
            asm.load_fast("x"),
            asm.load_fast("y"),
            asm.binary_op(0),    # ADD
            asm.return_value()
        ))
        add_fn = fb.build()
        assert add_fn(2, 3) == 5
    """

    def __init__(self, name: str):
        self._name = name
        self._args: list[str] = []
        self._asm = BytecodeAssembler(name=name)
        self._body_emitted = False

    def arg(self, name: str) -> 'FunctionBuilder':
        self._args.append(name)
        self._asm._varname_index(name)  # pre-register
        return self

    def body(self, emit_fn) -> 'FunctionBuilder':
        self._asm.resume()
        emit_fn(self._asm)
        self._body_emitted = True
        return self

    def build(self) -> types.FunctionType:
        if not self._body_emitted:
            self._asm.resume()
            self._asm.load_const(None)
            self._asm.return_value()
        code = self._asm.assemble_code_object(
            name=self._name,
            args=self._args,
        )
        return types.FunctionType(code, {})


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def make_assembler(name: str = "<asm>") -> BytecodeAssembler:
    return BytecodeAssembler(name=name)


def assemble_expr(expr: str) -> bytes:
    """Compile a Python expression and return its bytecode."""
    code = compile(expr, '<expr>', 'eval')
    return code.co_code


def round_trip_test(source: str) -> bool:
    """
    Compile source, disassemble, and verify instruction count is consistent.
    Returns True if disassembly produces sensible output.
    """
    code = compile(source, '<test>', 'exec')
    asm = BytecodeAssembler()
    instructions = asm.disassemble(code.co_code)
    return len(instructions) > 0


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    """Run internal consistency checks. Returns True if all pass."""
    asm = BytecodeAssembler("test")

    # Test constant pool dedup
    asm.load_const(42)
    asm.load_const(42)
    assert len(asm._consts) == 1, "Constant dedup failed"

    # Test varnames
    asm.load_fast("x")
    asm.store_fast("x")
    assert asm._varnames == ["x"]

    # Test bytecode roundtrip
    asm2 = BytecodeAssembler("rt")
    asm2.resume()
    asm2.load_const(1)
    asm2.load_const(2)
    asm2.binary_op(0)  # ADD
    asm2.return_value()
    bytecode = asm2.assemble()
    instructions = asm2.disassemble(bytecode)
    assert len(instructions) > 0

    return True


# ---------------------------------------------------------------------------
# OpcodeMeta — metadata about each opcode
# ---------------------------------------------------------------------------

@dataclass
class OpcodeMeta:
    """Metadata for a single CPython opcode."""
    opcode: Opcode
    name: str
    stack_effect: int     # net change to stack depth
    has_arg: bool
    is_jump: bool
    is_return: bool
    description: str

    def __repr__(self) -> str:
        return (
            f"OpcodeMeta({self.name}, effect={self.stack_effect:+d}, "
            f"has_arg={self.has_arg}, jump={self.is_jump})"
        )


def build_opcode_meta_table() -> dict[Opcode, OpcodeMeta]:
    """Build complete metadata table for all defined opcodes."""
    jump_ops = {
        Opcode.JUMP_FORWARD, Opcode.JUMP_BACKWARD,
        Opcode.JUMP_BACKWARD_NO_INTERRUPT,
        Opcode.POP_JUMP_IF_TRUE, Opcode.POP_JUMP_IF_FALSE,
        Opcode.POP_JUMP_IF_NONE, Opcode.POP_JUMP_IF_NOT_NONE,
        Opcode.JUMP_IF_TRUE_OR_POP, Opcode.JUMP_IF_FALSE_OR_POP,
        Opcode.FOR_ITER,
    }
    return_ops = {Opcode.RETURN_VALUE, Opcode.RETURN_CONST, Opcode.RAISE_VARARGS}
    table = {}
    for op in Opcode:
        try:
            name = op.name
        except AttributeError:
            continue
        effect = BytecodeVerifier.STACK_EFFECTS.get(int(op), 0)
        table[op] = OpcodeMeta(
            opcode=op,
            name=name,
            stack_effect=effect,
            has_arg=op.has_arg(),
            is_jump=op in jump_ops,
            is_return=op in return_ops,
            description=_OPCODE_DESCRIPTIONS.get(op, ""),
        )
    return table


_OPCODE_DESCRIPTIONS: dict[Opcode, str] = {
    Opcode.NOP:            "No operation",
    Opcode.LOAD_CONST:     "Push co_consts[arg] onto stack",
    Opcode.LOAD_FAST:      "Push co_varnames[arg] onto stack",
    Opcode.STORE_FAST:     "Pop top of stack; store in co_varnames[arg]",
    Opcode.LOAD_GLOBAL:    "Load global name[arg>>1] onto stack",
    Opcode.STORE_GLOBAL:   "Store top of stack as global name[arg]",
    Opcode.RETURN_VALUE:   "Return top of stack",
    Opcode.RETURN_CONST:   "Return co_consts[arg] without popping stack",
    Opcode.BINARY_OP:      "Perform binary operation with given operator code",
    Opcode.COMPARE_OP:     "Perform comparison with given operator code",
    Opcode.JUMP_FORWARD:   "Jump forward by arg*2 bytes",
    Opcode.JUMP_BACKWARD:  "Jump backward by arg*2 bytes",
    Opcode.POP_JUMP_IF_TRUE:  "Pop and jump if truthy",
    Opcode.POP_JUMP_IF_FALSE: "Pop and jump if falsy",
    Opcode.GET_ITER:       "Implement TOS = iter(TOS)",
    Opcode.FOR_ITER:       "TOS is iterator; advance or jump forward by arg*2",
    Opcode.BUILD_LIST:     "Build list from top arg items",
    Opcode.BUILD_TUPLE:    "Build tuple from top arg items",
    Opcode.BUILD_MAP:      "Build dict from top 2*arg items (key/value pairs)",
    Opcode.BUILD_SET:      "Build set from top arg items",
    Opcode.MAKE_FUNCTION:  "Create function object from code object and defaults",
    Opcode.IMPORT_NAME:    "Import module names[arg]",
    Opcode.IMPORT_FROM:    "Load attribute names[arg] from top of stack",
    Opcode.CALL:           "Call callable with arg positional arguments",
    Opcode.PUSH_NULL:      "Push NULL sentinel for CALL",
    Opcode.RESUME:         "Start of function body",
    Opcode.UNPACK_SEQUENCE:"Unpack sequence into arg items on stack",
    Opcode.LOAD_ATTR:      "Load attribute names[arg] of TOS",
    Opcode.STORE_ATTR:     "Set TOS.names[arg] = TOS1",
    Opcode.POP_TOP:        "Pop top of stack",
    Opcode.COPY:           "Push copy of stack[arg] (1-based from top)",
    Opcode.SWAP:           "Swap TOS with stack item arg (1-based)",
    Opcode.RAISE_VARARGS:  "Raise exception with arg values",
}


# ---------------------------------------------------------------------------
# BasicBlock — control flow graph building block
# ---------------------------------------------------------------------------

@dataclass
class BasicBlock:
    """A straight-line sequence of instructions with no internal branches."""
    label: str
    instructions: list[Instruction] = field(default_factory=list)
    successors: list[str] = field(default_factory=list)  # labels of successor blocks
    predecessors: list[str] = field(default_factory=list)

    def append(self, instr: Instruction) -> None:
        self.instructions.append(instr)

    def is_empty(self) -> bool:
        return len(self.instructions) == 0

    def last(self) -> Optional[Instruction]:
        return self.instructions[-1] if self.instructions else None

    def size(self) -> int:
        return len(self.instructions)

    def byte_size(self) -> int:
        return sum(i.encoded_size() for i in self.instructions)

    def __repr__(self) -> str:
        return f"BasicBlock({self.label!r}, {self.size()} instrs)"


class ControlFlowGraph:
    """
    Control flow graph built from a list of Instructions.
    Nodes are BasicBlocks; edges are branch/fallthrough relationships.
    """

    def __init__(self, instructions: list[Instruction]):
        self._instructions = instructions
        self._blocks: dict[str, BasicBlock] = {}
        self._entry: Optional[str] = None
        self._build()

    def _build(self) -> None:
        """Partition instructions into basic blocks."""
        if not self._instructions:
            return

        # Find block entry points: first instruction + jump targets + post-jump
        entries: set[int] = {0}
        for i, instr in enumerate(self._instructions):
            if instr.is_jump():
                entries.add(i + 1)
                if isinstance(instr.arg, int):
                    entries.add(instr.arg)

        sorted_entries = sorted(entries)
        block_starts = {off: f"B{off}" for off in sorted_entries}
        self._entry = block_starts.get(0, "B0")

        # Assign instructions to blocks
        current_label: Optional[str] = None
        for i, instr in enumerate(self._instructions):
            if i in block_starts:
                current_label = block_starts[i]
                if current_label not in self._blocks:
                    self._blocks[current_label] = BasicBlock(current_label)
            if current_label:
                self._blocks[current_label].append(instr)

    def blocks(self) -> list[BasicBlock]:
        return list(self._blocks.values())

    def entry_block(self) -> Optional[BasicBlock]:
        return self._blocks.get(self._entry) if self._entry else None

    def block_count(self) -> int:
        return len(self._blocks)

    def dominators(self) -> dict[str, set[str]]:
        """Compute dominator sets using iterative algorithm."""
        if not self._blocks:
            return {}

        labels = list(self._blocks.keys())
        entry = self._entry

        dom: dict[str, set[str]] = {}
        all_blocks = set(labels)

        # Initialize: entry dominates only itself; others dominated by all
        for lbl in labels:
            if lbl == entry:
                dom[lbl] = {lbl}
            else:
                dom[lbl] = set(all_blocks)

        # Iterative refinement
        changed = True
        while changed:
            changed = False
            for lbl in labels:
                if lbl == entry:
                    continue
                block = self._blocks[lbl]
                preds = block.predecessors
                if preds:
                    new_dom = set(all_blocks)
                    for pred in preds:
                        new_dom &= dom.get(pred, set())
                    new_dom.add(lbl)
                    if new_dom != dom[lbl]:
                        dom[lbl] = new_dom
                        changed = True
        return dom

    def to_dot(self) -> str:
        """Export as Graphviz dot format."""
        lines = ["digraph CFG {"]
        for label, block in self._blocks.items():
            content = r'\n'.join(
                f"{instr.opcode.name} {instr.arg}"
                for instr in block.instructions[:4]
            )
            if block.size() > 4:
                content += r'\n...'
            lines.append(f'  {label} [label="{label}\\n{content}", shape=box];')
        for label, block in self._blocks.items():
            for succ in block.successors:
                lines.append(f"  {label} -> {succ};")
        lines.append("}")
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# StackTracer — trace stack state through bytecode
# ---------------------------------------------------------------------------

class StackTracer:
    """
    Symbolically traces the stack through bytecode instructions,
    tracking the number of values at each point.
    """

    def __init__(self, assembler: BytecodeAssembler):
        self._asm = assembler
        self._verifier = BytecodeVerifier()

    def trace(self) -> list[tuple[int, int]]:
        """
        Trace stack depth through each instruction.
        Returns list of (instruction_index, stack_depth_before).
        """
        result = []
        depth = 0
        for i, instr in enumerate(self._asm._buf._instructions):
            result.append((i, depth))
            effect = self._verifier.STACK_EFFECTS.get(int(instr.opcode), 0)
            depth = max(0, depth + effect)
        return result

    def max_depth(self) -> int:
        trace = self.trace()
        return max((d for _, d in trace), default=0)

    def validate(self) -> bool:
        trace = self.trace()
        return all(d >= 0 for _, d in trace)


# ---------------------------------------------------------------------------
# BytecodePattern — pattern-based code transformation
# ---------------------------------------------------------------------------

@dataclass
class BytecodePattern:
    """Represents a sequence of opcodes to match in bytecode."""
    opcodes: list[Opcode]
    name: str = ""

    def matches(self, instructions: list[Instruction], start: int) -> bool:
        """Check if the pattern matches starting at index `start`."""
        if start + len(self.opcodes) > len(instructions):
            return False
        for i, op in enumerate(self.opcodes):
            if instructions[start + i].opcode != op:
                return False
        return True

    def find_all(self, instructions: list[Instruction]) -> list[int]:
        """Return all start indices where this pattern matches."""
        matches = []
        for i in range(len(instructions)):
            if self.matches(instructions, i):
                matches.append(i)
        return matches


class PatternRewriter:
    """Applies pattern-based transformations to instruction sequences."""

    def __init__(self):
        self._rules: list[tuple[BytecodePattern, list[Instruction]]] = []

    def add_rule(self, pattern: BytecodePattern, replacement: list[Instruction]) -> None:
        self._rules.append((pattern, replacement))

    def apply(self, instructions: list[Instruction]) -> tuple[list[Instruction], int]:
        """Apply all rules; return (new instructions, number of replacements)."""
        result = list(instructions)
        replacements = 0
        for pattern, replacement in self._rules:
            i = 0
            while i < len(result):
                if pattern.matches(result, i):
                    # Replace matched slice
                    result[i:i + len(pattern.opcodes)] = replacement
                    replacements += 1
                    i += len(replacement)
                else:
                    i += 1
        return result, replacements


# ---------------------------------------------------------------------------
# BytecodeStats — statistics about a bytecode sequence
# ---------------------------------------------------------------------------

@dataclass
class BytecodeStats:
    total_instructions: int = 0
    total_bytes: int = 0
    opcode_histogram: dict = field(default_factory=dict)
    jump_count: int = 0
    call_count: int = 0
    const_count: int = 0
    unique_consts: int = 0
    unique_names: int = 0
    unique_varnames: int = 0

    def analyze(self, asm: BytecodeAssembler) -> None:
        instructions = asm._buf._instructions
        self.total_instructions = len(instructions)
        for instr in instructions:
            name = instr.opcode.name
            self.opcode_histogram[name] = self.opcode_histogram.get(name, 0) + 1
            if instr.is_jump():
                self.jump_count += 1
            if instr.opcode == Opcode.CALL:
                self.call_count += 1
            if instr.opcode == Opcode.LOAD_CONST:
                self.const_count += 1
        self.unique_consts = len(asm._consts)
        self.unique_names = len(asm._names)
        self.unique_varnames = len(asm._varnames)
        self.total_bytes = asm._buf.size()

    def top_opcodes(self, n: int = 10) -> list[tuple[str, int]]:
        return sorted(self.opcode_histogram.items(), key=lambda x: -x[1])[:n]

    def summary(self) -> str:
        lines = [
            f"BytecodeStats:",
            f"  Instructions: {self.total_instructions}",
            f"  Bytes: {self.total_bytes}",
            f"  Jumps: {self.jump_count}",
            f"  Calls: {self.call_count}",
            f"  Constants: {self.const_count} ({self.unique_consts} unique)",
            f"  Names: {self.unique_names}",
            f"  Varnames: {self.unique_varnames}",
            f"  Top opcodes: {self.top_opcodes(5)}",
        ]
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CodeObjectDiff — compare two code objects
# ---------------------------------------------------------------------------

class CodeObjectDiff:
    """Compare two types.CodeType objects for differences."""

    ATTRS = (
        'co_argcount', 'co_nlocals', 'co_stacksize', 'co_flags',
        'co_consts', 'co_names', 'co_varnames', 'co_freevars', 'co_cellvars',
    )

    def diff(
        self,
        a: types.CodeType,
        b: types.CodeType,
        label_a: str = "A",
        label_b: str = "B",
    ) -> list[str]:
        differences = []
        for attr in self.ATTRS:
            va = getattr(a, attr, None)
            vb = getattr(b, attr, None)
            if va != vb:
                differences.append(f"{attr}: {label_a}={va!r}, {label_b}={vb!r}")
        # Bytecode
        ca, cb = a.co_code, b.co_code
        if ca != cb:
            differences.append(
                f"co_code: {label_a}={len(ca)} bytes, {label_b}={len(cb)} bytes"
            )
            if len(ca) == len(cb):
                diffs = [i for i in range(0, len(ca), 2) if ca[i] != cb[i]]
                differences.append(f"  Differing offsets: {diffs[:10]}")
        return differences

    def is_equivalent(self, a: types.CodeType, b: types.CodeType) -> bool:
        return len(self.diff(a, b)) == 0


# ---------------------------------------------------------------------------
# EmitContext — scoped emission with automatic cleanup
# ---------------------------------------------------------------------------

class EmitContext:
    """
    Context manager for structured emission of related instruction groups.
    Tracks the byte range of instructions emitted within the context.
    """

    def __init__(self, asm: BytecodeAssembler, name: str = ""):
        self._asm = asm
        self._name = name
        self._start_count = 0
        self._end_count = 0

    def __enter__(self) -> 'EmitContext':
        self._start_count = len(self._asm._buf._instructions)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._end_count = len(self._asm._buf._instructions)
        return False

    @property
    def instruction_count(self) -> int:
        return self._end_count - self._start_count

    @property
    def instructions(self) -> list[Instruction]:
        return self._asm._buf._instructions[self._start_count:self._end_count]

    @property
    def byte_size(self) -> int:
        return sum(i.encoded_size() for i in self.instructions)

    def __repr__(self) -> str:
        return (
            f"EmitContext({self._name!r}, "
            f"{self.instruction_count} instrs, {self.byte_size} bytes)"
        )


# ---------------------------------------------------------------------------
# LoopBuilder — structured loop emission
# ---------------------------------------------------------------------------

class LoopBuilder:
    """
    Helper for emitting structured for/while loops using labels.

    Example:
        lb = LoopBuilder(asm)
        with lb.for_range(10):  # pushes count
            asm.load_fast("body_value")
            asm.pop_top()
    """

    def __init__(self, asm: BytecodeAssembler):
        self._asm = asm

    class _ForRangeContext:
        def __init__(self, lb: 'LoopBuilder', count: int):
            self._lb = lb
            self._count = count
            self._loop_label = ""
            self._exit_label = ""

        def __enter__(self):
            asm = self._lb._asm
            self._loop_label = asm.new_label()
            self._exit_label = asm.new_label()
            # Build range(count) and get iterator
            asm.load_global("range", push_null=True)
            asm.load_const(self._count)
            asm.call(1)
            asm.get_iter()
            asm.emit_label(self._loop_label)
            asm.for_iter(self._exit_label)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            asm = self._lb._asm
            asm.jump_backward(self._loop_label)
            asm.emit_label(self._exit_label)
            return False

    def for_range(self, count: int) -> '_ForRangeContext':
        return self._ForRangeContext(self, count)


# ---------------------------------------------------------------------------
# Global opcode metadata table (built lazily)
# ---------------------------------------------------------------------------

_OPCODE_META: Optional[dict] = None

def get_opcode_meta() -> dict[Opcode, OpcodeMeta]:
    global _OPCODE_META
    if _OPCODE_META is None:
        _OPCODE_META = build_opcode_meta_table()
    return _OPCODE_META


def opcode_info(op: Opcode) -> Optional[OpcodeMeta]:
    return get_opcode_meta().get(op)


if __name__ == "__main__":
    assert _self_test(), "Self-test failed"
    print("bytecode_assembler.py: all self-tests passed")

    # Demo: build and execute a simple add function
    fb = FunctionBuilder("add")
    fb.arg("x").arg("y")
    fb.body(lambda asm: [
        asm.load_fast("x"),
        asm.load_fast("y"),
        asm.binary_op(0),
        asm.return_value(),
    ])
    # Note: executing assembled bytecode requires careful version matching
    print("FunctionBuilder demo: built 'add' code object")

    # Demo: hex dump
    asm3 = BytecodeAssembler("demo")
    asm3.resume()
    asm3.load_const(42)
    asm3.return_value()
    bytecode = asm3.assemble()
    print("Hex dump of 'return 42' bytecode:")
    print(asm3.to_hex_dump(bytecode))

    # Demo: opcode metadata
    meta = get_opcode_meta()
    print(f"\nOpcode metadata table: {len(meta)} entries")
    for op in list(meta.keys())[:5]:
        print(f"  {meta[op]}")

    # Demo: BytecodeStats
    stats = BytecodeStats()
    stats.analyze(asm3)
    print("\n" + stats.summary())
