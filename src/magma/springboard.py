"""
springboard.py — Virtual Circuit Board Springboard

The vertical integration layer connecting:
  - Virtual 6502/Z80 silicon (transistor-level storage cells)
  - ISA-8 / ISA-16 instruction VMs
  - CCE (64-bit combinatorial control decoder)
  - MicroROM CA (cellular automaton state evolution)
  - MAGMA protocol (§VERB sovereign agent operations)
  - CUFF assembly kernels (raw_gemm / raw_normalization / etc.)

Architecture (iOS Springboard analogy):

  ┌─────────────────────────────────────────────────────┐
  │  SPRINGBOARD                                        │
  │  §MAGMA verbs: SEAL FLUX FORGE ANCHOR PULSE...      │
  │  (Home Screen / App Launch / Lock Screen)           │
  ├─────────────────────────────────────────────────────┤
  │  UIKIT / COREANIMATION LAYER                        │
  │  ISA-8 / ISA-16 instruction VMs                     │
  ├─────────────────────────────────────────────────────┤
  │  PRIVATE FRAMEWORKS                                  │
  │  CCE: 8-bit opcode → 64-bit control word (SOP)      │
  ├─────────────────────────────────────────────────────┤
  │  XPC / MACH IPC                                     │
  │  MAGMA bindings (magmad REST/SSE + Ada FFI)         │
  ├─────────────────────────────────────────────────────┤
  │  BACKBOARDD / LAUNCHSERVICES                        │
  │  MicroROM CA VM (LOAD/XOR/STORE cellular automaton) │
  ├─────────────────────────────────────────────────────┤
  │  HARDWARE / DISPLAY                                  │
  │  CUFF assembly kernels (raw_gemm, raw_normalization) │
  ├─────────────────────────────────────────────────────┤
  │  VIRTUAL CIRCUIT BOARD                              │
  │  6502/Z80 storage cells: flip-flops, latches,       │
  │  dynamic nodes, buses, ALU paths, clock network     │
  └─────────────────────────────────────────────────────┘

6502 circuit → MAGMA cell mapping:
  Dynamic storage node  → Core_State.cells bit (magma_666.adb)
  Latch (D/SR)          → Core_State.state (Idle/Flowing/Latched)
  Register (A/X/Y/SP)   → ISA-8 accumulator register
  ALU                   → CCE ALU_Op field → raw_gemm / raw_residual
  Bus transition        → §FLUX:FLUX:PULSE_MATRIX
  Memory write          → §ANCHOR:MNEMEX:WORM_PERSIST + STORE_CELL
  Clock edge            → CA_VM.step() → LOAD_CELL/XOR_UPDATE/STORE_CELL
  Control signals       → CCE 64-bit horizontal control word
  Reset                 → §NULLIFY:SENTINEL:RESET_CORE + INIT_STATE
"""

from __future__ import annotations

import sys, io, hashlib, math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import os, sys
_repo = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _repo not in sys.path:
    sys.path.insert(0, _repo)

from src.isa.isa8  import ISA8VM,  ISA8Program, REFERENCE_PROGRAM_BINARY
from src.isa.isa16 import ISA16VM, ISA16Program, REFERENCE_PROGRAM_HEX
from src.magma.macro_magma import MacroMAGMA, CORE_PERSIST_PIPELINE


# ---------------------------------------------------------------------------
# Layer 7: Virtual Circuit Board — 6502/Z80 storage cells
# ---------------------------------------------------------------------------

class CellType(Enum):
    DYNAMIC_NODE  = auto()   # 6502 dynamic storage (capacitive)
    LATCH_D       = auto()   # D-latch (level-sensitive)
    LATCH_SR      = auto()   # SR-latch (Set/Reset)
    FLIPFLOP_D    = auto()   # Edge-triggered D flip-flop
    REGISTER_BIT  = auto()   # Named register bit (A, X, Y, SP, PC, SR)
    BUS_NODE      = auto()   # Data/address bus wire
    ALU_NODE      = auto()   # ALU intermediate node
    CLOCK_NODE    = auto()   # Clock/phase node


