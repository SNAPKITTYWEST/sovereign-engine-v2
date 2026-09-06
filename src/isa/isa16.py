"""
isa16.py — 16-bit Sovereign ISA Virtual Machine

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Instruction format (16-bit, BIG-ENDIAN):
  15─12: OPCODE  (4 bits)
  11─10: MODE    (2 bits)
   9─ 8: REG     (2 bits)
   7─ 0: OPERAND (8 bits)

  WORD = (HIGH_BYTE << 8) | LOW_BYTE
  MEM[addr]   = HIGH_BYTE
  MEM[addr+1] = LOW_BYTE
  PC steps by +2 each instruction

Modes:
  00  REG/REG      — register ↔ register
  01  IMMEDIATE    — literal value in operand field
  10  DIRECT       — operand is memory address
  11  INDIRECT / PLUGBOARD — operand is pointer

Opcodes:
  0000 HALT       stop
  0001 SET        Rx ← operand (mode-dependent)
  0010 CLEAR      Rx ← 0
  0011 TOGGLE     Rx ← ~Rx
  0100 ROUTE      jump to operand address
  0101 READ       Rx ← port[operand]
  0110 WRITE      port[operand] ← Rx
  0111 XOR        Rx ← Rx XOR operand
  1000 AND        Rx ← Rx AND operand
  1001 OR         Rx ← Rx OR operand
  1010 SHIFT      Rx ← Rx << (operand & 0x1F)
  1011 BRANCH     PC ← operand (unconditional)
  1100 BRANCH-NZ  if Rx ≠ 0: PC ← operand
  1101-1111  RESERVED

Constraints:
  CODE BYTES:       22  (11 instructions × 2 bytes)
  RAM BYTES:        256
  REGISTER BITS:    32
  REGISTERS:        4  (R0–R3)
  INSTRUCTION WIDTH: 16 bits
  ENDIANNESS:       BIG-ENDIAN (HIGH BYTE first)

Reference program (Ahmad):
  14 10 → SET  IMM  R0  0x10
  15 00 → SET  IMM  R1  0x00
  16 05 → SET  IMM  R2  0x05
  5F 00 → READ IND  R3  0x00
  71 03 → XOR  IMM  R0  0x03
  6D 00 → WRITE DIR R1  0x00
  30 00 → TOGGLE REG R0  0x00
  76 01 → XOR  IMM  R1  0x01
  C6 06 → BRANCH-NZ DIR R2  0x06
  4F 40 → ROUTE IND R3  0x40
  00 00 → HALT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Decode tables
# ---------------------------------------------------------------------------

OPCODES16 = {
    0x0: "HALT",     0x1: "SET",     0x2: "CLEAR",   0x3: "TOGGLE",
    0x4: "ROUTE",    0x5: "READ",    0x6: "WRITE",   0x7: "XOR",
    0x8: "AND",      0x9: "OR",      0xA: "SHIFT",   0xB: "BRANCH",
    0xC: "BRANCH-NZ",0xD: "RSVD-D", 0xE: "RSVD-E",  0xF: "RSVD-F",
}

MODES = {0: "R/R", 1: "IMM", 2: "DIR", 3: "IND"}

REFERENCE_PROGRAM_HEX = [
    (0x14, 0x10), (0x15, 0x00), (0x16, 0x05), (0x5F, 0x00),
    (0x71, 0x03), (0x6D, 0x00), (0x30, 0x00), (0x76, 0x01),
    (0xC6, 0x06), (0x4F, 0x40), (0x00, 0x00),
]


# ---------------------------------------------------------------------------
# Instruction decode
# ---------------------------------------------------------------------------

@dataclass
class ISA16Instruction:
    pc:      int
    word:    int     # full 16-bit word
    opcode:  int     # bits 15-12
    mode:    int     # bits 11-10
    reg:     int     # bits 9-8
    operand: int     # bits 7-0

    @classmethod
    def decode(cls, pc: int, hi: int, lo: int) -> "ISA16Instruction":
        word   = (hi << 8) | lo
        opcode = (word >> 12) & 0xF
        mode   = (word >> 10) & 0x3
        reg    = (word >>  8) & 0x3
        operand = word & 0xFF
        return cls(pc=pc, word=word, opcode=opcode, mode=mode,
                   reg=reg, operand=operand)

    @property
    def mnemonic(self) -> str:
        return OPCODES16.get(self.opcode, f"UNK_{self.opcode:X}")

    def __str__(self) -> str:
        mode_s = MODES.get(self.mode, "??")
        return (f"[0x{self.pc:02X}]  {self.mnemonic:<10}  "
                f"{mode_s:<3}  R{self.reg}  0x{self.operand:02X}  "
                f"(word=0x{self.word:04X})")


class ISA16Program:
    def __init__(self, byte_pairs: list[tuple[int, int]]) -> None:
        self.instructions = [
            ISA16Instruction.decode(pc=i * 2, hi=hi, lo=lo)
            for i, (hi, lo) in enumerate(byte_pairs)
        ]
        self.code_bytes = len(byte_pairs) * 2

    @classmethod
    def from_reference(cls) -> "ISA16Program":
        return cls(REFERENCE_PROGRAM_HEX)

    def __repr__(self) -> str:
        return f"ISA16Program({self.code_bytes} code bytes, {len(self.instructions)} instructions)"


def disassemble16(byte_pairs: list[tuple[int, int]] | None = None) -> str:
    prog  = ISA16Program(byte_pairs or REFERENCE_PROGRAM_HEX)
    lines = [
        "ISA-16 DISASSEMBLY  (16-bit big-endian, 4 registers, 256 RAM bytes)",
        "─" * 60,
        f"  {'PC':>4}  {'WORD':>6}  {'MNEM':<10}  {'MODE':<4}  {'REG':>3}  {'OPERAND':>8}",
        "─" * 60,
    ]
    for ins in prog.instructions:
        mode_s = MODES.get(ins.mode, "??")
        lines.append(
            f"  0x{ins.pc:02X}  0x{ins.word:04X}  {ins.mnemonic:<10}  "
            f"{mode_s:<4}  R{ins.reg}  0x{ins.operand:02X}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# VM
# ---------------------------------------------------------------------------

@dataclass
class ISA16State:
    regs:   list[int]  = field(default_factory=lambda: [0, 0, 0, 0])  # R0-R3
    pc:     int        = 0
    ram:    list[int]  = field(default_factory=lambda: [0] * 256)
    ports:  list[int]  = field(default_factory=lambda: [0] * 256)
    halted: bool       = False
    steps:  int        = 0
    trace:  list[str]  = field(default_factory=list)


class ISA16VM:
    """Executes ISA-16 bytecode (big-endian 16-bit instructions)."""

    def __init__(self, program: ISA16Program | None = None) -> None:
        self.prog  = program or ISA16Program.from_reference()
        self.state = ISA16State()

    def reset(self) -> None:
        self.state = ISA16State()

    def _instr(self) -> Optional[ISA16Instruction]:
        idx = self.state.pc // 2
        if idx < len(self.prog.instructions):
            return self.prog.instructions[idx]
        return None

    def _resolve(self, ins: ISA16Instruction) -> int:
        """Resolve operand based on addressing mode."""
        s = self.state
        if ins.mode == 0:    # REG/REG — treat operand as register index
            return s.regs[ins.operand & 0x3]
        elif ins.mode == 1:  # IMMEDIATE
            return ins.operand
        elif ins.mode == 2:  # DIRECT — operand is address
            return s.ram[ins.operand]
        else:                # INDIRECT / PLUGBOARD — operand → address → value
            addr = s.ram[ins.operand]
            return s.ram[addr & 0xFF]

    def step(self) -> bool:
        if self.state.halted:
            return False
        ins = self._instr()
        if ins is None:
            self.state.halted = True
            return False

        s  = self.state
        rx = ins.reg
        v  = self._resolve(ins)

        if   ins.opcode == 0x0:  s.halted = True                               # HALT
        elif ins.opcode == 0x1:  s.regs[rx] = v                                # SET
        elif ins.opcode == 0x2:  s.regs[rx] = 0                                # CLEAR
        elif ins.opcode == 0x3:  s.regs[rx] = (~s.regs[rx]) & 0xFFFFFFFF      # TOGGLE
        elif ins.opcode == 0x4:                                                  # ROUTE
            s.pc = v * 2; s.steps += 1; s.trace.append(str(ins)); return True
        elif ins.opcode == 0x5:  s.regs[rx] = s.ports[ins.operand]             # READ
        elif ins.opcode == 0x6:  s.ports[ins.operand] = s.regs[rx] & 0xFF      # WRITE
        elif ins.opcode == 0x7:  s.regs[rx] ^= v                               # XOR
        elif ins.opcode == 0x8:  s.regs[rx] &= v                               # AND
        elif ins.opcode == 0x9:  s.regs[rx] |= v                               # OR
        elif ins.opcode == 0xA:  s.regs[rx] = (s.regs[rx] << (v & 31)) & 0xFFFFFFFF  # SHIFT
        elif ins.opcode == 0xB:                                                  # BRANCH
            s.pc = v * 2; s.steps += 1; s.trace.append(str(ins)); return True
        elif ins.opcode == 0xC:                                                  # BRANCH-NZ
            if s.regs[rx] != 0:
                s.pc = v * 2; s.steps += 1; s.trace.append(str(ins)); return True

        s.trace.append(f"{ins}  R{rx}=0x{s.regs[rx]:08X}")
        s.pc    += 2
        s.steps += 1
        return not s.halted

    def run(self, max_steps: int = 1000) -> ISA16State:
        while self.state.steps < max_steps:
            if not self.step():
                break
        return self.state

    def run_summary(self) -> str:
        s = self.run()
        lines = ["ISA-16 EXECUTION TRACE", "─" * 60]
        for line in s.trace:
            lines.append(f"  {line}")
        lines += [
            "─" * 60,
            f"  R0=0x{s.regs[0]:08X}  R1=0x{s.regs[1]:08X}  R2=0x{s.regs[2]:08X}  R3=0x{s.regs[3]:08X}",
            f"  Steps : {s.steps}   Halted : {s.halted}",
        ]
        return "\n".join(lines)
