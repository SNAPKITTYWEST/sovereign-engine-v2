"""
macro_wasm.py — MacroWASM Compiler

Decodes <X opcode_bytes>MACROWASM instructions into their WASM binary
representation and connects them to the full Macro MAGMA stack.

MacroWASM format:
    <X HH HH ...>MACROWASM

Where HH... are WASM binary opcodes (LEB128-encoded immediates).

The bridge instruction Ahmad sent:
    <X 36 02 40 20 00 20 01 6A>MACROWASM

Decodes as:
    0x36        i32.store8       — write one byte to linear memory
    0x02 0x40   align=2, offset=64   — 4-byte aligned, 64 bytes ahead
    0x20 0x00   local.get $addr  — first param (address)
    0x20 0x01   local.get $val   — second param (value)
    0x6A        i32.add          — accumulate addr+val

This is the WASM equivalent of AC VM STORE at addr+64, then ADD.
Maps to: M5.macrowasm_pulse(addr, val) → m5_memory[addr+64] = val; return addr+val.

Full pipeline:
    §MAGMA verb
        ↓  MacroMAGMA compiler  (macro_magma.py)
    ISA-8 opcode sequence
        ↓  CCE decode           (compact_control_engine.v)
    64-bit control word
        ↓  MicroROM CA step     (ca_vm.py)
    LOAD/XOR/STORE triplets
        ↓  CUFF assembly        (narm_kernels_avx512.asm)
    raw_gemm / raw_normalization
        ↓  MacroWASM            (this file)
    <X wasm_binary>MACROWASM
        ↓  M5 module            (m5.wat)
    m5_memory[4096 bytes]
        ↓  Virtual circuit board
    6502/Z80 storage cells
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# WASM opcode table (subset relevant to MacroWASM)
# ---------------------------------------------------------------------------

WASM_OPCODES: dict[int, str] = {
    0x00: "unreachable",
    0x01: "nop",
    0x0F: "return",
    0x20: "local.get",
    0x21: "local.set",
    0x22: "local.tee",
    0x23: "global.get",
    0x24: "global.set",
    0x28: "i32.load",
    0x29: "i64.load",
    0x2C: "i32.load8_s",
    0x2D: "i32.load8_u",
    0x36: "i32.store8",
    0x37: "i32.store16",
    0x38: "i64.store",
    0x41: "i32.const",
    0x42: "i64.const",
    0x45: "i32.eqz",
    0x46: "i32.eq",
    0x47: "i32.ne",
    0x4A: "i32.lt_u",
    0x4D: "i32.gt_u",
    0x50: "i32.ge_u",
    0x67: "i32.clz",
    0x68: "i32.ctz",
    0x69: "i32.popcnt",
    0x6A: "i32.add",
    0x6B: "i32.sub",
    0x6C: "i32.mul",
    0x6E: "i32.div_u",
    0x71: "i32.and",
    0x72: "i32.or",
    0x73: "i32.xor",
    0x74: "i32.shl",
    0x75: "i32.shr_s",
    0x76: "i32.shr_u",
    0x7C: "i64.add",
    0x7D: "i64.sub",
    0x7E: "i64.mul",
    0xAC: "i32.wrap_i64",
    0xAD: "i32.trunc_f32_s",
}

# Memory instruction immediates: (align_bytes, offset_bytes)
MEM_INSTRUCTIONS = {0x28, 0x29, 0x2C, 0x2D, 0x36, 0x37, 0x38}

# Variable instructions: (index_bytes)
VAR_INSTRUCTIONS = {0x20, 0x21, 0x22, 0x23, 0x24}


# ---------------------------------------------------------------------------
# Decoded instruction
# ---------------------------------------------------------------------------

@dataclass
class WasmInstr:
    opcode:   int
    mnemonic: str
    operands: list[int]   # decoded immediates

    def __str__(self) -> str:
        ops = "  ".join(f"0x{o:02X}" for o in self.operands) if self.operands else ""
        return f"{self.mnemonic:<20}  {ops}"

    def to_wat(self) -> str:
        """Render as WAT S-expression."""
        if self.opcode in MEM_INSTRUCTIONS:
            align, offset = self.operands[0], self.operands[1]
            return f"({self.mnemonic} align={align} offset={offset})"
        elif self.opcode in VAR_INSTRUCTIONS:
            return f"({self.mnemonic} {self.operands[0]})"
        else:
            return f"({self.mnemonic})"


# ---------------------------------------------------------------------------
# MacroWASM parser
# ---------------------------------------------------------------------------

MACROWASM_RE = re.compile(r"<X\s+((?:[0-9A-Fa-f]{2}\s*)+)>MACROWASM")


def parse_macrowasm(text: str) -> list[list[int]]:
    """Extract byte sequences from all <X ...>MACROWASM tokens in text."""
    results = []
    for m in MACROWASM_RE.finditer(text):
        hexstr = m.group(1).strip()
        bytelist = [int(b, 16) for b in hexstr.split()]
        results.append(bytelist)
    return results


def decode_leb128(data: list[int], pos: int) -> tuple[int, int]:
    """Decode unsigned LEB128. Returns (value, new_pos)."""
    result, shift = 0, 0
    while True:
        byte = data[pos]; pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7


def disassemble_macrowasm(bytes_: list[int]) -> list[WasmInstr]:
    """Disassemble a raw byte sequence into WasmInstr objects."""
    instrs: list[WasmInstr] = []
    pos = 0
    while pos < len(bytes_):
        opcode = bytes_[pos]; pos += 1
        mnemonic = WASM_OPCODES.get(opcode, f"unknown_0x{opcode:02X}")
        operands: list[int] = []

        if opcode in MEM_INSTRUCTIONS:
            # align + offset (two LEB128 values)
            align,  pos = decode_leb128(bytes_, pos)
            offset, pos = decode_leb128(bytes_, pos)
            operands = [align, offset]
        elif opcode in VAR_INSTRUCTIONS:
            idx, pos = decode_leb128(bytes_, pos)
            operands = [idx]
        elif opcode in (0x41, 0x42):   # i32/i64.const
            val, pos = decode_leb128(bytes_, pos)
            operands = [val]

        instrs.append(WasmInstr(opcode=opcode, mnemonic=mnemonic, operands=operands))
    return instrs


# ---------------------------------------------------------------------------
# MacroWASM → MAGMA verb mapping
# ---------------------------------------------------------------------------

# WASM opcode pattern → MAGMA verb + M5 function
WASM_TO_MAGMA: dict[tuple[int, ...], tuple[str, str]] = {
    (0x36,): ("ANCHOR", "write_byte"),          # i32.store8 → ANCHOR/WORM
    (0x6A,): ("FLUX",   "macrowasm_pulse"),      # i32.add    → FLUX/accumulate
    (0x36, 0x6A): ("PULSE", "macrowasm_pulse"),  # store+add  → PULSE (Ahmad's pattern)
    (0x73,): ("SEAL",   "xor_and_seal"),         # i32.xor    → SEAL (= M.Imaginary)
    (0x71,): ("BIND",   "and_bind"),             # i32.and    → BIND
    (0x72,): ("ECHO",   "or_broadcast"),         # i32.or     → ECHO
    (0x2D,): ("QUERY",  "read_byte"),            # i32.load8  → QUERY
}

def macrowasm_to_magma(bytes_: list[int]) -> list[tuple[str, str]]:
    """Map a MacroWASM byte sequence to MAGMA (verb, m5_function) pairs."""
    instrs = disassemble_macrowasm(bytes_)
    results = []
    opcodes = tuple(i.opcode for i in instrs)
    # Try longest match first
    for n in range(len(opcodes), 0, -1):
        key = opcodes[:n]
        if key in WASM_TO_MAGMA:
            results.append(WASM_TO_MAGMA[key])
            break
    if not results:
        results.append(("INVOKE", "raw_exec"))
    return results


# ---------------------------------------------------------------------------
# Full pipeline integration
# ---------------------------------------------------------------------------

def render_macrowasm(raw: str) -> str:
    """
    Decode all <X ...>MACROWASM tokens and show the full pipeline:
      MacroWASM bytes → WASM disassembly → WAT → MAGMA verb → M5 function
    """
    sequences = parse_macrowasm(raw)
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  MacroWASM Decoder                                       ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
    ]

    for idx, seq in enumerate(sequences):
        lines.append(f"  Sequence {idx}: {' '.join(f'{b:02X}' for b in seq)}")
        lines.append("")

        instrs = disassemble_macrowasm(seq)
        lines.append("  WASM binary → disassembly:")
        for instr in instrs:
            lines.append(f"    {instr}")

        lines.append("")
        lines.append("  WAT S-expressions:")
        for instr in instrs:
            lines.append(f"    {instr.to_wat()}")

        lines.append("")
        magma_ops = macrowasm_to_magma(seq)
        lines.append("  → MAGMA mapping:")
        for verb, fn in magma_ops:
            lines.append(f"    §{verb}:M5:{fn}  →  m5.wat export \"{fn}\"")

        lines.append("")
        lines.append("  → AC VM equivalent:")
        for instr in instrs:
            ac_equiv = {
                0x36: "STORE addr    (Mem[addr] ← AC)",
                0x6A: "ADD   addr    (AC ← AC + Mem[addr])",
                0x73: "XOR   addr    (AC ← AC ⊕ Mem[addr])  = M.Imaginary",
                0x20: "LOAD  local   (operand fetch)",
                0x2D: "LOAD  addr    (AC ← Mem[addr])",
            }.get(instr.opcode, f"NOP  (0x{instr.opcode:02X})")
            lines.append(f"    {ac_equiv}")

        lines.append("")

    lines += [
        "═" * 60,
        "  Full compilation stack:",
        "  §MAGMA → ISA-8 → CCE → MicroROM → CUFF → MacroWASM → M5",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The bridge instruction from Ahmad
# ---------------------------------------------------------------------------

AHMAD_MACROWASM = "<X 36 02 40 20 00 20 01 6A>MACROWASM"


if __name__ == "__main__":
    import sys, io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print(render_macrowasm(AHMAD_MACROWASM))
    print()

    # Show the connection to the full pipeline
    print("MacroWASM instruction → complete execution chain:")
    print()
    print("  <X 36 02 40 20 00 20 01 6A>MACROWASM")
    print()
    print("  Layer 7 → M5 WASM: m5_memory[addr+64] = val; return addr+val")
    print("  Layer 6 → CUFF:    raw_normalization (ALU=0x3F from 0x36 store)")
    print("  Layer 5 → MicroROM: LOAD_CELL(0) XOR_UPDATE(0x36) STORE_CELL(0)")
    print("  Layer 4 → ISA-8:   0x36→STORE + 0x6A→ADD  (≈ 0x07 XOR + 0x03 ADD)")
    print("  Layer 3 → CCE:     0x8F ZK_PROOF_TICK → 0xFFFF_0000_AAAA_BBBB")
    print("  Layer 2 → MAGMA:   §PULSE:M5:macrowasm_pulse")
    print("  Layer 1 → Springboard: launched via §PULSE:FLUX:BOARD_PROBE")
