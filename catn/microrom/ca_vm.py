"""
ca_vm.py — Boolean Cellular Automaton VM

Executes the MicroROM bytecode from BINARY MICROROM.txt.

ISA (32-bit words, big-endian):
  Byte [31:24]  opcode
  Byte [23:16]  field A  (rule index / mask high)
  Bytes[15:0]   field B  (node address / immediate)

Opcodes:
  0x1c  LOAD_CELL    reg ← state[node]
  0x1e  XOR_UPDATE   acc ← acc XOR rule(reg)
  0x0b  STORE_CELL   state[node] ← acc
  0x09  INIT_STATE   state ← all-zeros
  0x0a  SET_RULE     rule_id ← field_A
  0x80  CTRL         pipeline/section boundary
  0x00  NOP

The MICROROM encodes a Boolean CA step loop:
  XOR_UPDATE | STORE_CELL | LOAD_CELL  ×N steps

The included microrom.hex is a 2-node test program (2962 steps):
  state[0] = XOR(state[1])   (toggle node 0 based on node 1 each step)

Source: BINARY MICROROM.txt / BINARY VERI.txt — bob's control repo
Companion build system: veri_stack.txt (Makefile, CUDA, AVX2, P4, x86 stubs)
"""

from __future__ import annotations

import sys, io
from pathlib import Path
from dataclasses import dataclass, field

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


# ---------------------------------------------------------------------------
# Instruction
# ---------------------------------------------------------------------------

@dataclass
class Instruction:
    op:    int    # upper byte
    fa:    int    # byte [23:16] — field A
    fb:    int    # bytes [15:0] — field B

    @classmethod
    def from_word(cls, word: int) -> "Instruction":
        op = (word >> 24) & 0xFF
        fa = (word >> 16) & 0xFF
        fb =  word        & 0xFFFF
        return cls(op=op, fa=fa, fb=fb)

    def __str__(self) -> str:
        names = {0x1c:"LOAD_CELL", 0x1e:"XOR_UPDATE", 0x0b:"STORE_CELL",
                 0x09:"INIT_STATE", 0x0a:"SET_RULE", 0x80:"CTRL", 0x00:"NOP"}
        n = names.get(self.op, f"UNK_{self.op:02x}")
        return f"{n:15s}  fa=0x{self.fa:02x}  fb=0x{self.fb:04x}"


# ---------------------------------------------------------------------------
# VM state
# ---------------------------------------------------------------------------

@dataclass
class CAVMState:
    nodes:    list[int]       = field(default_factory=lambda: [0]*256)
    acc:      int             = 0
    rule_id:  int             = 0
    pc:       int             = 0
    steps:    int             = 0
    history:  list[list[int]] = field(default_factory=list)

    def snapshot(self) -> list[int]:
        return list(self.nodes[:8])   # record first 8 nodes


# ---------------------------------------------------------------------------
# VM executor
# ---------------------------------------------------------------------------

def xor_rule(acc: int, node_val: int, rule_id: int) -> int:
    """
    Boolean rule application.
    Rule 0x10 = XOR (bitwise — single-bit nodes).
    Production: use Wolfram rule table for complex CA rules.
    """
    if rule_id == 0x10:
        return acc ^ node_val
    # Default: XNOR (complement XOR)
    return 1 - (acc ^ node_val) if node_val in (0, 1) else acc ^ node_val