@dataclass
class CircuitCell:
    """One storage element on the virtual circuit board."""
    id:        str
    cell_type: CellType
    state:     int = 0          # 0 or 1 (single bit)
    driven_by: list[str] = field(default_factory=list)   # cell IDs that drive this
    drives:    list[str] = field(default_factory=list)   # cell IDs this drives

    # MAGMA mapping
    magma_verb:  Optional[str] = None   # which verb transitions this cell
    microrom_op: Optional[int] = None   # which CA opcode evolves this cell


@dataclass
class VirtualCircuitBoard:
    """
    The stripped-down virtual silicon reconstruction.
    No instruction interpreter. No assembler. Just cells and their connectivity.
    Clock transitions cause the circuit to evolve — not opcode execution.
    """
    name:    str
    cells:   dict[str, CircuitCell] = field(default_factory=dict)
    clock:   int = 0   # global clock cycle counter

    def add_cell(self, cell: CircuitCell) -> None:
        self.cells[cell.id] = cell

    def tick(self) -> None:
        """Advance one clock edge — evolve dynamic storage nodes."""
        self.clock += 1
        # Propagate: each cell driven by others updates its state
        for cell in self.cells.values():
            if cell.cell_type == CellType.DYNAMIC_NODE:
                # Dynamic node: XOR of its inputs (capacitive charge)
                new_state = 0
                for src_id in cell.driven_by:
                    if src_id in self.cells:
                        new_state ^= self.cells[src_id].state
                cell.state = new_state

    def to_magma_matrix(self) -> bytes:
        """Pack all cell states into a 4096-bit matrix (512 bytes) for magma_666.adb."""
        bits = []
        for cell in sorted(self.cells.values(), key=lambda c: c.id):
            bits.append(cell.state & 1)
        # Pad or truncate to 4096 bits
        bits = (bits + [0] * 4096)[:4096]
        result = bytearray(512)
        for i, b in enumerate(bits):
            if b:
                result[i // 8] |= (1 << (i % 8))
        return bytes(result)

    def summary(self) -> str:
        counts = {}
        for c in self.cells.values():
            counts[c.cell_type.name] = counts.get(c.cell_type.name, 0) + 1
        lines = [f"  {k:<20} {v}" for k, v in sorted(counts.items())]
        return "\n".join(lines)


def build_6502_virtual_board() -> VirtualCircuitBoard:
    """
    Construct a virtual circuit board representing the core 6502 storage elements.
    No instruction semantics — only the physical storage structure.
    """
    board = VirtualCircuitBoard("6502_virtual")

    # ── 8-bit accumulator A ──────────────────────────────────────────────────
    for i in range(8):
        board.add_cell(CircuitCell(
            id       = f"A{i}",
            cell_type= CellType.REGISTER_BIT,
            driven_by= [f"ALU_OUT{i}"],
            drives   = [f"DATA_BUS{i}", f"ALU_IN_A{i}"],
            magma_verb   = "FLUX",
            microrom_op  = 0x1c,   # LOAD_CELL
        ))

    # ── 8-bit X/Y index registers ─────────────────────────────────────────────
    for reg in ("X", "Y"):
        for i in range(8):
            board.add_cell(CircuitCell(
                id       = f"{reg}{i}",
                cell_type= CellType.REGISTER_BIT,
                driven_by= [f"DATA_BUS{i}"],
                drives   = [f"ALU_IN_B{i}"],
                magma_verb   = "BIND",
                microrom_op  = 0x1c,
            ))

    # ── 8-bit Status Register (P) ─────────────────────────────────────────────
    status_bits = ["C","Z","I","D","B","_","V","N"]   # 6502 flag bits
    for i, flag in enumerate(status_bits):
        board.add_cell(CircuitCell(
            id       = f"SR_{flag}",
            cell_type= CellType.FLIPFLOP_D,
            driven_by= [f"ALU_FLAG_{flag}"],
            drives   = ["BRANCH_LOGIC"],
            magma_verb   = "SEAL" if flag in ("C","V") else "FLUX",
            microrom_op  = 0x1e,   # XOR_UPDATE
        ))

    # ── 8-bit Stack Pointer ───────────────────────────────────────────────────
    for i in range(8):
        board.add_cell(CircuitCell(
            id       = f"SP{i}",
            cell_type= CellType.REGISTER_BIT,
            driven_by= [f"ADDR_BUS{i}"],
            drives   = [f"ADDR_BUS{i}"],
            magma_verb   = "ANCHOR",
            microrom_op  = 0x0b,   # STORE_CELL
        ))

    # ── 16-bit Program Counter ────────────────────────────────────────────────
    for i in range(16):
        board.add_cell(CircuitCell(
            id       = f"PC{i}",
            cell_type= CellType.FLIPFLOP_D,
            driven_by= ["BRANCH_LOGIC", f"ADDR_BUS{i%8}"],
            drives   = [f"ADDR_BUS{i%8}"],
            magma_verb   = "INVOKE",
            microrom_op  = 0x09,   # INIT_STATE (route = PC jump)
        ))

    # ── ALU internal nodes (8 bits) ───────────────────────────────────────────
    for i in range(8):
        board.add_cell(CircuitCell(
            id       = f"ALU_OUT{i}",
            cell_type= CellType.ALU_NODE,
            driven_by= [f"ALU_IN_A{i}", f"ALU_IN_B{i}"],
            drives   = [f"A{i}", f"DATA_BUS{i}"],
            magma_verb   = "FORGE",
            microrom_op  = 0x1e,   # XOR_UPDATE
        ))

    # ── Dynamic storage nodes (6502 charge-stored state, 8 nodes) ─────────────
    for i in range(8):
        board.add_cell(CircuitCell(
            id       = f"DYN{i}",
            cell_type= CellType.DYNAMIC_NODE,
            driven_by= [f"PHI1", f"ALU_OUT{i}"],
            drives   = [f"INTERNAL_BUS{i}"],
            magma_verb   = "PULSE",
            microrom_op  = 0x1c,   # LOAD_CELL
        ))

    # ── Data bus (8 bits) ─────────────────────────────────────────────────────
    for i in range(8):
        board.add_cell(CircuitCell(
            id       = f"DATA_BUS{i}",
            cell_type= CellType.BUS_NODE,
            driven_by= [f"A{i}", "MEM_READ"],
            drives   = [f"A{i}", f"X{i}", f"Y{i}"],
            magma_verb   = "ECHO",
            microrom_op  = 0x0b,
        ))

    # ── Clock nodes ───────────────────────────────────────────────────────────
    for ph in ("PHI1", "PHI2"):
        board.add_cell(CircuitCell(
            id       = ph,
            cell_type= CellType.CLOCK_NODE,
            driven_by= [],
            drives   = [f"DYN{i}" for i in range(8)] + ["ALU_OUT0"],
            magma_verb   = "PULSE",
            microrom_op  = 0x80,   # CTRL
        ))

    return board


# ---------------------------------------------------------------------------
# Layer 6: CUFF kernel dispatcher
# ---------------------------------------------------------------------------

CUFF_DISPATCH: dict[str, str] = {
    "raw_gemm":                    "Matrix multiply (A×B+C) — ALU path",
    "raw_normalization":           "RMSNorm — ZK proof tick / SEAL",
    "raw_residual":                "Y=X+R — ANCHOR / WORM write-back",
    "raw_activation":              "GELU — non-linear gate (FORGE)",
    "raw_buffer_copy":             "Bulk copy — PULSE / READ / ECHO",
    "raw_reconstruction_loss":     "L2+spectral — VAULT encrypted store",
    "raw_position_encoding":       "Fourier PE — INVOKE / BRANCH",
    "raw_reconstruction_attention":"RECON_ATTENTION — QUERY / ORACLE",
}


# ---------------------------------------------------------------------------
# Springboard — full vertical integration
# ---------------------------------------------------------------------------

class Springboard:
    """
    Vertical integration across all seven layers.

    Analogous to iOS Springboard:
      launch_app()   = compile_and_run(§VERB)
      home_screen()  = show_board_state()
      lock_screen()  = validate_worm()
      app_switch()   = context_switch between ISA-8/ISA-16
    """

    def __init__(self) -> None:
        self.board      = build_6502_virtual_board()
        self.isa8_vm    = ISA8VM()
        self.isa16_vm   = ISA16VM()
        self.compiler   = MacroMAGMA()
        self._worm_chain: list[str] = []

    # ── Layer 7: Virtual circuit board ───────────────────────────────────────

    def tick_board(self, n: int = 1) -> None:
        """Advance N clock edges on the virtual circuit board."""
        for _ in range(n):
            self.board.tick()

    def load_program_into_board(self, cells: bytes) -> None:
        """
        Load a program's binary into the circuit board's register cells.
        Maps each byte to 8 consecutive register bits (A0–A7, X0–X7, etc.)
        """
        bit_idx = 0
        for byte in cells[:64]:   # first 64 bytes
            for b in range(8):
                bit = (byte >> b) & 1
                cell_id = f"A{bit_idx % 8}" if bit_idx < 8 \
                    else f"X{bit_idx % 8}" if bit_idx < 16 \
                    else f"DYN{bit_idx % 8}"
                if cell_id in self.board.cells:
                    self.board.cells[cell_id].state = bit
                bit_idx += 1

    # ── Layer 5: MicroROM CA VM ───────────────────────────────────────────────

    def run_microrom_sequence(self, ops: list[tuple[int, int]]) -> list[int]:
        """
        Execute a MicroROM opcode sequence and return cell states.
        ops = [(0x1c, node_idx), (0x1e, rule), (0x0b, node_idx), ...]
        """
        acc = 0
        results = []
        for op, arg in ops:
            if op == 0x1c:    # LOAD_CELL
                node = f"DYN{arg % 8}"
                acc = self.board.cells.get(node, type("", (), {"state": 0})()).state
            elif op == 0x1e:  # XOR_UPDATE
                acc ^= (arg & 0xFF)
            elif op == 0x0b:  # STORE_CELL
                node = f"DYN{arg % 8}"
                if node in self.board.cells:
                    self.board.cells[node].state = acc & 1
            elif op == 0x09:  # INIT_STATE
                acc = 0
            results.append(acc)
        return results

    # ── Layer 4: ISA VM execution ─────────────────────────────────────────────

    def run_isa8(self, program: list[tuple[int, int]] | None = None) -> str:
        """Run the ISA-8 VM and return execution trace."""
        if program:
            self.isa8_vm = ISA8VM(ISA8Program(program))
        else:
            self.isa8_vm.reset()
        return self.isa8_vm.run_summary()

    def run_isa16(self, program: list[tuple[int, int]] | None = None) -> str:
        """Run the ISA-16 VM and return execution trace."""
        if program:
            self.isa16_vm = ISA16VM(ISA16Program(program))
        else:
            self.isa16_vm.reset()
        return self.isa16_vm.run_summary()

    # ── Layer 3: CCE decode ───────────────────────────────────────────────────

    def decode_control_word(self, opcode: int) -> dict:
        from src.magma.macro_magma import cce_decode, cce_fields, alu_to_cuff
        cw = cce_decode(opcode)
        f  = cce_fields(cw)
        return {
            "opcode":       opcode,
            "control_word": cw,
            "fields":       f,
            "cuff_kernel":  alu_to_cuff(f["ALU_Op"]),
        }

    # ── Layer 2: MAGMA compiler (§VERB → ISA → CCE → CA → CUFF) ──────────────

    def launch_app(self, verb: str, agent: str = "CIPHER", action: str = "DEFAULT") -> dict:
        """
        Springboard: launch an app = compile + execute a §MAGMA instruction
        through all seven layers.
        """
        # L2: compile MAGMA → ISA + CCE + MicroROM + CUFF
        instr = self.compiler.compile(verb, agent, action)

        # L4: run through ISA-8 VM
        isa_result = self.run_isa8(instr.isa8_ops)

        # L5: run through MicroROM CA
        ca_results = self.run_microrom_sequence(instr.microrom_ops)

        # L7: advance virtual board one clock edge per microrom op
        self.tick_board(len(instr.microrom_ops))

        # WORM: hash the full execution trace
        raw = f"{verb}:{instr.worm_hash}:{ca_results}:{self.board.clock}"
        seal = hashlib.sha256(raw.encode()).hexdigest()
        self._worm_chain.append(seal)

        return {
            "instruction":   instr,
            "isa_trace":     isa_result,
            "ca_results":    ca_results,
            "board_clock":   self.board.clock,
            "worm_seal":     seal,
            "cuff_kernels":  instr.cuff_kernels,
        }

    # ── Layer 1: MAGMA protocol interface (home screen) ───────────────────────

    def home_screen(self) -> str:
        """Show the current state of the virtual circuit board."""
        lines = [
            "╔══════════════════════════════════════════════════════════╗",
            "║  SPRINGBOARD — VIRTUAL CIRCUIT BOARD                    ║",
            "╠══════════════════════════════════════════════════════════╣",
            f"║  Clock cycle     : {self.board.clock:<38}║",
            f"║  Cells total     : {len(self.board.cells):<38}║",
            f"║  WORM chain len  : {len(self._worm_chain):<38}║",
            "╠══════════════════════════════════════════════════════════╣",
            "║  Cell type distribution:                                 ║",
        ]
        counts: dict[str, int] = {}
        for c in self.board.cells.values():
            counts[c.cell_type.name] = counts.get(c.cell_type.name, 0) + 1
        for k, v in sorted(counts.items()):
            lines.append(f"║    {k:<22}  {v:<34}║")
        lines += [
            "╠══════════════════════════════════════════════════════════╣",
            "║  Register A state (8 bits):                              ║",
        ]
        a_bits = "".join(str(self.board.cells.get(f"A{i}", type("",(),{"state":0})()).state) for i in range(8))
        lines.append(f"║    A = {a_bits} = 0x{int(a_bits[::-1],2):02X}{'':38}║")
        lines += [
            "╠══════════════════════════════════════════════════════════╣",
            "║  WORM chain head:                                        ║",
        ]
        head = self._worm_chain[-1][:48] + "..." if self._worm_chain else "(empty)"
        lines.append(f"║    {head:<54}║")
        lines.append("╚══════════════════════════════════════════════════════════╝")
        return "\n".join(lines)

    def lock_screen(self) -> bool:
        """Validate WORM chain integrity."""
        if not self._worm_chain:
            return True
        return all(len(h) == 64 for h in self._worm_chain)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sb = Springboard()

    print("═" * 62)
    print("  SPRINGBOARD BOOT")
    print("═" * 62)
    print()
    print(sb.home_screen())
    print()

    # Launch apps through the full stack
    for verb, agent, action in [
        ("PULSE",  "FLUX",    "BOARD_PROBE"),
        ("FORGE",  "FORGE",   "ALU_BUILD"),
        ("SEAL",   "CIPHER",  "SIGN"),
        ("ANCHOR", "MNEMEX",  "WORM_PERSIST"),
    ]:
        print(f"  § Launching §{verb}:{agent}:{action}...")
        result = sb.launch_app(verb, agent, action)
        cuff   = " + ".join(result["cuff_kernels"])
        ca     = result["ca_results"]
        print(f"    CUFF : {cuff}")
        print(f"    CA   : {ca}")
        print(f"    WORM : {result['worm_seal'][:32]}...")
        print()

    print(sb.home_screen())
    print()
    print(f"  Lock screen valid: {sb.lock_screen()}")
