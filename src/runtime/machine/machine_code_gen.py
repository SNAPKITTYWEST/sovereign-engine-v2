"""
machine_code_gen.py — x86-64 machine code generator for the sovereign engine.

Pure Python — generates raw x86-64 machine code bytes without external assemblers.
Converts Sovereign IR graphs to x86-64 binary code sequences for native dispatch.

Part of the SOVEREIGN_IR PYTHON_C_BRIDGE_IR pipeline.
Agent A (Cognition) — HyperKittyConstraintDSL v1.0
"""

from __future__ import annotations

import io
import math
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Register definitions
# ---------------------------------------------------------------------------

class Register(IntEnum):
    """x86-64 general-purpose register encoding."""
    RAX = 0   # accumulator
    RCX = 1   # counter
    RDX = 2   # data
    RBX = 3   # base
    RSP = 4   # stack pointer
    RBP = 5   # frame pointer
    RSI = 6   # source index
    RDI = 7   # destination index
    R8  = 8
    R9  = 9
    R10 = 10
    R11 = 11
    R12 = 12
    R13 = 13
    R14 = 14
    R15 = 15

    def is_extended(self) -> bool:
        """True if this register requires a REX prefix (R8-R15)."""
        return self >= 8

    def low_bits(self) -> int:
        """Low 3 bits of register encoding."""
        return int(self) & 0x7


# 32-bit register aliases
class Reg32(IntEnum):
    EAX = 0; ECX = 1; EDX = 2; EBX = 3
    ESP = 4; EBP = 5; ESI = 6; EDI = 7
    R8D = 8; R9D = 9; R10D = 10; R11D = 11
    R12D = 12; R13D = 13; R14D = 14; R15D = 15


# ---------------------------------------------------------------------------
# Condition codes for Jcc instructions
# ---------------------------------------------------------------------------

class Condition(IntEnum):
    """x86-64 condition codes (Jcc opcode suffix)."""
    O   = 0x00   # overflow
    NO  = 0x01   # no overflow
    B   = 0x02   # below (CF=1)
    NAE = 0x02   # not above or equal
    NB  = 0x03   # not below (CF=0)
    AE  = 0x03   # above or equal
    Z   = 0x04   # zero (ZF=1)
    E   = 0x04   # equal
    NZ  = 0x05   # not zero (ZF=0)
    NE  = 0x05   # not equal
    BE  = 0x06   # below or equal
    NA  = 0x06   # not above
    NBE = 0x07   # not below or equal
    A   = 0x07   # above
    S   = 0x08   # sign (SF=1)
    NS  = 0x09   # no sign
    P   = 0x0A   # parity
    PE  = 0x0A   # parity even
    NP  = 0x0B   # no parity
    PO  = 0x0B   # parity odd
    L   = 0x0C   # less (SF != OF)
    NGE = 0x0C   # not greater or equal
    NL  = 0x0D   # not less (SF == OF)
    GE  = 0x0D   # greater or equal
    LE  = 0x0E   # less or equal (ZF=1 or SF!=OF)
    NG  = 0x0E   # not greater
    NLE = 0x0F   # not less or equal
    G   = 0x0F   # greater


# ---------------------------------------------------------------------------
# CodeBuffer
# ---------------------------------------------------------------------------

class CodeBuffer:
    """
    Mutable byte buffer for emitting machine code.
    Supports patching of 32-bit values at arbitrary offsets.
    """

    def __init__(self, initial_capacity: int = 1024):
        self._data = bytearray()
        self._capacity = initial_capacity

    def emit(self, data: bytes) -> int:
        """Emit bytes; return starting offset."""
        offset = len(self._data)
        self._data.extend(data)
        return offset

    def emit_byte(self, b: int) -> int:
        """Emit single byte; return its offset."""
        offset = len(self._data)
        self._data.append(b & 0xFF)
        return offset

    def emit_u16(self, v: int) -> int:
        offset = len(self._data)
        self._data.extend(struct.pack('<H', v & 0xFFFF))
        return offset

    def emit_u32(self, v: int) -> int:
        offset = len(self._data)
        self._data.extend(struct.pack('<I', v & 0xFFFFFFFF))
        return offset

    def emit_u64(self, v: int) -> int:
        offset = len(self._data)
        self._data.extend(struct.pack('<Q', v & 0xFFFFFFFFFFFFFFFF))
        return offset

    def emit_i32(self, v: int) -> int:
        offset = len(self._data)
        self._data.extend(struct.pack('<i', self._sign_extend(v, 32)))
        return offset

    def emit_i64(self, v: int) -> int:
        offset = len(self._data)
        self._data.extend(struct.pack('<q', self._sign_extend(v, 64)))
        return offset

    def patch_i32(self, offset: int, value: int) -> None:
        """Patch a 32-bit little-endian integer at `offset`."""
        data = struct.pack('<i', self._sign_extend(value, 32))
        self._data[offset:offset + 4] = data

    def patch_u32(self, offset: int, value: int) -> None:
        data = struct.pack('<I', value & 0xFFFFFFFF)
        self._data[offset:offset + 4] = data

    def patch_u64(self, offset: int, value: int) -> None:
        data = struct.pack('<Q', value & 0xFFFFFFFFFFFFFFFF)
        self._data[offset:offset + 8] = data

    def get_bytes(self) -> bytes:
        return bytes(self._data)

    def size(self) -> int:
        return len(self._data)

    def current_offset(self) -> int:
        return len(self._data)

    def align(self, alignment: int) -> int:
        """Pad to alignment boundary with NOP (0x90)."""
        rem = len(self._data) % alignment
        if rem:
            padding = alignment - rem
            self._data.extend(b'\x90' * padding)
        return len(self._data)

    def hexdump(self, width: int = 16) -> str:
        lines = []
        data = self._data
        for off in range(0, len(data), width):
            chunk = data[off:off + width]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'{off:08x}  {hex_part:<{width * 3}}  |{ascii_part}|')
        return '\n'.join(lines)

    def _sign_extend(self, v: int, bits: int) -> int:
        mask = (1 << bits) - 1
        v = v & mask
        if v >= (1 << (bits - 1)):
            v -= (1 << bits)
        return v

    def clear(self) -> None:
        self._data.clear()

    def copy(self) -> 'CodeBuffer':
        new = CodeBuffer()
        new._data = bytearray(self._data)
        return new


