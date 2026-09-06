"""
macro_magma.py — Macro MAGMA Compiler

Connects the MAGMA protocol (§VERB:AGENT:ACTION) to the Binary ISA
and MicroROM to produce a unified Macro MAGMA execution substrate.

Compilation pipeline:
  §MAGMA verb
      ↓  [MacroMAGMA.compile()]
  ISA opcode sequence  (8-bit or 16-bit instruction pairs)
      ↓  [CCE decode: compact_control_engine.v]
  64-bit horizontal control word
      ↓  [MicroROM CA VM: ca_vm.py]
  LOAD_CELL / XOR_UPDATE / STORE_CELL triplets
      ↓  [CUFF assembly: narm_kernels_avx512.asm]
  raw_gemm / raw_normalization / raw_reconstruction_loss
      ↓
  WORM seal / entropy / FSM state

MAGMA verb → ISA opcode mapping:
  SEAL    → [0x8F]                    ZK_PROOF_TICK
  ANCHOR  → [0x0D, 0x06]             STORE + WRITE
  FLUX    → [0x03, 0x04]             TOGGLE + ROUTE (FSM transition)
  FORGE   → [0x01, 0x0C, 0x0D]       SET + LOAD + STORE
  VAULT   → [0x07, 0x06]             XOR + WRITE (encrypted store)
  PULSE   → [0x05]                    READ (probe/heartbeat)
  QUERY   → [0x05, 0x0C]             READ + LOAD
  BIND    → [0x04]                    ROUTE
  NULLIFY → [0x02, 0x00]             CLEAR + HALT
  ECHO    → [0x06]                    WRITE
  INVOKE  → [0x0B]                    BRANCH
  SHADOW  → [0x08, 0x09]             AND + OR (masked)

ISA opcode → CCE 64-bit control word:
  0x8F → 0xFFFF_0000_AAAA_BBBB  (ZK_PROOF_TICK — ZK sustain)
  0x10 → 0xF0A1_B2C3_D4E5_F6A7  (ADD_REG_REG)
  0x25 → 0xA1B2_C3D4_E5F6_A7B8  (LOAD_MEM_Sovereign)
  0x0D → 0x0001_0000_0D00_0001  (STORE)
  0x06 → 0x0001_0000_0600_0001  (WRITE)
  0x07 → 0x0007_0000_0700_0007  (XOR)
  others → synthesized from SovereignSynth

CCE control word → CUFF kernel:
  ALU bits [59:54] map to NARM assembly:
  0x3F → raw_normalization
  0x38 → raw_reconstruction_loss
  0x07 → raw_gemm
  0x01 → raw_residual
  0x00 → raw_buffer_copy

ISA opcode → MicroROM CA operation:
  0x8F → LOAD_CELL + XOR_UPDATE(rule=0x8F) + STORE_CELL  (ZK tick = CA step)
  0x07 → XOR_UPDATE(rule=0x10)                          (toggle = XOR rule)
  0x0D → STORE_CELL node=0                              (persist)
  0x03 → XOR_UPDATE(rule=0x01)                          (toggle)
"""

from __future__ import annotations

import sys
import io
import math
import hashlib
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# MAGMA verb → ISA-8 opcode sequence
# ---------------------------------------------------------------------------

MAGMA_TO_ISA8: dict[str, list[tuple[int, int]]] = {
    # verb    → [(opcode, operand), ...]
    "SEAL":   [(0x8F, 0x00)],
    "ANCHOR": [(0x0D, 0x00), (0x06, 0x01)],
    "FLUX":   [(0x03, 0x01), (0x04, 0x02)],
    "FORGE":  [(0x01, 0x10), (0x0C, 0x00), (0x0D, 0x00)],
    "VAULT":  [(0x07, 0x23), (0x06, 0x01)],
    "PULSE":  [(0x05, 0x00)],
    "QUERY":  [(0x05, 0x00), (0x0C, 0x00)],
    "BIND":   [(0x04, 0x00)],
    "NULLIFY":[(0x02, 0x00), (0x00, 0x00)],
    "ECHO":   [(0x06, 0x01)],
    "INVOKE": [(0x0B, 0x05)],
    "SHADOW": [(0x08, 0x45), (0x09, 0x67)],
}

