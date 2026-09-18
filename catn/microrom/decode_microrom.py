"""
decode_microrom.py — Boolean Cellular Automaton MicroROM Decoder

Source: BINARY MICROROM.txt (bob's control repo)

The MicroROM is the bytecode output of vm_bytecode_gen.c for a 256-node
Boolean network CA. Each word is 32-bit big-endian hex.

Opcode table (upper byte of each 32-bit word):
  0x1c  LOAD_CELL    load state of node[arg] into accumulator
  0x1e  XOR_UPDATE   XOR accumulator with rule result
  0x0b  STORE_CELL   write accumulator back to node[arg]
  0x09  INIT_STATE   initialize CA state register
  0x0a  SET_RULE     set Boolean rule for current node
  0x80  CTRL         control word (marks section boundaries)

Structure:
  - 7 header words (init + rule setup)
  - ~2966 LOAD/XOR/STORE triplets = one full CA generation step over 256 nodes
  - Each triplet: LOAD_CELL node_idx | XOR_UPDATE rule_arg | STORE_CELL node_idx
"""

from __future__ import annotations

import sys
import io
import collections
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OPCODE_NAMES = {
    0x1c: "LOAD_CELL",
    0x1e: "XOR_UPDATE",
    0x0b: "STORE_CELL",
    0x09: "INIT_STATE",
    0x0a: "SET_RULE",
    0x80: "CTRL",
    0x00: "NOP",
}


def decode_word(word: int) -> tuple[str, int]:
    op   = (word >> 24) & 0xFF
    arg  = word & 0xFFFFFF
    name = OPCODE_NAMES.get(op, f"UNK(0x{op:02x})")
    return name, arg


def decode_microrom(path: str) -> list[tuple[int, str, int]]:
    lines = Path(path).read_text().splitlines()
    words = [int(l.strip(), 16) for l in lines if l.strip()]
    result = []
    for i, w in enumerate(words):
        name, arg = decode_word(w)
        result.append((i, name, arg))
    return result


def analyse(path: str) -> None:
    instructions = decode_microrom(path)
    total = len(instructions)

    print("=== MicroROM Analysis ===")
    print(f"Total words : {total}")
    print(f"Bytes       : {total * 4}")
    print()

    # Opcode distribution
    counts = collections.Counter(name for _, name, _ in instructions)
    print("Opcode distribution:")
    for name, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        pct = cnt / total * 100
        print(f"  {name:<15}  {cnt:>6}  ({pct:.1f}%)")
    print()

    # Header (first 20 words)
    print("Header instructions (first 14 words):")
    for idx, name, arg in instructions[:14]:
        print(f"  [{idx:>4}]  {name:<15}  0x{arg:06x}  ({arg})")
    print()

    # Detect LOAD/XOR/STORE triplet structure
    triplets = []
    i = 14  # skip header
    while i + 2 < len(instructions):
        a_idx, a_op, a_arg = instructions[i]
        b_idx, b_op, b_arg = instructions[i + 1]
        c_idx, c_op, c_arg = instructions[i + 2]
        if a_op == "LOAD_CELL" and b_op == "XOR_UPDATE" and c_op == "STORE_CELL":
            triplets.append((a_arg, b_arg, c_arg))
            i += 3
        else:
            i += 1

    print(f"LOAD/XOR/STORE triplets: {len(triplets)}")
    n_nodes = 256
    generations = len(triplets) / n_nodes if n_nodes > 0 else 0
    print(f"Assuming 256 nodes → {generations:.2f} CA generation steps")
    print()

    # Sample triplets
    print("Sample triplets (node, rule_arg, store_node):")
    for load_arg, xor_arg, store_arg in triplets[:8]:
        print(f"  LOAD node={load_arg:#05x}  XOR rule={xor_arg:#05x}  STORE node={store_arg:#05x}")
    print()

    # Unique node indices
    node_ids = sorted(set(t[0] for t in triplets))
    print(f"Unique node indices: {len(node_ids)}")
    if node_ids:
        print(f"  Range: {min(node_ids)} – {max(node_ids)}")

    # Generation structure: find how many triplets per node
    node_counts = collections.Counter(t[0] for t in triplets)
    ops_per_node = list(node_counts.values())
    if ops_per_node:
        print(f"  Ops per node: min={min(ops_per_node)} max={max(ops_per_node)} mean={sum(ops_per_node)/len(ops_per_node):.1f}")


def export_disassembly(path: str, out_path: str) -> None:
    """Write full disassembly to a text file."""
    instructions = decode_microrom(path)
    lines = []
    lines.append("; MicroROM Disassembly")
    lines.append(f"; Source: {path}")
    lines.append(f"; Words: {len(instructions)}")
    lines.append("")
    for idx, name, arg in instructions:
        lines.append(f"[{idx:>5}]  {name:<15}  0x{arg:06x}")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"Disassembly written to {out_path}")


if __name__ == "__main__":
    here  = Path(__file__).parent
    rom   = here / "microrom.hex"
    disas = here / "microrom_disassembly.txt"

    analyse(str(rom))
    print()
    export_disassembly(str(rom), str(disas))