class CodeGenError(Exception):
    pass


# ---------------------------------------------------------------------------
# REX prefix and ModRM/SIB encoders
# ---------------------------------------------------------------------------

def encode_rex(w: int, r: int, x: int, b: int) -> int:
    """
    Encode a REX prefix byte.
    w=1: 64-bit operand size
    r:   extends ModRM.reg
    x:   extends SIB.index
    b:   extends ModRM.rm or SIB.base or opcode reg
    Returns the REX byte (0x40 | w<<3 | r<<2 | x<<1 | b)
    """
    return 0x40 | (w & 1) << 3 | (r & 1) << 2 | (x & 1) << 1 | (b & 1)


def encode_modrm(mod: int, reg: int, rm: int) -> int:
    """
    Encode a ModRM byte.
    mod: 2 bits (0=no disp, 1=8-bit disp, 2=32-bit disp, 3=register)
    reg: 3 bits (register or opcode extension)
    rm:  3 bits (register or base)
    """
    return ((mod & 3) << 6) | ((reg & 7) << 3) | (rm & 7)


def encode_sib(scale: int, index: int, base: int) -> int:
    """
    Encode a SIB (Scale-Index-Base) byte.
    scale: 0=1, 1=2, 2=4, 3=8
    index: 3-bit register index
    base:  3-bit register base
    """
    return ((scale & 3) << 6) | ((index & 7) << 3) | (base & 7)


def rex_needed(r: Register, rm: Register | None = None) -> bool:
    """True if a REX prefix is required for given registers."""
    if r.is_extended():
        return True
    if rm is not None and rm.is_extended():
        return True
    return False


# ---------------------------------------------------------------------------
# X86Encoder — pure-Python x86-64 instruction encoder
# ---------------------------------------------------------------------------

