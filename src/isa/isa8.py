"""
isa8.py — 8-bit Sovereign ISA Virtual Machine

Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust

Instruction format (single-byte OR two-byte):
  Full-byte opcode + separate operand byte (CODE BYTES 30 = 15 × 2)

  Alternatively packed as single byte: bits[7:4]=opcode, bits[3:0]=operand

Opcodes:
  0x00  HALT    stop execution
  0x01  SET     register ← operand
  0x02  CLEAR   register ← 0
  0x03  TOGGLE  register ← ~register & 0xF (lower nibble)
  0x04  ROUTE   redirect execution to address operand
  0x05  READ    read from memory[operand] → register
  0x06  WRITE   write register → memory[operand]
  0x07  XOR     register ← register XOR operand
  0x08  AND     register ← register AND operand
  0x09  OR      register ← register OR operand
  0x0A  SHIFT   register ← register << (operand & 0x07)
  0x0B  BRANCH  PC ← operand (unconditional jump)
  0x0C  LOAD    register ← memory[operand]
  0x0D  STORE   memory[operand] ← register
  0xFF  SENTINEL end of ROM marker

Constraints:
  CODE BYTES:     30 (15 instructions × 2 bytes)
  RAM BYTES:      64
  REGISTER BITS:  32
  INSTRUCTION WIDTH: 8 (opcode nibble) + 8 (operand) = 16 bits per instruction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Opcode table
# ---------------------------------------------------------------------------

OPCODES = {
    0x00: "HALT",   0x01: "SET",    0x02: "CLEAR",  0x03: "TOGGLE",
    0x04: "ROUTE",  0x05: "READ",   0x06: "WRITE",  0x07: "XOR",
    0x08: "AND",    0x09: "OR",     0x0A: "SHIFT",  0x0B: "BRANCH",
    0x0C: "LOAD",   0x0D: "STORE",  0xFF: "SENTINEL",
}

# Reference binary program from Ahmad
REFERENCE_PROGRAM_BINARY = [
    (0x01, 0x00), (0x02, 0x00), (0x03, 0x01), (0x04, 0x12),
    (0x05, 0x00), (0x06, 0x01), (0x07, 0x23), (0x08, 0x45),
    (0x09, 0x67), (0x0A, 0x01), (0x0B, 0x05), (0x0C, 0x00),
    (0x0D, 0x00), (0x00, 0x00), (0xFF, 0xFF),
]


# ---------------------------------------------------------------------------
# Program representation
# ---------------------------------------------------------------------------

@dataclass
class ISA8Instruction:
    pc:      int
    opcode:  int
    operand: int

    @property
    def mnemonic(self) -> str:
        return OPCODES.get(self.opcode, f"UNK_{self.opcode:02X}")

    def __str__(self) -> str:
        return f"[0x{self.pc:02X}]  {self.mnemonic:<8}  0x{self.operand:02X}"


class ISA8Program:
    def __init__(self, instructions: list[tuple[int, int]]) -> None:
        self.instructions = [
            ISA8Instruction(pc=i * 2, opcode=op, operand=operand)
            for i, (op, operand) in enumerate(instructions)
        ]
        self.bytes = len(instructions) * 2

    @classmethod
    def from_reference(cls) -> "ISA8Program":
        return cls(REFERENCE_PROGRAM_BINARY)

    def __repr__(self) -> str:
        return f"ISA8Program({self.bytes} bytes, {len(self.instructions)} instructions)"


def disassemble8(instructions: list[tuple[int, int]] | None = None) -> str:
    prog = ISA8Program(instructions or REFERENCE_PROGRAM_BINARY)
    lines = [
        f"ISA-8 DISASSEMBLY  ({prog.bytes} code bytes, 64 RAM bytes, 32-bit register)",
        "─" * 50,
        f"  {'PC':>4}  {'OP':>4}  {'MNEM':<8}  {'ARG':>4}",
        "─" * 50,
    ]
    for ins in prog.instructions:
        lines.append(f"  0x{ins.pc:02X}  0x{ins.opcode:02X}  {ins.mnemonic:<8}  0x{ins.operand:02X}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# VM
# ---------------------------------------------------------------------------

@dataclass
class ISA8State:
    register: int           = 0        # 32-bit accumulator
    pc:       int           = 0        # program counter (byte address)
    ram:      list[int]     = field(default_factory=lambda: [0] * 64)
    halted:   bool          = False
    steps:    int           = 0
    trace:    list[str]     = field(default_factory=list)


class ISA8VM:
    """Executes ISA-8 bytecode (2-byte instruction pairs)."""

    def __init__(self, program: ISA8Program | None = None) -> None:
        self.prog  = program or ISA8Program.from_reference()
        self.state = ISA8State()

    def reset(self) -> None:
        self.state = ISA8State()

    def _instr(self) -> Optional[ISA8Instruction]:
        idx = self.state.pc // 2
        if idx < len(self.prog.instructions):
            return self.prog.instructions[idx]
        return None

    def step(self) -> bool:
        if self.state.halted:
            return False
        ins = self._instr()
        if ins is None or ins.opcode == 0xFF:
            self.state.halted = True
            return False

        s   = self.state
        op  = ins.opcode
        arg = ins.operand
        reg = s.register

        if   op == 0x00: s.halted   = True                                # HALT
        elif op == 0x01: s.register = arg                                  # SET
        elif op == 0x02: s.register = 0                                    # CLEAR
        elif op == 0x03: s.register = (~s.register) & 0xFFFFFFFF          # TOGGLE
        elif op == 0x04: s.pc = arg * 2; s.steps += 1; return True        # ROUTE
        elif op == 0x05: s.register = s.ram[arg % 64]                     # READ
        elif op == 0x06: s.ram[arg % 64] = s.register & 0xFF              # WRITE
        elif op == 0x07: s.register = s.register ^ arg                    # XOR
        elif op == 0x08: s.register = s.register & arg                    # AND
        elif op == 0x09: s.register = s.register | arg                    # OR
        elif op == 0x0A: s.register = (s.register << (arg & 7)) & 0xFFFFFFFF  # SHIFT
        elif op == 0x0B: s.pc = arg * 2; s.steps += 1; return True        # BRANCH
        elif op == 0x0C: s.register = s.ram[arg % 64]                     # LOAD
        elif op == 0x0D: s.ram[arg % 64] = s.register & 0xFF              # STORE

        s.trace.append(f"{ins}  reg=0x{s.register:08X}")
        s.pc    += 2
        s.steps += 1
        return not s.halted

    def run(self, max_steps: int = 1000) -> ISA8State:
        while self.state.steps < max_steps:
            if not self.step():
                break
        return self.state

    def run_summary(self) -> str:
        s = self.run()
        lines = [
            "ISA-8 EXECUTION TRACE",
            "─" * 50,
        ]
        for line in s.trace:
            lines.append(f"  {line}")
        lines += [
            "─" * 50,
            f"  Final register : 0x{s.register:08X}",
            f"  RAM[0:8]       : {[hex(b) for b in s.ram[:8]]}",
            f"  Steps          : {s.steps}",
            f"  Halted         : {s.halted}",
        ]
        return "\n".join(lines)
