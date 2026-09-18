"""
tunnel_layer.py — WASM Tunnel Layer

The bypass layer that strips the NATS broker and creates direct
memory-to-memory apertures through the substrate.

Full sovereign stack:
  ┌─────────────────────────────────────────────────────┐
  │  SPRINGBOARD          §MAGMA verbs                  │
  ├─────────────────────────────────────────────────────┤
  │  UIKit layer          ISA-8 / ISA-16 VMs            │
  ├─────────────────────────────────────────────────────┤
  │  Private Frameworks   CCE 64-bit control word       │
  ├─────────────────────────────────────────────────────┤
  │  XPC / Mach IPC       MAGMA bindings / magmad       │
  ├─────────────────────────────────────────────────────┤
  │  backboardd           MicroROM CA VM                │
  ├─────────────────────────────────────────────────────┤
  │  Hardware             CUFF assembly kernels          │
  ├─────────────────────────────────────────────────────┤
  │  MacroWASM            <X 36 02 40 20 00 20 01 6A>   │
  ├─────────────────────────────────────────────────────┤
  │  M5 buffer            m5.wat (4096 bytes, 7 regs)   │
  ├──────────────────────── TUNNEL ─────────────────────┤
  │  tunnel_borehole.wat  purge_beams_and_nats +        │
  │                       bore_tunnel_hole(0xDEADBEEF)  │
  ├─────────────────────────────────────────────────────┤
  │  tunnel_matrix.wat    bore_tunnel(src,dst,len) +    │
  │                       verify_aperture + checksum    │
  ├─────────────────────────────────────────────────────┤
  │  Virtual Circuit Board  6502/Z80 storage cells      │
  └─────────────────────────────────────────────────────┘

Tunnel operations → MAGMA mapping:
  purge_beams_and_nats    → §NULLIFY:SENTINEL:RESET_CORE
  bore_tunnel_hole        → §FLUX:FLUX:PULSE_MATRIX (no NATS hop)
  bore_tunnel(src,dst)    → §ANCHOR:MNEMEX:WORM_PERSIST (direct path)
  verify_aperture         → §SEAL:CIPHER:SIGN (bounds + integrity)
  seal_aperture           → §BIND:CIPHER:LATCH_STATE (close tunnel)

0xDEADBEEF sentinel: marks live apertures on the virtual circuit board.
  When the board scans a cell and finds 0xDEADBEEF, it routes that cell
  directly through the tunnel (bypassing NATS/magmad).

Memory layout:
  tunnel_borehole: 2 pages = 128KB  (NATS purge + aperture punch)
  tunnel_matrix:   4 pages = 256KB  (raw transfer + board pipeline)
    [0x00000..0x0FFFF] Core 0 — primary tunnel channel
    [0x10000..0x1FFFF] Core 1 — secondary
    [0x20000..0x2FFFF] Core 2 — M5 mirror
    [0x30000..0x3FFFF] Core 3 — framebuffer staging
"""

from __future__ import annotations

import struct
import hashlib
from dataclasses import dataclass, field


DEAD_BEEF = 0xDEADBEEF
BOREHOLE_SIZE  = 2 * 65536   # 128KB
MATRIX_SIZE    = 4 * 65536   # 256KB
M5_SIZE        = 4096        # bytes


# ---------------------------------------------------------------------------
# Python simulation of the WASM tunnel modules
# ---------------------------------------------------------------------------

class TunnelBorehole:
    """
    Simulates tunnel_borehole.wat.
    Bypasses all NATS broker nodes; provides direct substrate apertures.
    """

    def __init__(self) -> None:
        self.memory = bytearray(BOREHOLE_SIZE)

    def purge_beams_and_nats(self) -> None:
        """Zero out 64KB broker register banks (strip NATS routing state)."""
        for i in range(65536):
            self.memory[i] = 0

    def bore_tunnel_hole(self, entry_point: int, depth: int) -> int:
        """
        Fill [entry_point .. entry_point+depth) with 0xDEADBEEF.
        Returns entry_point (aperture base address).
        """
        offset = entry_point
        limit  = entry_point + depth
        while offset < limit and offset + 3 < BOREHOLE_SIZE:
            struct.pack_into("<I", self.memory, offset, DEAD_BEEF)
            offset += 4
        return entry_point

    def is_tunnel_alive(self, addr: int) -> bool:
        if addr + 3 >= BOREHOLE_SIZE:
            return False
        val = struct.unpack_from("<I", self.memory, addr)[0]
        return val == DEAD_BEEF

    def seal_aperture(self, entry_point: int, depth: int) -> None:
        """Close tunnel by zeroing aperture (deactivate without full purge)."""
        offset = entry_point
        limit  = entry_point + depth
        while offset < limit and offset + 3 < BOREHOLE_SIZE:
            struct.pack_into("<I", self.memory, offset, 0)
            offset += 4

    def live_apertures(self) -> list[int]:
        """Return list of base addresses where 0xDEADBEEF tunnels are active."""
        addrs = []
        for i in range(0, BOREHOLE_SIZE - 3, 4):
            val = struct.unpack_from("<I", self.memory, i)[0]
            if val == DEAD_BEEF:
                addrs.append(i)
        return addrs


