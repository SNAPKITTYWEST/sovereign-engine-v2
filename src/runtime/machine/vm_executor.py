"""
vm_executor.py — Minimal stack-based virtual machine for Sovereign IR.

Executes sovereign IR instructions (VMInstruction objects) on a stack machine.
Enforces the DSL entropy constraint (H <= 0.20) at runtime.
Includes NAND-complete Boolean kernel, routing dispatch, and WORM commit hooks.

Part of the SOVEREIGN_IR PYTHON_C_BRIDGE_IR pipeline.
Agent A (Cognition) — HyperKittyConstraintDSL v1.0
"""

from __future__ import annotations

import hashlib
import io
import math
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Opcode definitions
# ---------------------------------------------------------------------------

class VMOpcode(IntEnum):
    # Stack primitives
    NOP       = 0x00
    PUSH      = 0x01
    POP       = 0x02
    DUP       = 0x03
    SWAP      = 0x04
    COPY      = 0x05  # duplicate nth from top
    ROT       = 0x06  # rotate top 3

    # Arithmetic
    ADD       = 0x10
    SUB       = 0x11
    MUL       = 0x12
    DIV       = 0x13
    MOD       = 0x14
    NEG       = 0x15
    ABS       = 0x16

    # Boolean (NAND-complete kernel)
    AND       = 0x20  # NAND(NAND(a,b), NAND(a,b))
    OR        = 0x21  # NAND(NAND(a,a), NAND(b,b))
    NOT       = 0x22  # NAND(x, x)
    NAND      = 0x23  # primitive
    XOR       = 0x24  # NAND(NAND(a,NAND(a,b)), NAND(b,NAND(a,b)))
    XNOR      = 0x25
    NOR       = 0x26

    # Comparison
    EQ        = 0x30
    NEQ       = 0x31
    LT        = 0x32
    GT        = 0x33
    LE        = 0x34
    GE        = 0x35

    # Bitwise
    BAND      = 0x38
    BOR       = 0x39
    BXOR      = 0x3A
    BNOT      = 0x3B
    SHL       = 0x3C
    SHR       = 0x3D

    # Control flow
    JMP       = 0x40
    JZ        = 0x41  # jump if top == 0 / False
    JNZ       = 0x42  # jump if top != 0 / True
    CALL      = 0x43
    RET       = 0x44
    LOOP      = 0x45  # loop: decrement top, jump if > 0

    # Routing & dispatch
    ROUTE     = 0x50  # route to expert by opcode arg
    DISPATCH  = 0x51  # dispatch tool by opcode arg
    GATE      = 0x52  # Jordan gate evaluation
    FILTER    = 0x53  # entropy filter gate
    FORWARD   = 0x54  # forward to next stage

    # Memory
    LOAD      = 0x60  # load from memory address
    STORE     = 0x61  # store to memory address
    ALLOC     = 0x62  # allocate n bytes
    FREE      = 0x63

    # State / WORM
    COMMIT    = 0x70  # commit state to WORM
    CHECKPOINT= 0x71  # save continuity checkpoint
    ROLLBACK  = 0x72  # restore from checkpoint
    SEAL      = 0x73  # seal current frame (WORM-protect)
    VERIFY    = 0x74  # verify sealed frame

    # I/O
    PRINT     = 0x80  # print top of stack
    READ      = 0x81  # read value (stub)
    EMIT      = 0x82  # emit to output buffer

    # Entropy management
    MEASURE   = 0x90  # push current entropy value
    CLAMP     = 0x91  # clamp top to [0.0, 0.20]
    ENTROPY   = 0x92  # compute entropy of stack distribution

    # Halt
    HALT      = 0xFF


# ---------------------------------------------------------------------------
# VMInstruction
# ---------------------------------------------------------------------------

@dataclass
class VMInstruction:
    opcode: VMOpcode
    arg: int = 0
    symbol: str = ''
    lineno: int = 0

    def __post_init__(self):
        if isinstance(self.opcode, int):
            self.opcode = VMOpcode(self.opcode)

    def __repr__(self) -> str:
        parts = [self.opcode.name]
        if self.arg != 0:
            parts.append(str(self.arg))
        if self.symbol:
            parts.append(repr(self.symbol))
        return f"VMInstruction({', '.join(parts)})"


# ---------------------------------------------------------------------------
# VMStack
# ---------------------------------------------------------------------------

class VMStackUnderflow(Exception):
    pass

class VMStackOverflow(Exception):
    pass


class VMStack:
    """LIFO stack with optional maximum depth limit."""

    DEFAULT_MAX = 4096

    def __init__(self, max_depth: int = DEFAULT_MAX):
        self._data: list[Any] = []
        self._max_depth = max_depth

    def push(self, value: Any) -> None:
        if len(self._data) >= self._max_depth:
            raise VMStackOverflow(
                f"Stack overflow at depth {self._max_depth}"
            )
        self._data.append(value)

    def pop(self) -> Any:
        if not self._data:
            raise VMStackUnderflow("Stack underflow: pop on empty stack")
        return self._data.pop()

    def peek(self, offset: int = 0) -> Any:
        """Peek at the top (offset=0) or nth item from top (offset=n)."""
        idx = -(offset + 1)
        if abs(idx) > len(self._data):
            raise VMStackUnderflow(f"Stack peek offset {offset} out of range")
        return self._data[idx]

    def peek_n(self, n: int) -> list[Any]:
        """Return top n items (bottom-first order)."""
        if n > len(self._data):
            raise VMStackUnderflow(f"Stack peek_n {n} > depth {len(self._data)}")
        return list(self._data[-n:])

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def size(self) -> int:
        return len(self._data)

    def clear(self) -> None:
        self._data.clear()

    def as_list(self) -> list[Any]:
        return list(self._data)

    def to_display(self) -> str:
        if not self._data:
            return "[empty]"
        items = [repr(x) for x in reversed(self._data)]
        return "[" + ", ".join(items[:8]) + (", ..." if len(items) > 8 else "") + "]"


# ---------------------------------------------------------------------------
# VMRegisters
# ---------------------------------------------------------------------------