# MAGMA verb → ISA-16 word sequence (decoded format)
MAGMA_TO_ISA16: dict[str, list[tuple[int, int]]] = {
    # verb    → [(hi_byte, lo_byte), ...]  (16-bit big-endian words)
    "SEAL":   [(0x8F, 0x00)],
    "ANCHOR": [(0x1D, 0x00), (0x16, 0x01)],  # STORE IMM R1 + WRITE IMM R2
    "FLUX":   [(0x30, 0x00), (0x40, 0x02)],  # TOGGLE R0 + ROUTE IMM addr=2
    "FORGE":  [(0x14, 0x10), (0x16, 0x05), (0x76, 0x01)],  # SET R0 0x10, SET R2 0x05, XOR R1 0x01
    "VAULT":  [(0x71, 0x23), (0x6D, 0x00)],  # XOR IMM R0 + WRITE DIR R1
    "PULSE":  [(0x15, 0x00)],
    "QUERY":  [(0x5F, 0x00), (0xC6, 0x00)],  # READ IND R3 + BRANCH-NZ
    "BIND":   [(0x4F, 0x40)],
    "NULLIFY":[(0x30, 0x00), (0x00, 0x00)],
    "ECHO":   [(0x16, 0x01)],
    "INVOKE": [(0xB6, 0x05)],
    "SHADOW": [(0x86, 0x45), (0x96, 0x67)],
}

ISA8_MNEMONICS = {
    0x00:"HALT", 0x01:"SET",  0x02:"CLEAR",  0x03:"TOGGLE",
    0x04:"ROUTE",0x05:"READ", 0x06:"WRITE",  0x07:"XOR",
    0x08:"AND",  0x09:"OR",   0x0A:"SHIFT",  0x0B:"BRANCH",
    0x0C:"LOAD", 0x0D:"STORE",0xFF:"SENTINEL",
}

# ---------------------------------------------------------------------------
# ISA opcode → CCE 64-bit control word
# ---------------------------------------------------------------------------

CCE_TABLE: dict[int, int] = {
    0x8F: 0xFFFF_0000_AAAA_BBBB,  # ZK_PROOF_TICK
    0x10: 0xF0A1_B2C3_D4E5_F6A7,  # ADD_REG_REG
    0x25: 0xA1B2_C3D4_E5F6_A7B8,  # LOAD_MEM_Sovereign
    0x0D: 0x0001_0000_0D00_0001,  # STORE
    0x06: 0x0001_0000_0600_0001,  # WRITE
    0x07: 0x0007_0000_0700_0007,  # XOR
    0x08: 0x0008_0000_0800_0008,  # AND
    0x09: 0x0009_0000_0900_0009,  # OR
    0x03: 0x0003_0000_0300_0003,  # TOGGLE
    0x04: 0x0004_0000_0400_0004,  # ROUTE
    0x05: 0x0005_0000_0500_0005,  # READ
    0x01: 0x0001_0000_0100_0001,  # SET
    0x02: 0x0002_0000_0200_0002,  # CLEAR
    0x0C: 0x000C_0000_0C00_000C,  # LOAD
    0x0B: 0x000B_0000_FFFF_000B,  # BRANCH
    0x00: 0x0000_0000_0001_0000,  # HALT
}

def cce_decode(opcode: int) -> int:
    return CCE_TABLE.get(opcode, 0)

def cce_fields(cw: int) -> dict:
    return {
        "RegRead":  (cw >> 60) & 0xF,
        "ALU_Op":   (cw >> 54) & 0x3F,
        "RegWrite": (cw >> 50) & 0xF,
        "BusRoute": (cw >> 42) & 0xFF,
        "MuxSel":   (cw >> 34) & 0xFF,
        "Misc":     cw & 0x3FFFFFFFF,
    }

# ---------------------------------------------------------------------------
# CCE ALU_Op → CUFF assembly kernel
# ---------------------------------------------------------------------------

CUFF_KERNELS: dict[int, str] = {
    0x3F: "raw_normalization",
    0x38: "raw_reconstruction_loss",
    0x07: "raw_gemm",
    0x01: "raw_residual",
    0x00: "raw_buffer_copy",
    0x08: "raw_activation",
    0x10: "raw_position_encoding",
    0x20: "raw_reconstruction_attention",
}

def alu_to_cuff(alu_op: int) -> str:
    # Match by closest high-bit pattern
    for key in sorted(CUFF_KERNELS.keys(), reverse=True):
        if alu_op & key == key:
            return CUFF_KERNELS[key]
    return "raw_buffer_copy"

# ---------------------------------------------------------------------------
# ISA opcode → MicroROM CA operation
# ---------------------------------------------------------------------------