class CAVM:
    """
    Boolean Cellular Automaton Virtual Machine.
    Executes 32-bit MicroROM instructions.
    """

    def __init__(self, rom_path: str) -> None:
        lines = Path(rom_path).read_text().splitlines()
        self.rom = [
            Instruction.from_word(int(l.strip(), 16))
            for l in lines if l.strip()
        ]
        self.state = CAVMState()

    def reset(self) -> None:
        self.state = CAVMState()

    def step(self) -> bool:
        """Execute one instruction. Returns False when HALT or end of ROM."""
        if self.state.pc >= len(self.rom):
            return False

        instr = self.rom[self.state.pc]
        s = self.state

        if instr.op == 0x1c:    # LOAD_CELL
            node_idx = instr.fb & 0xFF
            s.acc = s.nodes[node_idx] if node_idx < len(s.nodes) else 0

        elif instr.op == 0x1e:  # XOR_UPDATE
            s.acc = xor_rule(s.acc, s.acc, instr.fa)

        elif instr.op == 0x0b:  # STORE_CELL
            node_idx = instr.fb & 0xFF
            if node_idx < len(s.nodes):
                s.nodes[node_idx] = s.acc & 1

        elif instr.op == 0x09:  # INIT_STATE
            s.nodes = [0] * 256

        elif instr.op == 0x0a:  # SET_RULE
            s.rule_id = instr.fa

        elif instr.op == 0x80:  # CTRL — no-op at VM level
            pass

        elif instr.op == 0x00:  # NOP
            pass

        s.pc    += 1
        s.steps += 1
        return True

    def run(self, max_steps: int = 100_000, record_every: int = 100) -> CAVMState:
        """Run the VM, recording state snapshots."""
        while self.state.steps < max_steps:
            if self.state.steps % record_every == 0:
                self.state.history.append(self.state.snapshot())
            if not self.step():
                break
        return self.state

    def run_summary(self, max_steps: int = 10_000) -> None:
        state = self.run(max_steps, record_every=500)
        print(f"=== CAVM Execution Summary ===")
        print(f"ROM size    : {len(self.rom)} instructions")
        print(f"Steps run   : {state.steps}")
        print(f"Final PC    : {state.pc}")
        print(f"Final acc   : {state.acc}")
        print(f"Node[0:8]   : {state.nodes[:8]}")
        print()
        print("State snapshots (nodes[0:8]) every 500 steps:")
        for i, snap in enumerate(state.history[:12]):
            print(f"  step {i*500:>6} : {snap}")


# ---------------------------------------------------------------------------
# Bytecode generator (mirrors vm_bytecode_gen.c logic)
# ---------------------------------------------------------------------------

def generate_ca_bytecode(
    n_nodes:    int = 256,
    n_steps:    int = 10,
    rule_id:    int = 0x10,
) -> list[int]:
    """
    Generate MicroROM bytecode for an N-node CA, T steps, given rule.
    Mirrors the logic of vm_bytecode_gen.c.

    For each step t:
      For each node k:
        LOAD_CELL k
        XOR_UPDATE rule_id
        STORE_CELL k
    """
    words: list[int] = []

    def w(op, fa=0, fb=0) -> int:
        return (op << 24) | (fa << 16) | (fb & 0xFFFF)

    # Header: init state + set rule
    words.append(w(0x1c, 0, 0))       # LOAD_CELL 0
    words.append(w(0x09, 0, 0))       # INIT_STATE
    words.append(w(0x0a, rule_id, 0)) # SET_RULE

    # Body: n_steps generations over n_nodes
    for _ in range(n_steps):
        for k in range(n_nodes):
            words.append(w(0x1c, 0, k))       # LOAD_CELL k
            words.append(w(0x1e, rule_id, 0)) # XOR_UPDATE
            words.append(w(0x0b, 0, k))       # STORE_CELL k

    return words


def export_bytecode(words: list[int], out_path: str) -> None:
    lines = [f"{w:08x}" for w in words]
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(words)} words to {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    here = Path(__file__).parent

    # Run the existing MICROROM
    vm = CAVM(str(here / "microrom.hex"))
    vm.run_summary(max_steps=5000)

    # Generate a proper 256-node, 10-step program and save it
    print()
    words_256 = generate_ca_bytecode(n_nodes=256, n_steps=10, rule_id=0x10)
    out = here / "ca_256node_10step.hex"
    export_bytecode(words_256, str(out))

    # Run the generated program
    print()
    vm2 = CAVM(str(out))
    vm2.state.nodes[0] = 1   # seed: node 0 = 1
    vm2.run_summary(max_steps=20_000)