@dataclass
class VMRegisters:
    pc: int = 0         # program counter (instruction index)
    sp: int = 0         # shadow stack pointer (informational)
    flags: int = 0      # status flags: bit 0=zero, bit 1=carry, bit 2=overflow, bit 3=negative
    entropy: float = 0.0  # current running entropy estimate

    FLAG_ZERO     = 1 << 0
    FLAG_CARRY    = 1 << 1
    FLAG_OVERFLOW = 1 << 2
    FLAG_NEGATIVE = 1 << 3
    FLAG_HALT     = 1 << 7

    def set_zero(self, value: Any) -> None:
        if value == 0 or value is False:
            self.flags |= self.FLAG_ZERO
        else:
            self.flags &= ~self.FLAG_ZERO

    def set_negative(self, value: Any) -> None:
        try:
            if float(value) < 0:
                self.flags |= self.FLAG_NEGATIVE
            else:
                self.flags &= ~self.FLAG_NEGATIVE
        except (TypeError, ValueError):
            pass

    def is_zero(self) -> bool:
        return bool(self.flags & self.FLAG_ZERO)

    def is_halted(self) -> bool:
        return bool(self.flags & self.FLAG_HALT)

    def halt(self) -> None:
        self.flags |= self.FLAG_HALT

    def update(self, value: Any) -> None:
        self.set_zero(value)
        self.set_negative(value)


# ---------------------------------------------------------------------------
# VMMemory
# ---------------------------------------------------------------------------

class VMMemory:
    """
    Simple 64KB address space memory for the VM.
    Byte-addressable, no protection.
    """

    SIZE = 65536  # 64KB

    def __init__(self, size: int = SIZE):
        self._data = bytearray(size)
        self._size = size

    def read(self, addr: int) -> int:
        self._check(addr, 1)
        return self._data[addr]

    def write(self, addr: int, value: int) -> None:
        self._check(addr, 1)
        self._data[addr] = value & 0xFF

    def read_bytes(self, addr: int, n: int) -> bytes:
        self._check(addr, n)
        return bytes(self._data[addr:addr + n])

    def write_bytes(self, addr: int, data: bytes) -> None:
        self._check(addr, len(data))
        self._data[addr:addr + len(data)] = data

    def read_u32(self, addr: int) -> int:
        return struct.unpack_from('<I', self._data, addr)[0]

    def write_u32(self, addr: int, value: int) -> None:
        struct.pack_into('<I', self._data, addr, value & 0xFFFFFFFF)

    def read_u64(self, addr: int) -> int:
        return struct.unpack_from('<Q', self._data, addr)[0]

    def write_u64(self, addr: int, value: int) -> None:
        struct.pack_into('<Q', self._data, addr, value & 0xFFFFFFFFFFFFFFFF)

    def fill(self, addr: int, byte: int, n: int) -> None:
        self._check(addr, n)
        for i in range(n):
            self._data[addr + i] = byte & 0xFF

    def _check(self, addr: int, size: int) -> None:
        if addr < 0 or addr + size > self._size:
            raise VMError(f"Memory access out of bounds: addr={addr:#x}, size={size}")

    def size(self) -> int:
        return self._size

    def dump(self, addr: int = 0, length: int = 64) -> str:
        """Hex dump."""
        lines = []
        for off in range(0, length, 16):
            chunk = self._data[addr + off:addr + off + 16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'{addr + off:04x}  {hex_part:<48}  |{ascii_part}|')
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# VMError
# ---------------------------------------------------------------------------

class VMError(Exception):
    pass

class VMEntropyViolation(VMError):
    pass

class VMHaltException(Exception):
    pass


# ---------------------------------------------------------------------------
# WORMLog — immutable append-only log for COMMIT / CHECKPOINT
# ---------------------------------------------------------------------------

@dataclass
class WORMEntry:
    seq: int
    timestamp_ns: int
    opcode: VMOpcode
    data: bytes
    checksum: bytes

    def verify(self) -> bool:
        expected = hashlib.blake2b(self.data, digest_size=32).digest()
        return expected == self.checksum


class WORMLog:
    """Append-only log for VM state commits."""

    def __init__(self):
        self._entries: list[WORMEntry] = []
        self._seq = 0

    def append(self, opcode: VMOpcode, data: bytes) -> WORMEntry:
        checksum = hashlib.blake2b(data, digest_size=32).digest()
        entry = WORMEntry(
            seq=self._seq,
            timestamp_ns=time.time_ns(),
            opcode=opcode,
            data=data,
            checksum=checksum,
        )
        self._entries.append(entry)
        self._seq += 1
        return entry

    def last(self) -> Optional[WORMEntry]:
        return self._entries[-1] if self._entries else None

    def count(self) -> int:
        return len(self._entries)

    def all_valid(self) -> bool:
        return all(e.verify() for e in self._entries)

    def export(self) -> list[dict]:
        return [
            {
                'seq': e.seq,
                'timestamp_ns': e.timestamp_ns,
                'opcode': e.opcode.name,
                'data_len': len(e.data),
                'checksum': e.checksum.hex(),
                'valid': e.verify(),
            }
            for e in self._entries
        ]


# ---------------------------------------------------------------------------
# NAND-complete Boolean kernel (pure Python, no bit tricks)
# ---------------------------------------------------------------------------

def nand_op(a: Any, b: Any) -> int:
    """NAND gate — the universal primitive."""
    ai = 1 if a else 0
    bi = 1 if b else 0
    return 1 - ai * bi  # NAND(a,b) = NOT(a AND b) = 1 - a*b (when {0,1})


def nand_not(x: Any) -> int:
    return nand_op(x, x)


def nand_and(a: Any, b: Any) -> int:
    n = nand_op(a, b)
    return nand_op(n, n)  # NOT(NAND(a,b))


def nand_or(a: Any, b: Any) -> int:
    na = nand_op(a, a)   # NOT a
    nb = nand_op(b, b)   # NOT b
    return nand_op(na, nb)  # NAND(NOT a, NOT b) = a OR b


def nand_xor(a: Any, b: Any) -> int:
    ab = nand_op(a, b)
    a_ab = nand_op(a, ab)
    b_ab = nand_op(b, ab)
    return nand_op(a_ab, b_ab)


def nand_xnor(a: Any, b: Any) -> int:
    return nand_not(nand_xor(a, b))


def nand_nor(a: Any, b: Any) -> int:
    return nand_not(nand_or(a, b))


# ---------------------------------------------------------------------------
# Routing dispatch table
# ---------------------------------------------------------------------------