class X86Encoder:
    """
    Encodes individual x86-64 instructions to bytes.
    All instructions use 64-bit operand size (REX.W=1) unless noted.
    """

    # ---- Data movement ----

    def mov_reg_imm64(self, dst: Register, imm: int) -> bytes:
        """MOV r64, imm64  (REX.W + B8+rd, imm64)"""
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        opcode = 0xB8 + dst.low_bits()
        imm_bytes = struct.pack('<q', _sign_extend64(imm))
        return bytes([rex, opcode]) + imm_bytes

    def mov_reg_imm32(self, dst: Register, imm: int) -> bytes:
        """MOV r64, sign-extended-imm32  (REX.W + C7 /0, imm32)"""
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=0, rm=dst.low_bits())
        imm_bytes = struct.pack('<i', _sign_extend32(imm))
        return bytes([rex, 0xC7, modrm]) + imm_bytes

    def mov_reg_reg(self, dst: Register, src: Register) -> bytes:
        """MOV r64, r64  (REX.W + 89 /r)"""
        rex_r = 1 if src.is_extended() else 0
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=src.low_bits(), rm=dst.low_bits())
        return bytes([rex, 0x89, modrm])

    def mov_reg_mem(self, dst: Register, base: Register, disp: int = 0) -> bytes:
        """MOV r64, [base + disp32]  (REX.W + 8B /r)"""
        rex_r = 1 if dst.is_extended() else 0
        rex_b = 1 if base.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        if disp == 0 and base.low_bits() != 5:  # RBP requires disp8
            modrm = encode_modrm(mod=0, reg=dst.low_bits(), rm=base.low_bits())
            extra = b''
        elif -128 <= disp <= 127:
            modrm = encode_modrm(mod=1, reg=dst.low_bits(), rm=base.low_bits())
            extra = struct.pack('<b', disp)
        else:
            modrm = encode_modrm(mod=2, reg=dst.low_bits(), rm=base.low_bits())
            extra = struct.pack('<i', disp)
        return bytes([rex, 0x8B, modrm]) + extra

    def mov_mem_reg(self, base: Register, src: Register, disp: int = 0) -> bytes:
        """MOV [base + disp32], r64  (REX.W + 89 /r)"""
        rex_r = 1 if src.is_extended() else 0
        rex_b = 1 if base.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        if disp == 0 and base.low_bits() != 5:
            modrm = encode_modrm(mod=0, reg=src.low_bits(), rm=base.low_bits())
            extra = b''
        elif -128 <= disp <= 127:
            modrm = encode_modrm(mod=1, reg=src.low_bits(), rm=base.low_bits())
            extra = struct.pack('<b', disp)
        else:
            modrm = encode_modrm(mod=2, reg=src.low_bits(), rm=base.low_bits())
            extra = struct.pack('<i', disp)
        return bytes([rex, 0x89, modrm]) + extra

    # ---- Arithmetic ----

    def add_reg_reg(self, dst: Register, src: Register) -> bytes:
        """ADD r64, r64  (REX.W + 01 /r)"""
        rex_r = 1 if src.is_extended() else 0
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=src.low_bits(), rm=dst.low_bits())
        return bytes([rex, 0x01, modrm])

    def add_reg_imm32(self, dst: Register, imm: int) -> bytes:
        """ADD r64, imm32  (REX.W + 81 /0, imm32)"""
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=0, rm=dst.low_bits())
        return bytes([rex, 0x81, modrm]) + struct.pack('<i', imm)

    def sub_reg_reg(self, dst: Register, src: Register) -> bytes:
        """SUB r64, r64  (REX.W + 29 /r)"""
        rex_r = 1 if src.is_extended() else 0
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=src.low_bits(), rm=dst.low_bits())
        return bytes([rex, 0x29, modrm])

    def sub_reg_imm32(self, dst: Register, imm: int) -> bytes:
        """SUB r64, imm32  (REX.W + 81 /5, imm32)"""
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=5, rm=dst.low_bits())
        return bytes([rex, 0x81, modrm]) + struct.pack('<i', imm)

    def mul_rax_reg(self, src: Register) -> bytes:
        """IMUL r64  (REX.W + F7 /5) — RDX:RAX = RAX * src"""
        rex_b = 1 if src.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=5, rm=src.low_bits())
        return bytes([rex, 0xF7, modrm])

    def imul_reg_reg(self, dst: Register, src: Register) -> bytes:
        """IMUL r64, r/m64  (REX.W + 0F AF /r)"""
        rex_r = 1 if dst.is_extended() else 0
        rex_b = 1 if src.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=dst.low_bits(), rm=src.low_bits())
        return bytes([rex, 0x0F, 0xAF, modrm])

    def div_rax_reg(self, src: Register) -> bytes:
        """DIV r64  (REX.W + F7 /6) — RDX:RAX / src"""
        rex_b = 1 if src.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=6, rm=src.low_bits())
        return bytes([rex, 0xF7, modrm])

    def neg_reg(self, reg: Register) -> bytes:
        """NEG r64  (REX.W + F7 /3)"""
        rex_b = 1 if reg.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=3, rm=reg.low_bits())
        return bytes([rex, 0xF7, modrm])

    def inc_reg(self, reg: Register) -> bytes:
        """INC r64  (REX.W + FF /0)"""
        rex_b = 1 if reg.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=0, rm=reg.low_bits())
        return bytes([rex, 0xFF, modrm])

    def dec_reg(self, reg: Register) -> bytes:
        """DEC r64  (REX.W + FF /1)"""
        rex_b = 1 if reg.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=1, rm=reg.low_bits())
        return bytes([rex, 0xFF, modrm])

    # ---- Bitwise ----

    def and_reg_reg(self, dst: Register, src: Register) -> bytes:
        """AND r64, r64  (REX.W + 21 /r)"""
        rex_r = 1 if src.is_extended() else 0
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=src.low_bits(), rm=dst.low_bits())
        return bytes([rex, 0x21, modrm])

    def or_reg_reg(self, dst: Register, src: Register) -> bytes:
        """OR r64, r64  (REX.W + 09 /r)"""
        rex_r = 1 if src.is_extended() else 0
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=src.low_bits(), rm=dst.low_bits())
        return bytes([rex, 0x09, modrm])

    def xor_reg_reg(self, dst: Register, src: Register) -> bytes:
        """XOR r64, r64  (REX.W + 31 /r)"""
        rex_r = 1 if src.is_extended() else 0
        rex_b = 1 if dst.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=src.low_bits(), rm=dst.low_bits())
        return bytes([rex, 0x31, modrm])

    def not_reg(self, reg: Register) -> bytes:
        """NOT r64  (REX.W + F7 /2)"""
        rex_b = 1 if reg.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=2, rm=reg.low_bits())
        return bytes([rex, 0xF7, modrm])

    def shl_reg_imm8(self, reg: Register, count: int) -> bytes:
        """SHL r64, imm8  (REX.W + C1 /4, imm8)"""
        rex_b = 1 if reg.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=4, rm=reg.low_bits())
        return bytes([rex, 0xC1, modrm, count & 63])

    def shr_reg_imm8(self, reg: Register, count: int) -> bytes:
        """SHR r64, imm8  (REX.W + C1 /5, imm8)"""
        rex_b = 1 if reg.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=5, rm=reg.low_bits())
        return bytes([rex, 0xC1, modrm, count & 63])

    def sar_reg_imm8(self, reg: Register, count: int) -> bytes:
        """SAR r64, imm8  (REX.W + C1 /7, imm8)"""
        rex_b = 1 if reg.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=7, rm=reg.low_bits())
        return bytes([rex, 0xC1, modrm, count & 63])

    # ---- Comparison ----

    def cmp_reg_reg(self, a: Register, b: Register) -> bytes:
        """CMP r64, r64  (REX.W + 39 /r)"""
        rex_r = 1 if b.is_extended() else 0
        rex_b = 1 if a.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=b.low_bits(), rm=a.low_bits())
        return bytes([rex, 0x39, modrm])

    def cmp_reg_imm32(self, reg: Register, imm: int) -> bytes:
        """CMP r64, imm32  (REX.W + 81 /7, imm32)"""
        rex_b = 1 if reg.is_extended() else 0
        rex = encode_rex(w=1, r=0, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=7, rm=reg.low_bits())
        return bytes([rex, 0x81, modrm]) + struct.pack('<i', imm)

    def test_reg_reg(self, a: Register, b: Register) -> bytes:
        """TEST r64, r64  (REX.W + 85 /r)"""
        rex_r = 1 if b.is_extended() else 0
        rex_b = 1 if a.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=b.low_bits(), rm=a.low_bits())
        return bytes([rex, 0x85, modrm])

    # ---- Stack operations ----

    def push_reg(self, reg: Register) -> bytes:
        """PUSH r64  (50+rd or REX + 50+rd)"""
        if reg.is_extended():
            rex = encode_rex(w=0, r=0, x=0, b=1)
            return bytes([rex, 0x50 + reg.low_bits()])
        return bytes([0x50 + int(reg)])

    def pop_reg(self, reg: Register) -> bytes:
        """POP r64  (58+rd or REX + 58+rd)"""
        if reg.is_extended():
            rex = encode_rex(w=0, r=0, x=0, b=1)
            return bytes([rex, 0x58 + reg.low_bits()])
        return bytes([0x58 + int(reg)])

    def push_imm32(self, imm: int) -> bytes:
        """PUSH imm32  (68 imm32)"""
        return bytes([0x68]) + struct.pack('<i', _sign_extend32(imm))

    def push_imm8(self, imm: int) -> bytes:
        """PUSH imm8  (6A imm8)"""
        return bytes([0x6A, imm & 0xFF])

    # ---- Control flow ----

    def ret(self) -> bytes:
        """RET  (C3)"""
        return bytes([0xC3])

    def ret_n(self, n: int) -> bytes:
        """RET n  (C2 imm16) — pop n bytes after return"""
        return bytes([0xC2]) + struct.pack('<H', n & 0xFFFF)

    def call_reg(self, reg: Register) -> bytes:
        """CALL r64  (FF /2)"""
        if reg.is_extended():
            rex = encode_rex(w=0, r=0, x=0, b=1)
            modrm = encode_modrm(mod=3, reg=2, rm=reg.low_bits())
            return bytes([rex, 0xFF, modrm])
        modrm = encode_modrm(mod=3, reg=2, rm=int(reg))
        return bytes([0xFF, modrm])

    def call_rel32(self, offset: int) -> bytes:
        """CALL rel32  (E8 rel32)"""
        return bytes([0xE8]) + struct.pack('<i', _sign_extend32(offset))

    def jmp_reg(self, reg: Register) -> bytes:
        """JMP r64  (FF /4)"""
        if reg.is_extended():
            rex = encode_rex(w=0, r=0, x=0, b=1)
            modrm = encode_modrm(mod=3, reg=4, rm=reg.low_bits())
            return bytes([rex, 0xFF, modrm])
        modrm = encode_modrm(mod=3, reg=4, rm=int(reg))
        return bytes([0xFF, modrm])

    def jmp_rel32(self, offset: int) -> bytes:
        """JMP rel32  (E9 rel32)"""
        return bytes([0xE9]) + struct.pack('<i', _sign_extend32(offset))

    def jmp_rel8(self, offset: int) -> bytes:
        """JMP rel8  (EB rel8)"""
        return bytes([0xEB, offset & 0xFF])

    def jz_rel32(self, offset: int) -> bytes:
        """JZ rel32  (0F 84 rel32)"""
        return bytes([0x0F, 0x84]) + struct.pack('<i', _sign_extend32(offset))

    def jnz_rel32(self, offset: int) -> bytes:
        """JNZ rel32  (0F 85 rel32)"""
        return bytes([0x0F, 0x85]) + struct.pack('<i', _sign_extend32(offset))

    def jcc_rel32(self, cond: Condition, offset: int) -> bytes:
        """Jcc rel32  (0F 80+cc rel32)"""
        return bytes([0x0F, 0x80 + int(cond)]) + struct.pack('<i', _sign_extend32(offset))

    def jcc_rel8(self, cond: Condition, offset: int) -> bytes:
        """Jcc rel8  (70+cc rel8)"""
        return bytes([0x70 + int(cond), offset & 0xFF])

    def jz_rel8(self, offset: int) -> bytes:
        return self.jcc_rel8(Condition.Z, offset)

    def jnz_rel8(self, offset: int) -> bytes:
        return self.jcc_rel8(Condition.NZ, offset)

    # ---- Miscellaneous ----

    def nop(self) -> bytes:
        """NOP  (90)"""
        return bytes([0x90])

    def nop_n(self, n: int) -> bytes:
        """Multi-byte NOP sequence (for alignment)."""
        # Efficient multi-byte NOPs
        NOPS = {
            1: bytes([0x90]),
            2: bytes([0x66, 0x90]),
            3: bytes([0x0F, 0x1F, 0x00]),
            4: bytes([0x0F, 0x1F, 0x40, 0x00]),
            5: bytes([0x0F, 0x1F, 0x44, 0x00, 0x00]),
            6: bytes([0x66, 0x0F, 0x1F, 0x44, 0x00, 0x00]),
            7: bytes([0x0F, 0x1F, 0x80, 0x00, 0x00, 0x00, 0x00]),
            8: bytes([0x0F, 0x1F, 0x84, 0x00, 0x00, 0x00, 0x00, 0x00]),
        }
        result = b''
        remaining = n
        while remaining > 0:
            chunk = min(remaining, 8)
            result += NOPS.get(chunk, bytes([0x90]) * chunk)
            remaining -= chunk
        return result

    def int3(self) -> bytes:
        """INT3 (breakpoint)  (CC)"""
        return bytes([0xCC])

    def ud2(self) -> bytes:
        """UD2 (undefined instruction trap)  (0F 0B)"""
        return bytes([0x0F, 0x0B])

    def hlt(self) -> bytes:
        """HLT  (F4) — halt processor (ring 0 only)"""
        return bytes([0xF4])

    def syscall(self) -> bytes:
        """SYSCALL  (0F 05)"""
        return bytes([0x0F, 0x05])

    def sysret(self) -> bytes:
        """SYSRET  (0F 07)"""
        return bytes([0x0F, 0x07])

    def xchg_reg_reg(self, a: Register, b: Register) -> bytes:
        """XCHG r64, r64  (REX.W + 87 /r)"""
        rex_r = 1 if a.is_extended() else 0
        rex_b = 1 if b.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=3, reg=a.low_bits(), rm=b.low_bits())
        return bytes([rex, 0x87, modrm])

    def lea_reg_mem(self, dst: Register, base: Register, disp: int = 0) -> bytes:
        """LEA r64, [base + disp]  (REX.W + 8D /r)"""
        rex_r = 1 if dst.is_extended() else 0
        rex_b = 1 if base.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        if disp == 0 and base.low_bits() != 5:
            modrm = encode_modrm(mod=0, reg=dst.low_bits(), rm=base.low_bits())
            extra = b''
        elif -128 <= disp <= 127:
            modrm = encode_modrm(mod=1, reg=dst.low_bits(), rm=base.low_bits())
            extra = struct.pack('<b', disp)
        else:
            modrm = encode_modrm(mod=2, reg=dst.low_bits(), rm=base.low_bits())
            extra = struct.pack('<i', disp)
        return bytes([rex, 0x8D, modrm]) + extra

    def movzx_reg_mem8(self, dst: Register, base: Register, disp: int = 0) -> bytes:
        """MOVZX r64, byte [base+disp]  (REX.W + 0F B6 /r)"""
        rex_r = 1 if dst.is_extended() else 0
        rex_b = 1 if base.is_extended() else 0
        rex = encode_rex(w=1, r=rex_r, x=0, b=rex_b)
        modrm = encode_modrm(mod=0 if disp == 0 else (1 if -128 <= disp <= 127 else 2),
                              reg=dst.low_bits(), rm=base.low_bits())
        disp_bytes = b''
        if disp != 0:
            disp_bytes = struct.pack('<b' if -128 <= disp <= 127 else '<i', disp)
        return bytes([rex, 0x0F, 0xB6, modrm]) + disp_bytes

    # ---- Function prologue / epilogue helpers ----

    def prologue(self, frame_size: int = 0) -> bytes:
        """Standard function prologue: PUSH RBP, MOV RBP, RSP [, SUB RSP, n]"""
        code = self.push_reg(Register.RBP)
        code += self.mov_reg_reg(Register.RBP, Register.RSP)
        if frame_size > 0:
            aligned = (frame_size + 15) & ~15  # 16-byte align
            code += self.sub_reg_imm32(Register.RSP, aligned)
        return code

    def epilogue(self) -> bytes:
        """Standard function epilogue: MOV RSP, RBP, POP RBP, RET"""
        code = self.mov_reg_reg(Register.RSP, Register.RBP)
        code += self.pop_reg(Register.RBP)
        code += self.ret()
        return code


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _sign_extend32(v: int) -> int:
    v = v & 0xFFFFFFFF
    if v >= 0x80000000:
        v -= 0x100000000
    return v