MICROROM_OPS = {0x1c:"LOAD_CELL", 0x1e:"XOR_UPDATE", 0x0b:"STORE_CELL",
                0x09:"INIT_STATE", 0x0a:"SET_RULE",   0x80:"CTRL"}

ISA8_TO_MICROROM: dict[int, list[tuple[int, int]]] = {
    # opcode → [(microrom_op, arg), ...]
    0x8F: [(0x1c, 0x00), (0x1e, 0x8F), (0x0b, 0x00)],  # ZK tick = full CA step
    0x07: [(0x1e, 0x10)],                               # XOR = XOR_UPDATE rule 0x10
    0x0D: [(0x0b, 0x00)],                               # STORE = STORE_CELL 0
    0x06: [(0x1e, 0x10), (0x0b, 0x00)],                 # WRITE = XOR then STORE
    0x03: [(0x1e, 0x01)],                               # TOGGLE = XOR rule 0x01
    0x04: [(0x09, 0x00)],                               # ROUTE = INIT_STATE
    0x01: [(0x1c, 0x00), (0x0b, 0x00)],                 # SET = LOAD + STORE
    0x0C: [(0x1c, 0x00)],                               # LOAD = LOAD_CELL
    0x05: [(0x1c, 0x01)],                               # READ = LOAD_CELL node 1
    0x00: [(0x80, 0x00)],                               # HALT = CTRL
}

# ---------------------------------------------------------------------------
# Compiled instruction
# ---------------------------------------------------------------------------

@dataclass
class MacroInstruction:
    verb:         str
    agent:        str
    action:       str
    isa8_ops:     list[tuple[int, int]]
    isa16_ops:    list[tuple[int, int]]
    control_words:list[int]
    microrom_ops: list[tuple[int, int]]
    cuff_kernels: list[str]
    worm_hash:    str

    def disassemble(self) -> str:
        lines = [
            f"╔══ §{self.verb}:{self.agent}:{self.action}",
            "│",
            "├─ ISA-8  opcodes:",
        ]
        for op, arg in self.isa8_ops:
            mnem = ISA8_MNEMONICS.get(op, f"UNK_0x{op:02X}")
            lines.append(f"│     0x{op:02X} 0x{arg:02X}  {mnem}  arg={arg}")

        lines.append("│")
        lines.append("├─ ISA-16 words:")
        for hi, lo in self.isa16_ops:
            word = (hi << 8) | lo
            op4  = (word >> 12) & 0xF
            mode = (word >> 10) & 0x3
            reg  = (word >>  8) & 0x3
            imm  = word & 0xFF
            lines.append(f"│     0x{word:04X}  op={op4:X} mode={mode} R{reg} 0x{imm:02X}")

        lines.append("│")
        lines.append("├─ CCE control words (64-bit):")
        seen = set()
        for op, _ in self.isa8_ops:
            if op not in seen:
                seen.add(op)
                cw = cce_decode(op)
                f  = cce_fields(cw)
                lines.append(f"│     0x{op:02X} → 0x{cw:016X}")
                lines.append(f"│          RegRead=0x{f['RegRead']:X}  ALU=0x{f['ALU_Op']:02X}  RegWrite=0x{f['RegWrite']:X}  Bus=0x{f['BusRoute']:02X}")

        lines.append("│")
        lines.append("├─ MicroROM CA ops:")
        for mop, arg in self.microrom_ops:
            name = MICROROM_OPS.get(mop, f"UNK_0x{mop:02x}")
            lines.append(f"│     0x{mop:02x}  {name:<15}  arg=0x{arg:02X}")

        lines.append("│")
        lines.append("├─ CUFF assembly kernels:")
        for k in self.cuff_kernels:
            lines.append(f"│     → {k}")

        lines.append("│")
        lines.append(f"╰─ WORM  {self.worm_hash[:32]}...")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Macro MAGMA compiler
# ---------------------------------------------------------------------------