class DispatchTable:
    """
    Maps opcodes to Python callables for ROUTE / DISPATCH instructions.
    """

    def __init__(self):
        self._table: dict[int, Callable] = {}

    def register(self, opcode: int, handler: Callable) -> None:
        self._table[opcode] = handler

    def dispatch(self, opcode: int, *args) -> Any:
        handler = self._table.get(opcode)
        if handler is None:
            raise VMError(f"No handler registered for opcode {opcode:#04x}")
        return handler(*args)

    def has(self, opcode: int) -> bool:
        return opcode in self._table

    def count(self) -> int:
        return len(self._table)


# ---------------------------------------------------------------------------
# CallFrame
# ---------------------------------------------------------------------------

@dataclass
class CallFrame:
    return_pc: int
    local_vars: dict = field(default_factory=dict)
    saved_registers: VMRegisters = field(default_factory=VMRegisters)


# ---------------------------------------------------------------------------
# SovereignVM — main virtual machine
# ---------------------------------------------------------------------------

class SovereignVM:
    """
    Minimal stack-based VM that executes VMInstruction programs.

    Features:
      - NAND-complete Boolean kernel
      - Entropy constraint enforcement (H <= 0.20 per DSL)
      - WORM commit / checkpoint via WORMLog
      - Routing dispatch table
      - 64KB memory space
      - Call/return stack for subroutines
    """

    ENTROPY_LIMIT = 0.20  # DSL constraint

    def __init__(
        self,
        program: list[VMInstruction],
        dispatch_table: Optional[DispatchTable] = None,
        output_buffer: Optional[io.StringIO] = None,
    ):
        self._program = program
        self._stack = VMStack()
        self._registers = VMRegisters()
        self._memory = VMMemory()
        self._worm = WORMLog()
        self._call_stack: list[CallFrame] = []
        self._local_vars: dict[str, Any] = {}
        self._dispatch = dispatch_table or DispatchTable()
        self._output = output_buffer or io.StringIO()
        self._checkpoints: list[dict] = []
        self._step_count = 0
        self._max_steps = 100_000

    # --- execution core -----------------------------------------------------

    def step(self) -> bool:
        """
        Execute one instruction.
        Returns False if HALT was reached, True otherwise.
        """
        pc = self._registers.pc
        if pc < 0 or pc >= len(self._program):
            self._registers.halt()
            return False

        instr = self._program[pc]
        self._registers.pc += 1
        self._step_count += 1

        try:
            self._execute(instr)
        except VMHaltException:
            self._registers.halt()
            return False
        except VMEntropyViolation:
            raise
        except VMStackUnderflow as exc:
            raise VMError(f"Stack underflow at pc={pc}: {exc}") from exc

        return not self._registers.is_halted()

    def run(self, max_steps: int = 10_000) -> Any:
        """
        Run for up to max_steps instructions.
        Returns top of stack, or None if stack is empty.
        """
        self._max_steps = max_steps
        steps = 0
        while steps < max_steps:
            if not self.step():
                break
            steps += 1
        else:
            raise VMError(f"VM exceeded max_steps={max_steps}")

        return self._stack.peek() if not self._stack.is_empty() else None

    def run_until_halt(self) -> Any:
        return self.run(max_steps=self._max_steps)

    def get_registers(self) -> VMRegisters:
        return VMRegisters(
            pc=self._registers.pc,
            sp=self._stack.size(),
            flags=self._registers.flags,
            entropy=self._registers.entropy,
        )

    def get_stack(self) -> list:
        return self._stack.as_list()

    def reset(self) -> None:
        """Reset VM to initial state."""
        self._stack.clear()
        self._registers = VMRegisters()
        self._memory = VMMemory()
        self._call_stack.clear()
        self._local_vars.clear()
        self._checkpoints.clear()
        self._step_count = 0

    def check_entropy_constraint(self) -> bool:
        """DSL constraint: H <= 0.20"""
        return self._registers.entropy <= self.ENTROPY_LIMIT

    def compute_entropy(self) -> float:
        """
        Shannon entropy of stack value distribution.
        H = -sum(p * ln(p))
        Normalized to [0.0, 1.0] by dividing by ln(N).
        """
        data = self._stack.as_list()
        if len(data) < 2:
            return 0.0

        # Count occurrences (hash-based)
        counts: dict = {}
        for v in data:
            key = type(v).__name__ + ':' + str(v)[:32]
            counts[key] = counts.get(key, 0) + 1

        n = len(data)
        h = 0.0
        for cnt in counts.values():
            p = cnt / n
            if p > 0:
                h -= p * math.log(p)

        # Normalize to [0, 1]
        max_h = math.log(n) if n > 1 else 1.0
        return h / max_h if max_h > 0 else 0.0

    # --- instruction execution ----------------------------------------------

    def _execute(self, instr: VMInstruction) -> None:
        op = instr.opcode
        arg = instr.arg
        sym = instr.symbol

        # ---- Stack primitives ----
        if op == VMOpcode.NOP:
            pass

        elif op == VMOpcode.PUSH:
            # Push arg as integer, or symbol as string if symbol is set
            self._stack.push(sym if sym else arg)
            self._update_entropy()

        elif op == VMOpcode.POP:
            self._stack.pop()

        elif op == VMOpcode.DUP:
            self._stack.push(self._stack.peek())

        elif op == VMOpcode.COPY:
            self._stack.push(self._stack.peek(arg))

        elif op == VMOpcode.SWAP:
            a = self._stack.pop()
            b = self._stack.pop()
            self._stack.push(a)
            self._stack.push(b)

        elif op == VMOpcode.ROT:
            c = self._stack.pop()
            b = self._stack.pop()
            a = self._stack.pop()
            self._stack.push(b)
            self._stack.push(c)
            self._stack.push(a)

        # ---- Arithmetic ----
        elif op == VMOpcode.ADD:
            b, a = self._stack.pop(), self._stack.pop()
            result = self._coerce(a) + self._coerce(b)
            self._stack.push(result)
            self._registers.update(result)

        elif op == VMOpcode.SUB:
            b, a = self._stack.pop(), self._stack.pop()
            result = self._coerce(a) - self._coerce(b)
            self._stack.push(result)
            self._registers.update(result)

        elif op == VMOpcode.MUL:
            b, a = self._stack.pop(), self._stack.pop()
            result = self._coerce(a) * self._coerce(b)
            self._stack.push(result)
            self._registers.update(result)

        elif op == VMOpcode.DIV:
            b, a = self._stack.pop(), self._stack.pop()
            bf, af = self._coerce_f(b), self._coerce_f(a)
            if bf == 0.0:
                raise VMError("Division by zero")
            result = af / bf
            self._stack.push(result)
            self._registers.update(result)

        elif op == VMOpcode.MOD:
            b, a = self._stack.pop(), self._stack.pop()
            bi, ai = int(self._coerce(b)), int(self._coerce(a))
            if bi == 0:
                raise VMError("Modulo by zero")
            self._stack.push(ai % bi)

        elif op == VMOpcode.NEG:
            a = self._stack.pop()
            self._stack.push(-self._coerce(a))

        elif op == VMOpcode.ABS:
            a = self._stack.pop()
            self._stack.push(abs(self._coerce(a)))

        # ---- Boolean (NAND-complete kernel) ----
        elif op == VMOpcode.NAND:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(nand_op(a, b))

        elif op == VMOpcode.NOT:
            a = self._stack.pop()
            self._stack.push(nand_not(a))

        elif op == VMOpcode.AND:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(nand_and(a, b))

        elif op == VMOpcode.OR:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(nand_or(a, b))

        elif op == VMOpcode.XOR:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(nand_xor(a, b))

        elif op == VMOpcode.XNOR:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(nand_xnor(a, b))

        elif op == VMOpcode.NOR:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(nand_nor(a, b))

        # ---- Comparison ----
        elif op == VMOpcode.EQ:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(1 if a == b else 0)

        elif op == VMOpcode.NEQ:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(1 if a != b else 0)

        elif op == VMOpcode.LT:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(1 if self._coerce(a) < self._coerce(b) else 0)

        elif op == VMOpcode.GT:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(1 if self._coerce(a) > self._coerce(b) else 0)

        elif op == VMOpcode.LE:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(1 if self._coerce(a) <= self._coerce(b) else 0)

        elif op == VMOpcode.GE:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(1 if self._coerce(a) >= self._coerce(b) else 0)

        # ---- Bitwise ----
        elif op == VMOpcode.BAND:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(int(self._coerce(a)) & int(self._coerce(b)))

        elif op == VMOpcode.BOR:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(int(self._coerce(a)) | int(self._coerce(b)))

        elif op == VMOpcode.BXOR:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(int(self._coerce(a)) ^ int(self._coerce(b)))

        elif op == VMOpcode.BNOT:
            a = self._stack.pop()
            self._stack.push(~int(self._coerce(a)))

        elif op == VMOpcode.SHL:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(int(self._coerce(a)) << (int(self._coerce(b)) & 63))

        elif op == VMOpcode.SHR:
            b, a = self._stack.pop(), self._stack.pop()
            self._stack.push(int(self._coerce(a)) >> (int(self._coerce(b)) & 63))

        # ---- Control flow ----
        elif op == VMOpcode.JMP:
            self._registers.pc = arg

        elif op == VMOpcode.JZ:
            top = self._stack.peek()
            if not top or top == 0:
                self._registers.pc = arg

        elif op == VMOpcode.JNZ:
            top = self._stack.peek()
            if top and top != 0:
                self._registers.pc = arg

        elif op == VMOpcode.CALL:
            frame = CallFrame(
                return_pc=self._registers.pc,
                local_vars=dict(self._local_vars),
                saved_registers=VMRegisters(
                    pc=self._registers.pc,
                    sp=self._stack.size(),
                    flags=self._registers.flags,
                    entropy=self._registers.entropy,
                ),
            )
            self._call_stack.append(frame)
            self._registers.pc = arg

        elif op == VMOpcode.RET:
            if not self._call_stack:
                raise VMHaltException("RETURN with empty call stack")
            frame = self._call_stack.pop()
            self._registers.pc = frame.return_pc
            self._local_vars = frame.local_vars

        elif op == VMOpcode.LOOP:
            count = self._stack.pop()
            count = int(self._coerce(count)) - 1
            if count > 0:
                self._stack.push(count)
                self._registers.pc = arg
            # else: loop exits naturally

        # ---- Routing ----
        elif op == VMOpcode.ROUTE:
            if self._dispatch.has(arg):
                top = self._stack.peek() if not self._stack.is_empty() else None
                result = self._dispatch.dispatch(arg, top)
                if result is not None:
                    self._stack.push(result)
            # If no handler: passthrough (soft routing)

        elif op == VMOpcode.DISPATCH:
            args_list = []
            n_args = arg
            for _ in range(n_args):
                args_list.insert(0, self._stack.pop())
            opcode_val = int(args_list[0]) if args_list else 0
            result = None
            if self._dispatch.has(opcode_val):
                result = self._dispatch.dispatch(opcode_val, *args_list[1:])
            if result is not None:
                self._stack.push(result)

        elif op == VMOpcode.GATE:
            """Jordan gate: evaluate |ψ⟩ under Φ^-2 entropy bound."""
            top = self._stack.peek() if not self._stack.is_empty() else 0
            entropy = self.compute_entropy()
            # Gate passes if entropy <= PHI^-2 ≈ 0.382
            phi_sq_inv = (math.sqrt(5) - 1) / 2  # approx 0.618, but use phi^-2
            phi_sq_inv = 1.0 / (((1 + math.sqrt(5)) / 2) ** 2)  # phi^-2 ≈ 0.382
            gate_result = 1 if entropy <= phi_sq_inv else 0
            self._stack.push(gate_result)

        elif op == VMOpcode.FILTER:
            """Entropy filter gate — enforce DSL H <= 0.20."""
            entropy = self.compute_entropy()
            self._registers.entropy = entropy
            if entropy > self.ENTROPY_LIMIT:
                # Drain high-entropy items
                while self._stack.size() > 1 and self.compute_entropy() > self.ENTROPY_LIMIT:
                    self._stack.pop()

        elif op == VMOpcode.FORWARD:
            # No-op in this VM — downstream pipeline handles forwarding
            pass

        # ---- Memory ----
        elif op == VMOpcode.LOAD:
            addr = int(self._stack.pop())
            self._stack.push(self._memory.read(addr))

        elif op == VMOpcode.STORE:
            value = self._stack.pop()
            addr = int(self._stack.pop())
            self._memory.write(addr, int(self._coerce(value)))

        elif op == VMOpcode.ALLOC:
            # Stub: push 0 (address of allocation)
            self._stack.push(0)

        elif op == VMOpcode.FREE:
            self._stack.pop()  # discard address

        # ---- WORM / State ----
        elif op == VMOpcode.COMMIT:
            snapshot = self._serialize_state()
            entry = self._worm.append(VMOpcode.COMMIT, snapshot)
            self._stack.push(entry.seq)

        elif op == VMOpcode.CHECKPOINT:
            cp = {
                'pc': self._registers.pc,
                'flags': self._registers.flags,
                'entropy': self._registers.entropy,
                'stack': list(self._stack.as_list()),
                'locals': dict(self._local_vars),
                'timestamp_ns': time.time_ns(),
            }
            self._checkpoints.append(cp)
            self._stack.push(len(self._checkpoints) - 1)

        elif op == VMOpcode.ROLLBACK:
            cp_idx = int(self._stack.pop()) if not self._stack.is_empty() else -1
            if self._checkpoints:
                idx = cp_idx if 0 <= cp_idx < len(self._checkpoints) else -1
                cp = self._checkpoints[idx]
                self._stack.clear()
                for v in cp['stack']:
                    self._stack.push(v)
                self._registers.pc = cp['pc']
                self._registers.flags = cp['flags']
                self._registers.entropy = cp['entropy']
                self._local_vars = dict(cp['locals'])

        elif op == VMOpcode.SEAL:
            snapshot = self._serialize_state()
            self._worm.append(VMOpcode.SEAL, snapshot)

        elif op == VMOpcode.VERIFY:
            valid = self._worm.all_valid()
            self._stack.push(1 if valid else 0)

        # ---- I/O ----
        elif op == VMOpcode.PRINT:
            value = self._stack.peek() if not self._stack.is_empty() else None
            self._output.write(repr(value) + '\n')

        elif op == VMOpcode.READ:
            self._stack.push(0)  # stub

        elif op == VMOpcode.EMIT:
            value = self._stack.pop()
            self._output.write(repr(value))

        # ---- Entropy management ----
        elif op == VMOpcode.MEASURE:
            entropy = self.compute_entropy()
            self._registers.entropy = entropy
            self._stack.push(entropy)

        elif op == VMOpcode.CLAMP:
            top = self._stack.pop()
            try:
                v = float(top)
                self._stack.push(max(0.0, min(self.ENTROPY_LIMIT, v)))
            except (TypeError, ValueError):
                self._stack.push(0.0)

        elif op == VMOpcode.ENTROPY:
            entropy = self.compute_entropy()
            self._registers.entropy = entropy
            self._stack.push(entropy)

        # ---- Halt ----
        elif op == VMOpcode.HALT:
            raise VMHaltException("HALT instruction reached")

        else:
            raise VMError(f"Unknown opcode: {op!r}")

    # --- helpers ------------------------------------------------------------

    def _coerce(self, v: Any) -> Any:
        """Coerce value to numeric type."""
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, bool):
            return 1 if v else 0
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                try:
                    return float(v)
                except ValueError:
                    return 0
        return 0

    def _coerce_f(self, v: Any) -> float:
        return float(self._coerce(v))

    def _update_entropy(self) -> None:
        if self._stack.size() >= 4:
            self._registers.entropy = self.compute_entropy()
            if self._registers.entropy > self.ENTROPY_LIMIT:
                raise VMEntropyViolation(
                    f"Entropy {self._registers.entropy:.4f} exceeds "
                    f"limit {self.ENTROPY_LIMIT}"
                )

    def _serialize_state(self) -> bytes:
        """Serialize current VM state to bytes for WORM commitment."""
        buf = io.BytesIO()
        # Header
        buf.write(struct.pack('>Q', time.time_ns()))
        buf.write(struct.pack('>I', self._registers.pc))
        buf.write(struct.pack('>I', self._registers.flags))
        buf.write(struct.pack('>d', self._registers.entropy))
        # Stack depth
        stack_data = self._stack.as_list()
        buf.write(struct.pack('>H', len(stack_data)))
        # Top 16 items as string repr
        for item in stack_data[:16]:
            encoded = repr(item).encode('utf-8')[:64]
            buf.write(struct.pack('>H', len(encoded)))
            buf.write(encoded)
        return buf.getvalue()

    def output(self) -> str:
        """Return captured output."""
        return self._output.getvalue()

    def worm_log(self) -> WORMLog:
        return self._worm

    def step_count(self) -> int:
        return self._step_count

    def stats(self) -> dict:
        return {
            'steps': self._step_count,
            'stack_depth': self._stack.size(),
            'pc': self._registers.pc,
            'entropy': self._registers.entropy,
            'worm_entries': self._worm.count(),
            'checkpoints': len(self._checkpoints),
            'entropy_compliant': self.check_entropy_constraint(),
        }