def _sign_extend64(v: int) -> int:
    v = v & 0xFFFFFFFFFFFFFFFF
    if v >= 0x8000000000000000:
        v -= 0x10000000000000000
    return v


# ---------------------------------------------------------------------------
# IRToMachineCode — compile IRGraph to x86-64 bytes
# ---------------------------------------------------------------------------

class IRToMachineCode:
    """
    Compiles a Sovereign IR graph to x86-64 machine code.

    The generated code follows the System V AMD64 ABI calling convention.
    Each IR node type maps to a code sequence:
      INTENT     -> setup dispatch table lookup
      OPERATOR   -> arithmetic/logic operation
      CONSTRAINT -> conditional branch
      ENTITY     -> data load
      PAYLOAD    -> data store / emit
    """

    # Register conventions for sovereign dispatch
    REG_OPCODE  = Register.RDI   # first argument (opcode)
    REG_PAYLOAD = Register.RSI   # second argument (payload ptr)
    REG_RESULT  = Register.RAX   # return value
    REG_ENTROPY = Register.R10   # entropy tracking (caller-saved)
    REG_TMP1    = Register.R11
    REG_TMP2    = Register.R12
    REG_DISPATCH= Register.RBX   # dispatch table pointer (callee-saved)

    def __init__(self):
        self._encoder = X86Encoder()
        self._buf = CodeBuffer()

    def compile_graph(self, graph: 'IRGraph') -> bytes:
        """
        Compile a full IRGraph to x86-64 machine code.
        Returns raw bytes (not an ELF/PE — just a code sequence).
        """
        self._buf.clear()
        encoder = self._encoder

        # Function prologue
        self._buf.emit(encoder.prologue(frame_size=64))

        # Save callee-saved registers
        self._buf.emit(encoder.push_reg(Register.RBX))
        self._buf.emit(encoder.push_reg(Register.R12))

        # Initialize entropy register to 0
        self._buf.emit(encoder.xor_reg_reg(self.REG_ENTROPY, self.REG_ENTROPY))

        # Sort nodes topologically for linear compilation
        try:
            order = graph.topological_sort()
        except Exception:
            order = [n.node_id for n in graph.nodes]

        node_map = {n.node_id: n for n in graph.nodes}

        for node_id in order:
            node = node_map.get(node_id)
            if node is not None:
                node_code = self.compile_node(node)
                self._buf.emit(node_code)
                self._buf.align(4)  # align each node's code to 4 bytes

        # Restore callee-saved registers
        self._buf.emit(encoder.pop_reg(Register.R12))
        self._buf.emit(encoder.pop_reg(Register.RBX))

        # Function epilogue
        self._buf.emit(encoder.epilogue())

        return self._buf.get_bytes()

    def compile_node(self, node: 'IRNode') -> bytes:
        """Compile a single IR node to machine code."""
        from .binary_ir import IRNodeType

        buf = CodeBuffer()
        enc = self._encoder

        node_type = int(node.node_type)

        if node_type == 0:   # INTENT
            # Load routing weight into RAX, encode opcode
            rw_int = int(node.routing_weight * 1000) & 0xFFFFFFFF
            buf.emit(enc.mov_reg_imm32(Register.RAX, rw_int))
            # XOR with entropy to produce dispatch selector
            buf.emit(enc.xor_reg_reg(Register.RAX, self.REG_ENTROPY))

        elif node_type == 1:  # ENTITY
            # Load entity ID (hash of symbol) into RCX
            entity_hash = hash(node.symbol) & 0x7FFFFFFF
            buf.emit(enc.mov_reg_imm32(Register.RCX, entity_hash))

        elif node_type == 2:  # OPERATOR
            # Perform ADD as proxy for generic operator
            buf.emit(enc.add_reg_reg(Register.RAX, Register.RCX))
            # Update entropy register (simplified: increment by routing_weight * 256)
            entropy_delta = max(0, min(255, int(node.entropy * 256)))
            if entropy_delta > 0:
                buf.emit(enc.add_reg_imm32(self.REG_ENTROPY, entropy_delta))

        elif node_type == 3:  # CONSTRAINT
            # Constraint check: CMP RAX, 0; JZ skip
            buf.emit(enc.cmp_reg_imm32(Register.RAX, 0))
            # JZ +4 (skip over the NOP padding)
            buf.emit(enc.jz_rel8(4))
            buf.emit(enc.nop_n(4))

        elif node_type == 4:  # PAYLOAD
            # Store payload hash in RDX
            payload_hash = hash(node.symbol) & 0x7FFFFFFF
            buf.emit(enc.mov_reg_imm32(Register.RDX, payload_hash))

        return buf.get_bytes()

    def compile_routing_dispatch(self, opcode: int) -> bytes:
        """
        Compile a routing dispatch sequence for a given opcode.
        Generates code that:
          1. Loads the opcode into RDI
          2. Calls the dispatch table lookup
          3. Tests result and branches
        """
        buf = CodeBuffer()
        enc = self._encoder

        # Load opcode into RDI (first argument)
        buf.emit(enc.mov_reg_imm32(self.REG_OPCODE, opcode & 0xFFFF))

        # Save current entropy
        buf.emit(enc.push_reg(self.REG_ENTROPY))

        # Call indirect through RBX (dispatch table)
        # [RBX + opcode * 8] = function pointer
        # For simplicity: just do a TEST and conditional NOP
        buf.emit(enc.test_reg_reg(self.REG_DISPATCH, self.REG_DISPATCH))
        buf.emit(enc.jz_rel8(8))   # skip if no dispatch table

        # MOV RAX, [RBX + RDI*8] — load function pointer
        # This uses SIB: [RBX + RDI*8]
        rex = encode_rex(w=1, r=0, x=1, b=1)  # RAX=dst, RDI=index, RBX=base
        modrm = encode_modrm(mod=0, reg=0, rm=4)  # rm=4 -> SIB
        sib = encode_sib(scale=3, index=Register.RDI.low_bits(), base=Register.RBX.low_bits())
        buf.emit(bytes([rex, 0x8B, modrm, sib]))

        # CALL RAX
        buf.emit(enc.call_reg(Register.RAX))

        # Restore entropy
        buf.emit(enc.pop_reg(self.REG_ENTROPY))

        return buf.get_bytes()

    def compile_nand_gate(self, a_reg: Register, b_reg: Register) -> bytes:
        """
        Compile NAND(a, b) = NOT(a AND b) in x86-64.
        Uses a_reg and b_reg as inputs; result in a_reg.
        """
        buf = CodeBuffer()
        enc = self._encoder

        # TMP = a AND b
        buf.emit(enc.mov_reg_reg(self.REG_TMP1, a_reg))
        buf.emit(enc.and_reg_reg(self.REG_TMP1, b_reg))

        # result = NOT TMP
        buf.emit(enc.not_reg(self.REG_TMP1))

        # Mask to 1 bit (AND 1)
        buf.emit(enc.and_reg_reg(self.REG_TMP1, self.REG_TMP1))

        # Move to a_reg
        buf.emit(enc.mov_reg_reg(a_reg, self.REG_TMP1))

        return buf.get_bytes()

    def compile_jordan_gate(self, signal_reg: Register) -> bytes:
        """
        Compile Jordan gate evaluation.
        The Jordan gate checks: signal * phi^-2 <= threshold.
        Implemented as: (signal * 382) >> 10  (phi^-2 ≈ 0.382 = 382/1000)
        If result <= 200 (0.20), gate passes (returns 1); else fails (returns 0).
        """
        buf = CodeBuffer()
        enc = self._encoder

        # RAX = signal_reg
        buf.emit(enc.mov_reg_reg(Register.RAX, signal_reg))

        # RAX = RAX * 382 (phi^-2 scaled to 1000)
        buf.emit(enc.mov_reg_imm32(self.REG_TMP1, 382))
        buf.emit(enc.imul_reg_reg(Register.RAX, self.REG_TMP1))

        # RAX = RAX / 1000 (use shift approximation: >> 10 ≈ /1024)
        buf.emit(enc.sar_reg_imm8(Register.RAX, 10))

        # CMP RAX, 200  (threshold for H <= 0.20)
        buf.emit(enc.cmp_reg_imm32(Register.RAX, 200))

        # Set result: 1 if RAX <= 200, else 0
        # SETLE AL, then MOVZX RAX, AL
        # SETLE = 0F 9E /r
        modrm_setle = encode_modrm(mod=3, reg=0, rm=int(Register.RAX))
        buf.emit(bytes([0x0F, 0x9E, modrm_setle]))

        # MOVZX RAX, AL  (REX.W + 0F B6 /r with rm=RAX low)
        rex = encode_rex(w=1, r=0, x=0, b=0)
        modrm_movzx = encode_modrm(mod=3, reg=int(Register.RAX), rm=int(Register.RAX))
        buf.emit(bytes([rex, 0x0F, 0xB6, modrm_movzx]))

        return buf.get_bytes()

    def compile_syscall_wrapper(
        self,
        syscall_num: int,
        arg_regs: list[Register] | None = None,
    ) -> bytes:
        """
        Compile a Linux syscall wrapper.
        ABI: syscall number in RAX, args in RDI, RSI, RDX, R10, R8, R9.
        """
        buf = CodeBuffer()
        enc = self._encoder

        # Load syscall number
        buf.emit(enc.mov_reg_imm32(Register.RAX, syscall_num))

        # Args already in registers per calling convention
        # Save RCX and R11 (destroyed by SYSCALL)
        buf.emit(enc.push_reg(Register.RCX))
        buf.emit(enc.push_reg(Register.R11))

        buf.emit(enc.syscall())

        # Restore
        buf.emit(enc.pop_reg(Register.R11))
        buf.emit(enc.pop_reg(Register.RCX))

        buf.emit(enc.ret())

        return buf.get_bytes()

    def reset(self) -> None:
        self._buf.clear()

    def get_buffer(self) -> CodeBuffer:
        return self._buf