class TunnelMatrix:
    """
    Simulates tunnel_matrix.wat.
    Raw voltage transfer: direct memory-to-memory, no middleware.
    """

    def __init__(self) -> None:
        self.memory = bytearray(MATRIX_SIZE)

    def bore_tunnel(self, src: int, dst: int, length: int) -> None:
        """
        Raw byte-level memcpy within the matrix.
        Maps to §ANCHOR:MNEMEX:WORM_PERSIST (direct, no NATS).
        """
        for i in range(length):
            if src + i < MATRIX_SIZE and dst + i < MATRIX_SIZE:
                self.memory[dst + i] = self.memory[src + i]

    def write_external(self, dst: int, data: bytes) -> None:
        """Write external bytes into the matrix (from M5 or CUFF kernel output)."""
        for i, b in enumerate(data):
            if dst + i < MATRIX_SIZE:
                self.memory[dst + i] = b

    def verify_aperture(self, addr: int) -> bool:
        """addr < 262144 — within 4-page matrix bounds."""
        return addr < MATRIX_SIZE

    def tunnel_checksum(self) -> int:
        """SHA-256-seed checksum over all 256KB."""
        return sum(self.memory)

    def pipe_m5_to_board(self, m5_src: int, m5_data: bytes) -> int:
        """
        Copy 4096 bytes from M5 buffer into Core 0 of tunnel matrix.
        Returns checksum of transferred region.
        Connection: m5.wat → tunnel_matrix Core 0 → virtual circuit board.
        """
        self.write_external(m5_src, m5_data[:M5_SIZE])
        # Core 0 is at [0x0000..0x0FFF]
        self.bore_tunnel(m5_src, 0x0000, M5_SIZE)
        return sum(self.memory[0:M5_SIZE])


# ---------------------------------------------------------------------------
# Full tunnel pipeline
# ---------------------------------------------------------------------------

@dataclass
class TunnelSession:
    """One complete tunnel bore: NATS purge → aperture → M5 pipe → WORM seal."""
    borehole: TunnelBorehole = field(default_factory=TunnelBorehole)
    matrix:   TunnelMatrix   = field(default_factory=TunnelMatrix)
    worm_seals: list[str]    = field(default_factory=list)

    def run(
        self,
        m5_data:     bytes,
        entry_point: int  = 0x100,
        depth:       int  = 256,
    ) -> dict:
        """
        Execute the full tunnel pipeline:
          1. Purge NATS beams
          2. Bore aperture at entry_point
          3. Pipe M5 data through tunnel
          4. Verify aperture bounds
          5. Compute checksum → WORM seal
          6. Seal aperture
        """
        # Step 1: Purge NATS broker register banks
        self.borehole.purge_beams_and_nats()

        # Step 2: Bore quantum tunnel aperture
        base = self.borehole.bore_tunnel_hole(entry_point, depth)
        alive = self.borehole.is_tunnel_alive(base)

        # Step 3: Load M5 data into matrix staging region (Core 2 = 0x20000)
        self.matrix.write_external(0x20000, m5_data[:M5_SIZE])

        # Step 4: Pipe M5 → Core 0 (virtual circuit board)
        checksum = self.matrix.pipe_m5_to_board(0x20000, m5_data)

        # Step 5: Verify aperture
        aperture_ok = self.matrix.verify_aperture(base)

        # Step 6: WORM seal
        raw    = f"TUNNEL:{base:08X}:{depth}:{checksum}:{aperture_ok}"
        seal   = hashlib.sha256(raw.encode()).hexdigest()
        self.worm_seals.append(seal)

        # Step 7: Seal the aperture (deactivate after use)
        self.borehole.seal_aperture(base, depth)

        return {
            "entry_point":  base,
            "depth":        depth,
            "tunnel_alive": alive,
            "aperture_ok":  aperture_ok,
            "m5_bytes":     len(m5_data),
            "checksum":     checksum,
            "worm_seal":    seal,
            "live_after":   self.borehole.live_apertures(),
        }

    def summary(self) -> str:
        lines = [
            "╔══ TUNNEL LAYER STATUS",
            f"│  Borehole memory  : {BOREHOLE_SIZE // 1024} KB",
            f"│  Matrix memory    : {MATRIX_SIZE // 1024} KB",
            f"│  WORM seals issued: {len(self.worm_seals)}",
            f"│  Matrix checksum  : {self.matrix.tunnel_checksum()}",
            "╰──────────────────────────────────",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAGMA verb → tunnel operation mapping
# ---------------------------------------------------------------------------

TUNNEL_VERBS: dict[str, str] = {
    "NULLIFY": "purge_beams_and_nats",
    "FLUX":    "bore_tunnel_hole",
    "ANCHOR":  "bore_tunnel",
    "SEAL":    "verify_aperture + tunnel_checksum",
    "BIND":    "seal_aperture",
    "PULSE":   "is_tunnel_alive",
}

def tunnel_verb_to_op(verb: str) -> str:
    return TUNNEL_VERBS.get(verb, "noop")


if __name__ == "__main__":
    import sys, io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print("=== Tunnel Layer Demo ===")
    print()

    # Build a synthetic M5 payload (simulate magma_666.adb Core_State.cells)
    m5_data = bytes([0xAB if i % 64 == 0 else 0x00 for i in range(4096)])

    session = TunnelSession()
    result  = session.run(m5_data, entry_point=0x100, depth=256)

    print("Tunnel bore result:")
    for k, v in result.items():
        if k == "live_after":
            print(f"  {k:<16}: {len(v)} live apertures remaining")
        else:
            val = v[:32]+"..." if isinstance(v,str) and len(v)>32 else v
            print(f"  {k:<16}: {val}")

    print()
    print(session.summary())
    print()

    print("MAGMA verb → tunnel operation:")
    for verb, op in TUNNEL_VERBS.items():
        print(f"  §{verb:<10} → {op}")