# ---------------------------------------------------------------------------
# VMAssembler — text-format assembler
# ---------------------------------------------------------------------------

class VMAssembler:
    """
    Parses a simple text assembly language into VMInstruction lists.

    Grammar:
        OPCODE [arg] [; comment]
        LABEL:
    """

    def assemble(self, source: str) -> list[VMInstruction]:
        """Parse text assembly to VMInstruction list."""
        instructions = []
        labels: dict[str, int] = {}
        pending_jumps: list[tuple[int, str]] = []  # (idx, label_name)

        lines = source.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('#'):
                continue
            # Strip inline comments
            line = line.split(';')[0].strip()
            if not line:
                continue

            # Label definition
            if line.endswith(':'):
                labels[line[:-1].strip()] = len(instructions)
                continue

            parts = line.split(None, 2)
            opcode_name = parts[0].upper()

            try:
                opcode = VMOpcode[opcode_name]
            except KeyError:
                raise VMError(f"Unknown opcode: {opcode_name!r}")

            arg = 0
            sym = ''

            if len(parts) > 1:
                raw_arg = parts[1].strip().strip('"\'')
                # Check if it's a label reference
                if raw_arg.isidentifier() and not raw_arg.startswith('0x'):
                    sym = raw_arg
                    pending_jumps.append((len(instructions), raw_arg))
                else:
                    try:
                        arg = int(raw_arg, 0)
                    except ValueError:
                        sym = raw_arg

            if len(parts) > 2:
                sym = parts[2].strip().strip('"\'')

            instructions.append(VMInstruction(opcode=opcode, arg=arg, symbol=sym))

        # Resolve label references
        for idx, label_name in pending_jumps:
            if label_name in labels:
                instructions[idx].arg = labels[label_name]
                instructions[idx].symbol = ''
            # else: leave as symbol (might be a dispatch name)

        return instructions

    def disassemble(self, instructions: list[VMInstruction]) -> str:
        """Convert VMInstruction list to text assembly."""
        lines = []
        for i, instr in enumerate(instructions):
            parts = [f'{i:4d}:  {instr.opcode.name:<12}']
            if instr.arg != 0:
                parts.append(f'{instr.arg}')
            if instr.symbol:
                parts.append(repr(instr.symbol))
            lines.append(' '.join(parts))
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Program builders (convenience functions)
# ---------------------------------------------------------------------------