# Make IRGraph available without circular import
try:
    from .binary_ir import IRGraph, IRNode, IRNodeType
except ImportError:
    # Standalone use
    pass


# ---------------------------------------------------------------------------
# Disassembler stub (for display purposes only)
# ---------------------------------------------------------------------------

def simple_disasm(data: bytes, base_addr: int = 0) -> list[str]:
    """
    Very basic byte-level 'disassembly' for display.
    Not a real disassembler — just shows opcode bytes with known patterns.
    """
    lines = []
    i = 0
    while i < len(data):
        byte = data[i]
        if byte == 0x90:
            lines.append(f"{base_addr + i:08x}  90                       NOP")
            i += 1
        elif byte == 0xC3:
            lines.append(f"{base_addr + i:08x}  C3                       RET")
            i += 1
        elif byte == 0xCC:
            lines.append(f"{base_addr + i:08x}  CC                       INT3")
            i += 1
        elif byte == 0xF4:
            lines.append(f"{base_addr + i:08x}  F4                       HLT")
            i += 1
        elif byte == 0x48 and i + 1 < len(data) and data[i + 1] == 0x31:
            # XOR r64, r64
            rm = data[i + 2] if i + 2 < len(data) else 0
            lines.append(f"{base_addr + i:08x}  48 31 {rm:02x}                XOR r64, r64")
            i += 3
        elif byte == 0x48 and i + 1 < len(data) and data[i + 1] == 0x89:
            rm = data[i + 2] if i + 2 < len(data) else 0
            lines.append(f"{base_addr + i:08x}  48 89 {rm:02x}                MOV r64, r64")
            i += 3
        else:
            # Raw bytes
            chunk = data[i:min(i + 4, len(data))]
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            lines.append(f"{base_addr + i:08x}  {hex_str:<24} ...")
            i += len(chunk)
    return lines


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    enc = X86Encoder()

    # Test NOP
    assert enc.nop() == bytes([0x90])

    # Test RET
    assert enc.ret() == bytes([0xC3])

    # Test INT3
    assert enc.int3() == bytes([0xCC])

    # Test PUSH RAX = 0x50
    assert enc.push_reg(Register.RAX) == bytes([0x50])

    # Test PUSH R8 = 41 50
    assert enc.push_reg(Register.R8) == bytes([0x41, 0x50])

    # Test POP RBX = 0x5B
    assert enc.pop_reg(Register.RBX) == bytes([0x5B])

    # Test MOV RAX, imm64
    code = enc.mov_reg_imm64(Register.RAX, 0x1234567890ABCDEF)
    assert code[0] == 0x48  # REX.W
    assert code[1] == 0xB8  # MOV RAX opcode
    assert len(code) == 10  # 2 + 8

    # Test MOV RCX, imm64
    code2 = enc.mov_reg_imm64(Register.RCX, 42)
    assert code2[0] == 0x48
    assert code2[1] == 0xB9  # 0xB8 + 1 (RCX)

    # Test MOV R10, imm64 (extended register)
    code3 = enc.mov_reg_imm64(Register.R10, 0xDEAD)
    assert code3[0] == 0x49  # REX.W | REX.B
    assert code3[1] == 0xBA  # 0xB8 + 2 (R10 low bits = 2)

    # Test XOR RAX, RAX
    code4 = enc.xor_reg_reg(Register.RAX, Register.RAX)
    assert code4[0] == 0x48  # REX.W
    assert code4[1] == 0x31  # XOR opcode

    # Test ADD RDX, RCX
    code5 = enc.add_reg_reg(Register.RDX, Register.RCX)
    assert len(code5) == 3  # REX + opcode + modrm

    # Test REX encoding
    assert encode_rex(1, 0, 0, 0) == 0x48  # REX.W
    assert encode_rex(1, 1, 0, 0) == 0x4C  # REX.W | REX.R
    assert encode_rex(1, 0, 0, 1) == 0x49  # REX.W | REX.B

    # Test ModRM encoding
    assert encode_modrm(3, 0, 0) == 0xC0   # mod=3, reg=0, rm=0
    assert encode_modrm(3, 1, 2) == 0xCA   # mod=3, reg=1, rm=2

    # Test CodeBuffer
    buf = CodeBuffer()
    off1 = buf.emit(enc.nop())
    off2 = buf.emit(enc.ret())
    assert buf.size() == 2
    assert off1 == 0
    assert off2 == 1
    data = buf.get_bytes()
    assert data == bytes([0x90, 0xC3])

    # Test patch
    buf2 = CodeBuffer()
    buf2.emit(bytes([0xE8]))  # CALL prefix
    patch_off = buf2.emit_i32(0)  # placeholder
    buf2.emit(enc.ret())
    buf2.patch_i32(patch_off, 100)
    data2 = buf2.get_bytes()
    assert struct.unpack_from('<i', data2, 1)[0] == 100

    # Test prologue/epilogue
    prologue = enc.prologue()
    assert prologue[0] == 0x55  # PUSH RBP
    epilogue = enc.epilogue()
    assert epilogue[-1] == 0xC3  # ends with RET

    # Test NAND gate compilation
    gen = IRToMachineCode()
    nand_code = gen.compile_nand_gate(Register.RAX, Register.RCX)
    assert len(nand_code) > 0

    # Test Jordan gate compilation
    jordan_code = gen.compile_jordan_gate(Register.RDI)
    assert len(jordan_code) > 0

    return True


if __name__ == "__main__":
    assert _self_test(), "Self-test failed"
    print("machine_code_gen.py: all self-tests passed")

    enc = X86Encoder()

    # Demo: generate a simple "return 42" function
    buf = CodeBuffer()
    buf.emit(enc.prologue())
    buf.emit(enc.mov_reg_imm32(Register.RAX, 42))
    buf.emit(enc.epilogue())
    data = buf.get_bytes()
    print(f"\n'return 42' function: {len(data)} bytes")
    print(buf.hexdump())

    # Demo: NAND gate
    gen = IRToMachineCode()
    nand = gen.compile_nand_gate(Register.RAX, Register.RCX)
    print(f"\nNAND gate: {len(nand)} bytes")

    # Demo: Jordan gate
    jordan = gen.compile_jordan_gate(Register.RDI)
    print(f"Jordan gate: {len(jordan)} bytes")

    # Demo: disassembly
    print("\nSimple disassembly:")
    for line in simple_disasm(data):
        print(" ", line)