class MacroMAGMA:
    """
    Compiles MAGMA protocol instructions down to the full execution stack:
      §VERB:AGENT:ACTION → ISA opcodes → CCE control words → MicroROM → CUFF
    """

    def compile(
        self,
        verb:    str,
        agent:   str = "CIPHER",
        action:  str = "DEFAULT",
        payload: dict | None = None,
    ) -> MacroInstruction:
        payload = payload or {}

        # 1. MAGMA verb → ISA opcode sequences
        isa8  = MAGMA_TO_ISA8.get(verb,  [(0x00, 0x00)])
        isa16 = MAGMA_TO_ISA16.get(verb, [(0x00, 0x00)])

        # 2. ISA opcodes → CCE 64-bit control words
        cws = [cce_decode(op) for op, _ in isa8]

        # 3. CCE control words → MicroROM CA ops
        micro_ops: list[tuple[int, int]] = []
        for op, _ in isa8:
            micro_ops.extend(ISA8_TO_MICROROM.get(op, [(0x80, 0x00)]))

        # 4. CCE ALU fields → CUFF kernels
        cuff: list[str] = []
        for cw in cws:
            alu_op = (cw >> 54) & 0x3F
            k = alu_to_cuff(alu_op)
            if k not in cuff:
                cuff.append(k)

        # 5. WORM hash (SHA-256 of the full compiled sequence)
        raw = f"{verb}:{agent}:{action}:{str(isa8)}:{str(cws)}:{str(micro_ops)}"
        worm_hash = hashlib.sha256(raw.encode()).hexdigest()

        return MacroInstruction(
            verb          = verb,
            agent         = agent,
            action        = action,
            isa8_ops      = isa8,
            isa16_ops     = isa16,
            control_words = cws,
            microrom_ops  = micro_ops,
            cuff_kernels  = cuff,
            worm_hash     = worm_hash,
        )

    def compile_pipeline(self, instructions: list[tuple[str, str, str]]) -> list[MacroInstruction]:
        """Compile a full MAGMA pipeline (sequence of §VERB:AGENT:ACTION)."""
        return [self.compile(verb, agent, action) for verb, agent, action in instructions]

    def render_pipeline(self, instructions: list[tuple[str, str, str]]) -> str:
        compiled = self.compile_pipeline(instructions)
        lines = [
            "⟦ Ω ⟧ MACRO MAGMA PIPELINE",
            "═" * 60,
            "",
        ]
        for i, instr in enumerate(compiled):
            lines.append(f"  ── Instruction {i} ──────────────────────────────")
            lines.append(instr.disassemble())
            lines.append("")
        lines += [
            "═" * 60,
            f"  Total instructions : {len(compiled)}",
            f"  Total ISA-8 ops    : {sum(len(i.isa8_ops) for i in compiled)}",
            f"  Total MicroROM ops : {sum(len(i.microrom_ops) for i in compiled)}",
            f"  CUFF kernels used  : {sorted(set(k for i in compiled for k in i.cuff_kernels))}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standard MAGMA pipelines
# ---------------------------------------------------------------------------

# Core persistence pipeline (magma_666.adb Persist path)
CORE_PERSIST_PIPELINE = [
    ("PULSE",   "FLUX",    "PULSE_MATRIX"),
    ("BIND",    "CIPHER",  "LATCH_STATE"),
    ("ANCHOR",  "MNEMEX",  "WORM_PERSIST"),
    ("SEAL",    "CIPHER",  "SIGN"),
]

# ZK verification pipeline (RLBC over RV32IMAC)
ZK_PIPELINE = [
    ("FORGE",   "FORGE",   "ZK_COMMIT"),
    ("SEAL",    "CIPHER",  "ZK_CHALLENGE"),
    ("ANCHOR",  "MNEMEX",  "ZK_RESPONSE"),
]

# Drain pipeline (tensor pruning → WORM seal)
DRAIN_PIPELINE = [
    ("PULSE",   "FLUX",    "DRAIN_INIT"),
    ("FLUX",    "FLUX",    "APPLY_DRAIN"),
    ("SEAL",    "CIPHER",  "DRAIN_PROOF"),
    ("ANCHOR",  "MNEMEX",  "DRAIN_WORM"),
]

# Q-Regex match pipeline
QREGEX_PIPELINE = [
    ("PULSE",   "SENTINEL","QREGEX_PROBE"),
    ("FLUX",    "SENTINEL","RESONANCE_STEP"),
    ("SEAL",    "CIPHER",  "MATCH_SEAL"),
]


if __name__ == "__main__":
    import io as _io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    compiler = MacroMAGMA()

    # Demo: compile the core persistence pipeline
    print(compiler.render_pipeline(CORE_PERSIST_PIPELINE))
    print()

    # Demo: single SEAL instruction full stack
    print("─" * 60)
    print("Single §SEAL:CIPHER:SIGN — full compilation stack:")
    print("─" * 60)
    print(compiler.compile("SEAL", "CIPHER", "SIGN").disassemble())