def make_program(*spec: tuple) -> list[VMInstruction]:
    """
    Build a program from (opcode, arg, symbol) tuples.
    arg and symbol are optional.
    """
    instructions = []
    for item in spec:
        if isinstance(item, VMInstruction):
            instructions.append(item)
        elif isinstance(item, tuple):
            op = item[0]
            arg = item[1] if len(item) > 1 else 0
            sym = item[2] if len(item) > 2 else ''
            if isinstance(op, (str,)):
                op = VMOpcode[op.upper()]
            instructions.append(VMInstruction(opcode=op, arg=arg, symbol=sym))
        elif isinstance(item, VMOpcode):
            instructions.append(VMInstruction(opcode=item))
    return instructions


def push(value: Any) -> VMInstruction:
    if isinstance(value, str):
        return VMInstruction(VMOpcode.PUSH, 0, value)
    return VMInstruction(VMOpcode.PUSH, int(value) if isinstance(value, (int, float)) else 0,
                         str(value) if not isinstance(value, (int, float)) else '')


def halt() -> VMInstruction:
    return VMInstruction(VMOpcode.HALT)


def commit() -> VMInstruction:
    return VMInstruction(VMOpcode.COMMIT)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    # Test NAND kernel
    assert nand_op(0, 0) == 1
    assert nand_op(0, 1) == 1
    assert nand_op(1, 0) == 1
    assert nand_op(1, 1) == 0

    assert nand_not(0) == 1
    assert nand_not(1) == 0

    assert nand_and(1, 1) == 1
    assert nand_and(1, 0) == 0
    assert nand_and(0, 0) == 0

    assert nand_or(0, 0) == 0
    assert nand_or(1, 0) == 1
    assert nand_or(1, 1) == 1

    assert nand_xor(0, 0) == 0
    assert nand_xor(1, 0) == 1
    assert nand_xor(1, 1) == 0

    # Test VMStack
    stack = VMStack()
    stack.push(1)
    stack.push(2)
    assert stack.peek() == 2
    assert stack.pop() == 2
    assert stack.size() == 1

    # Test simple VM program: compute 3 + 4
    program = [
        VMInstruction(VMOpcode.PUSH, 3),
        VMInstruction(VMOpcode.PUSH, 4),
        VMInstruction(VMOpcode.ADD),
        VMInstruction(VMOpcode.HALT),
    ]
    vm = SovereignVM(program)
    result = vm.run()
    assert result == 7, f"Expected 7, got {result}"

    # Test NAND in VM
    nand_prog = [
        VMInstruction(VMOpcode.PUSH, 1),
        VMInstruction(VMOpcode.PUSH, 1),
        VMInstruction(VMOpcode.NAND),
        VMInstruction(VMOpcode.HALT),
    ]
    vm2 = SovereignVM(nand_prog)
    result2 = vm2.run()
    assert result2 == 0, f"NAND(1,1) should be 0, got {result2}"

    # Test CHECKPOINT + COMMIT
    cp_prog = [
        VMInstruction(VMOpcode.PUSH, 42),
        VMInstruction(VMOpcode.CHECKPOINT),
        VMInstruction(VMOpcode.POP),  # remove checkpoint index
        VMInstruction(VMOpcode.COMMIT),
        VMInstruction(VMOpcode.HALT),
    ]
    vm3 = SovereignVM(cp_prog)
    vm3.run()
    assert vm3.worm_log().count() >= 1

    # Test assembler
    asm = VMAssembler()
    prog_text = """
        PUSH 10
        PUSH 20
        ADD
        HALT
    """
    instrs = asm.assemble(prog_text)
    assert len(instrs) == 4
    vm4 = SovereignVM(instrs)
    result4 = vm4.run()
    assert result4 == 30

    # Test entropy constraint
    entropy_prog = [
        VMInstruction(VMOpcode.ENTROPY),
        VMInstruction(VMOpcode.HALT),
    ]
    vm5 = SovereignVM(entropy_prog)
    result5 = vm5.run()
    assert isinstance(result5, float)

    return True


# ---------------------------------------------------------------------------
# VMProfiler — instruction-level profiling
# ---------------------------------------------------------------------------

@dataclass
class VMProfile:
    """Runtime profiling data collected from VM execution."""
    instruction_counts: dict = field(default_factory=dict)
    total_steps: int = 0
    total_time_ns: int = 0
    worm_commits: int = 0
    checkpoints: int = 0
    peak_stack_depth: int = 0
    entropy_violations: int = 0
    entropy_samples: list = field(default_factory=list)

    def record(self, opcode: VMOpcode, stack_depth: int) -> None:
        name = opcode.name
        self.instruction_counts[name] = self.instruction_counts.get(name, 0) + 1
        self.total_steps += 1
        if stack_depth > self.peak_stack_depth:
            self.peak_stack_depth = stack_depth

    def top_instructions(self, n: int = 10) -> list[tuple[str, int]]:
        return sorted(self.instruction_counts.items(), key=lambda x: -x[1])[:n]

    def summary(self) -> str:
        lines = [
            f"VMProfile: {self.total_steps} steps",
            f"  Peak stack depth: {self.peak_stack_depth}",
            f"  WORM commits: {self.worm_commits}",
            f"  Checkpoints: {self.checkpoints}",
            f"  Entropy violations: {self.entropy_violations}",
            f"  Top instructions:",
        ]
        for name, count in self.top_instructions(5):
            pct = count / self.total_steps * 100 if self.total_steps else 0
            lines.append(f"    {name:<15} {count:>6}  ({pct:.1f}%)")
        return '\n'.join(lines)


class ProfilingVM(SovereignVM):
    """
    SovereignVM subclass that collects profiling data during execution.
    """

    def __init__(self, program: list[VMInstruction], **kwargs):
        super().__init__(program, **kwargs)
        self._profile = VMProfile()
        self._start_ns: int = 0

    def run(self, max_steps: int = 10_000) -> Any:
        self._start_ns = time.time_ns()
        result = super().run(max_steps=max_steps)
        self._profile.total_time_ns = time.time_ns() - self._start_ns
        return result

    def step(self) -> bool:
        pc = self._registers.pc
        if 0 <= pc < len(self._program):
            instr = self._program[pc]
            self._profile.record(instr.opcode, self._stack.size())
        result = super().step()
        if not result:
            self._profile.worm_commits = self._worm.count()
            self._profile.checkpoints = len(self._checkpoints)
        return result

    def profile(self) -> VMProfile:
        return self._profile


# ---------------------------------------------------------------------------
# VMDebugger — interactive debugging interface
# ---------------------------------------------------------------------------

class VMDebugger:
    """
    Provides debugging facilities for SovereignVM programs.
    Supports breakpoints, single-step, watch expressions.
    """

    def __init__(self, vm: SovereignVM):
        self._vm = vm
        self._breakpoints: set[int] = set()
        self._watchpoints: dict[str, Any] = {}   # name -> previous value
        self._trace: list[dict] = []
        self._max_trace = 1000

    def add_breakpoint(self, pc: int) -> None:
        self._breakpoints.add(pc)

    def remove_breakpoint(self, pc: int) -> None:
        self._breakpoints.discard(pc)

    def watch(self, name: str, getter: Callable) -> None:
        """Watch a named value computed by getter(vm) at each step."""
        self._watchpoints[name] = (getter, None)

    def run_to_breakpoint(self, max_steps: int = 100_000) -> Optional[int]:
        """
        Run until a breakpoint is hit or max_steps reached.
        Returns the PC where execution stopped, or None if halted.
        """
        steps = 0
        while steps < max_steps:
            pc = self._vm._registers.pc

            if pc in self._breakpoints and steps > 0:
                return pc

            # Collect trace entry
            if len(self._trace) < self._max_trace:
                entry = {
                    'step': self._vm.step_count(),
                    'pc': pc,
                    'stack': self._vm._stack.as_list()[:4],
                    'entropy': self._vm._registers.entropy,
                }
                # Check watchpoints
                for name, (getter, prev) in list(self._watchpoints.items()):
                    try:
                        current = getter(self._vm)
                    except Exception:
                        current = None
                    if current != prev:
                        entry[f'watch:{name}'] = {'old': prev, 'new': current}
                        self._watchpoints[name] = (getter, current)
                self._trace.append(entry)

            if not self._vm.step():
                return None
            steps += 1
        return None

    def step_once(self) -> bool:
        """Execute one instruction."""
        return self._vm.step()

    def dump_trace(self, last_n: int = 20) -> str:
        """Return the last N trace entries as human-readable text."""
        entries = self._trace[-last_n:]
        lines = [f"VMDebugger trace (last {len(entries)} entries):"]
        for entry in entries:
            stack_str = str(entry.get('stack', []))[:40]
            lines.append(
                f"  step={entry['step']:5d}  pc={entry['pc']:4d}  "
                f"stack={stack_str}  H={entry['entropy']:.4f}"
            )
            for k, v in entry.items():
                if k.startswith('watch:'):
                    lines.append(f"    {k}: {v}")
        return '\n'.join(lines)

    def clear_trace(self) -> None:
        self._trace.clear()

    def state_at(self, step: int) -> Optional[dict]:
        for entry in self._trace:
            if entry['step'] == step:
                return entry
        return None


# ---------------------------------------------------------------------------
# VMBenchmark — measure VM performance
# ---------------------------------------------------------------------------

class VMBenchmark:
    """
    Benchmarks the VM on standard programs.
    Reports instructions per second and overhead per instruction.
    """

    def run_nop_loop(self, count: int = 10_000) -> dict:
        """Benchmark: execute `count` NOPs."""
        program = (
            [VMInstruction(VMOpcode.PUSH, count)] +
            [VMInstruction(VMOpcode.NOP)] * min(count, 1000) +
            [VMInstruction(VMOpcode.HALT)]
        )
        vm = SovereignVM(program)
        start = time.time_ns()
        vm.run(max_steps=count + 10)
        elapsed_ns = time.time_ns() - start
        steps = vm.step_count()
        ips = steps / (elapsed_ns / 1e9) if elapsed_ns > 0 else 0.0
        return {
            'steps': steps,
            'elapsed_ns': elapsed_ns,
            'ips': ips,
            'ns_per_step': elapsed_ns / steps if steps > 0 else 0,
        }

    def run_arithmetic(self, count: int = 1000) -> dict:
        """Benchmark: additions in a tight loop."""
        program = []
        for i in range(count):
            program.append(VMInstruction(VMOpcode.PUSH, i))
            if i > 0:
                program.append(VMInstruction(VMOpcode.ADD))
        program.append(VMInstruction(VMOpcode.HALT))

        vm = SovereignVM(program)
        start = time.time_ns()
        result = vm.run(max_steps=count * 3)
        elapsed_ns = time.time_ns() - start
        return {
            'result': result,
            'steps': vm.step_count(),
            'elapsed_ns': elapsed_ns,
            'ips': vm.step_count() / (elapsed_ns / 1e9) if elapsed_ns > 0 else 0.0,
        }

    def run_boolean(self, count: int = 1000) -> dict:
        """Benchmark: NAND operations."""
        program = []
        for i in range(count):
            program.append(VMInstruction(VMOpcode.PUSH, i & 1))
            program.append(VMInstruction(VMOpcode.PUSH, (i >> 1) & 1))
            program.append(VMInstruction(VMOpcode.NAND))
        program.append(VMInstruction(VMOpcode.HALT))

        vm = SovereignVM(program)
        start = time.time_ns()
        result = vm.run(max_steps=count * 4)
        elapsed_ns = time.time_ns() - start
        return {
            'result': result,
            'steps': vm.step_count(),
            'elapsed_ns': elapsed_ns,
        }


# ---------------------------------------------------------------------------
# VMProgram — named program container with metadata
# ---------------------------------------------------------------------------

@dataclass
class VMProgram:
    """A named, versioned VM program with metadata."""
    name: str
    version: str
    instructions: list[VMInstruction]
    description: str = ""
    author: str = ""
    created_ns: int = field(default_factory=time.time_ns)
    checksum: str = field(default="")

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        payload = self.name + self.version + str(len(self.instructions))
        for instr in self.instructions:
            payload += f"{instr.opcode.value}{instr.arg}{instr.symbol}"
        return hashlib.blake2b(payload.encode(), digest_size=16).hexdigest()

    def build_vm(self, **kwargs) -> SovereignVM:
        return SovereignVM(self.instructions, **kwargs)

    def run(self, max_steps: int = 10_000) -> Any:
        vm = self.build_vm()
        return vm.run(max_steps=max_steps)

    def instruction_count(self) -> int:
        return len(self.instructions)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'created_ns': self.created_ns,
            'checksum': self.checksum,
            'instructions': [
                {
                    'opcode': i.opcode.name,
                    'arg': i.arg,
                    'symbol': i.symbol,
                }
                for i in self.instructions
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'VMProgram':
        instructions = [
            VMInstruction(
                opcode=VMOpcode[i['opcode']],
                arg=i.get('arg', 0),
                symbol=i.get('symbol', ''),
            )
            for i in d.get('instructions', [])
        ]
        return cls(
            name=d['name'],
            version=d.get('version', '0.0.1'),
            instructions=instructions,
            description=d.get('description', ''),
            author=d.get('author', ''),
        )

    @classmethod
    def from_source(cls, name: str, source: str, **kwargs) -> 'VMProgram':
        """Assemble from text source."""
        asm = VMAssembler()
        instructions = asm.assemble(source)
        return cls(name=name, version="1.0.0", instructions=instructions, **kwargs)


# ---------------------------------------------------------------------------
# Standard library programs
# ---------------------------------------------------------------------------

def make_sum_program(values: list[int]) -> VMProgram:
    """Build a program that pushes all values and sums them."""
    instructions = []
    if not values:
        instructions.append(VMInstruction(VMOpcode.PUSH, 0))
    else:
        for v in values:
            instructions.append(VMInstruction(VMOpcode.PUSH, v))
        for _ in range(len(values) - 1):
            instructions.append(VMInstruction(VMOpcode.ADD))
    instructions.append(VMInstruction(VMOpcode.HALT))
    return VMProgram("sum", "1.0.0", instructions, "Sum a list of values")


def make_factorial_iterative(n: int) -> VMProgram:
    """Build a program that computes n! iteratively."""
    source = f"""
        PUSH {n}        ; counter n
        PUSH 1          ; accumulator
    loop:
        SWAP            ; acc, n
        DUP             ; acc, n, n
        PUSH 0
        EQ              ; acc, n, (n==0)
        JNZ done        ; if n==0 jump to done
        SWAP            ; n, acc
        COPY 1          ; n, acc, n
        MUL             ; n, acc*n
        SWAP            ; acc*n, n
        PUSH 1
        SUB             ; acc*n, n-1
        SWAP            ; n-1, acc*n
        JMP loop
    done:
        POP             ; remove counter
        HALT
    """
    try:
        asm = VMAssembler()
        instructions = asm.assemble(source)
        return VMProgram(f"factorial_{n}", "1.0.0", instructions,
                         f"Compute {n}!")
    except Exception:
        # Fallback: just push the result directly
        import math as _math
        result = _math.factorial(n)
        return VMProgram(f"factorial_{n}", "1.0.0",
                         [VMInstruction(VMOpcode.PUSH, result),
                          VMInstruction(VMOpcode.HALT)],
                         f"Precomputed {n}!")


def make_nand_truth_table() -> VMProgram:
    """Build a program that computes all 4 NAND combinations."""
    instructions = [
        # NAND(0,0) = 1
        VMInstruction(VMOpcode.PUSH, 0),
        VMInstruction(VMOpcode.PUSH, 0),
        VMInstruction(VMOpcode.NAND),
        # NAND(0,1) = 1
        VMInstruction(VMOpcode.PUSH, 0),
        VMInstruction(VMOpcode.PUSH, 1),
        VMInstruction(VMOpcode.NAND),
        # NAND(1,0) = 1
        VMInstruction(VMOpcode.PUSH, 1),
        VMInstruction(VMOpcode.PUSH, 0),
        VMInstruction(VMOpcode.NAND),
        # NAND(1,1) = 0
        VMInstruction(VMOpcode.PUSH, 1),
        VMInstruction(VMOpcode.PUSH, 1),
        VMInstruction(VMOpcode.NAND),
        # Commit truth table to WORM
        VMInstruction(VMOpcode.COMMIT),
        VMInstruction(VMOpcode.HALT),
    ]
    return VMProgram("nand_truth_table", "1.0.0", instructions,
                     "NAND truth table with WORM commit")


if __name__ == "__main__":
    assert _self_test(), "Self-test failed"
    print("vm_executor.py: all self-tests passed")

    # Demo: sum program
    prog = make_sum_program([1, 2, 3, 4, 5])
    result = prog.run()
    print(f"Sum [1..5] = {result}")

    # Demo: NAND truth table
    nand_prog = make_nand_truth_table()
    vm = nand_prog.build_vm()
    vm.run()
    stack = vm.get_stack()
    print(f"NAND truth table stack (bottom to top): {stack}")
    print(f"WORM commits: {vm.worm_log().count()}")

    # Demo: profiling
    prof_vm = ProfilingVM([
        VMInstruction(VMOpcode.PUSH, 100),
        VMInstruction(VMOpcode.PUSH, 200),
        VMInstruction(VMOpcode.ADD),
        VMInstruction(VMOpcode.NAND),
        VMInstruction(VMOpcode.NOT),
        VMInstruction(VMOpcode.COMMIT),
        VMInstruction(VMOpcode.HALT),
    ])
    prof_vm.run()
    print("\n" + prof_vm.profile().summary())

    # Demo: benchmark
    bench = VMBenchmark()
    nop_result = bench.run_nop_loop(100)
    print(f"\nBenchmark NOP loop: {nop_result['ips']:.0f} instructions/sec")

    arith_result = bench.run_arithmetic(50)
    print(f"Benchmark arithmetic: {arith_result['steps']} steps, "
          f"result={arith_result['result']}")

    # Demo: assembler disassembly
    asm = VMAssembler()
    prog2 = [
        VMInstruction(VMOpcode.PUSH, 42),
        VMInstruction(VMOpcode.PUSH, 58),
        VMInstruction(VMOpcode.ADD),
        VMInstruction(VMOpcode.COMMIT),
        VMInstruction(VMOpcode.HALT),
    ]
    print("\n" + asm.disassemble(prog2))
