"""
Static Opcode Registry for Sovereign IPC Tool Dispatcher
Part of SOVEREIGN PYTHON LLM ENGINE

Maps 16-bit opcodes to tool_ids for O(1) dispatch without string lookup.

Static assignments (0x0001-0x0022) mirror the 34 tools registered in
registry.py. Dynamic opcodes start at 0x0100 to leave 0x0023-0x00FF as
reserved expansion space for future namespaces.

Wire protocol:
  opcode 0x0000  — reserved (null / no-op)
  opcode 0x0001-0x0022  — static built-in tools
  opcode 0x0023-0x00FF  — reserved
  opcode 0x0100-0xFFFF  — dynamic runtime registrations

Thread-safety: register_dynamic() uses a module-level lock so concurrent
workers can register tools safely.
"""

from __future__ import annotations

import threading
from typing import Iterator

# ─────────────────────────────────────────────────────────────────────────────
# Static opcode table — assigned at build time, never change
# ─────────────────────────────────────────────────────────────────────────────

OPCODE_TABLE: dict[int, str] = {
    0x0001: "filesystem.read",
    0x0002: "filesystem.write",
    0x0003: "filesystem.list",
    0x0004: "filesystem.delete",
    0x0005: "filesystem.move",
    0x0006: "filesystem.search",
    0x0007: "code.execute_python",
    0x0008: "code.shell",
    0x0009: "git.status",
    0x000A: "git.diff",
    0x000B: "git.log",
    0x000C: "git.commit",
    0x000D: "git.push",
    0x000E: "git.pull",
    0x000F: "git.branch_list",
    0x0010: "git.branch_create",
    0x0011: "git.checkout",
    0x0012: "git.clone",
    0x0013: "database.sqlite_query",
    0x0014: "database.sqlite_execute",
    0x0015: "database.sqlite_list_tables",
    0x0016: "documents.parse_pdf",
    0x0017: "documents.parse_docx",
    0x0018: "documents.parse_markdown",
    0x0019: "documents.parse_html",
    0x001A: "web.search",
    0x001B: "web.fetch",
    0x001C: "web.extract",
    0x001D: "embeddings.encode_text",
    0x001E: "embeddings.similarity",
    0x001F: "audio.transcribe",
    0x0020: "audio.synthesize",
    0x0021: "pytorch.tensor_operation",
    0x0022: "pytorch.check_cuda",
}

# Reverse map — built once from OPCODE_TABLE
TOOL_OPCODES: dict[str, int] = {v: k for k, v in OPCODE_TABLE.items()}

# ─────────────────────────────────────────────────────────────────────────────
# Dynamic registry state
# ─────────────────────────────────────────────────────────────────────────────

# All dynamic entries go in these mutable dicts (same key space, different
# range so they never collide with static entries).
_dynamic_opcode_to_tool: dict[int, str] = {}
_dynamic_tool_to_opcode: dict[str, int] = {}

# Next available dynamic opcode counter — starts at 0x0100
_next_dynamic_opcode: int = 0x0100
_registry_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_opcode(tool_id: str) -> int:
    """
    Return the 16-bit opcode for *tool_id*.

    Searches static table first, then dynamic registrations.

    Args:
        tool_id: Fully-qualified tool identifier (e.g. "filesystem.read")

    Returns:
        16-bit integer opcode

    Raises:
        KeyError: If tool_id is not registered
    """
    if tool_id in TOOL_OPCODES:
        return TOOL_OPCODES[tool_id]
    with _registry_lock:
        if tool_id in _dynamic_tool_to_opcode:
            return _dynamic_tool_to_opcode[tool_id]
    raise KeyError(f"No opcode registered for tool_id: {tool_id!r}")


def get_tool_id(opcode: int) -> str:
    """
    Return the tool_id for *opcode*.

    Searches static table first, then dynamic registrations.

    Args:
        opcode: 16-bit integer opcode

    Returns:
        tool_id string

    Raises:
        KeyError: If opcode is not registered
    """
    if opcode in OPCODE_TABLE:
        return OPCODE_TABLE[opcode]
    with _registry_lock:
        if opcode in _dynamic_opcode_to_tool:
            return _dynamic_opcode_to_tool[opcode]
    raise KeyError(f"No tool_id registered for opcode: 0x{opcode:04X}")


def register_dynamic(tool_id: str) -> int:
    """
    Assign the next available dynamic opcode to *tool_id*.

    If *tool_id* is already registered (static or dynamic) the existing
    opcode is returned without allocating a new one — idempotent.

    Dynamic opcodes start at 0x0100.  If the 16-bit space is exhausted
    (all 65280 dynamic slots filled) a RuntimeError is raised.

    Args:
        tool_id: Fully-qualified tool identifier

    Returns:
        Assigned 16-bit opcode

    Raises:
        RuntimeError: If the dynamic opcode space is exhausted
    """
    # Fast path — already in static table
    if tool_id in TOOL_OPCODES:
        return TOOL_OPCODES[tool_id]

    with _registry_lock:
        global _next_dynamic_opcode

        # Already registered dynamically — return existing opcode
        if tool_id in _dynamic_tool_to_opcode:
            return _dynamic_tool_to_opcode[tool_id]

        if _next_dynamic_opcode > 0xFFFF:
            raise RuntimeError(
                "Dynamic opcode space exhausted — all 16-bit opcodes are assigned"
            )

        opcode = _next_dynamic_opcode
        _next_dynamic_opcode += 1

        _dynamic_opcode_to_tool[opcode] = tool_id
        _dynamic_tool_to_opcode[tool_id] = opcode

        return opcode


def list_opcodes() -> list[tuple[int, str]]:
    """
    Return all registered (opcode, tool_id) pairs, sorted by opcode.

    Includes both static and dynamic registrations.

    Returns:
        Sorted list of (opcode, tool_id) tuples
    """
    combined: dict[int, str] = {}
    combined.update(OPCODE_TABLE)
    with _registry_lock:
        combined.update(_dynamic_opcode_to_tool)
    return sorted(combined.items())


def is_static(opcode: int) -> bool:
    """
    Return True if *opcode* is a static (built-in) assignment.

    Args:
        opcode: 16-bit integer opcode

    Returns:
        True for static opcodes (0x0001-0x0022), False otherwise
    """
    return opcode in OPCODE_TABLE


def is_dynamic(opcode: int) -> bool:
    """
    Return True if *opcode* was registered at runtime via register_dynamic().

    Args:
        opcode: 16-bit integer opcode

    Returns:
        True for dynamically registered opcodes
    """
    with _registry_lock:
        return opcode in _dynamic_opcode_to_tool


def opcode_count() -> int:
    """
    Return total number of registered opcodes (static + dynamic).

    Returns:
        Integer count
    """
    with _registry_lock:
        return len(OPCODE_TABLE) + len(_dynamic_opcode_to_tool)


def iter_static() -> Iterator[tuple[int, str]]:
    """
    Yield (opcode, tool_id) pairs for all static registrations, sorted.

    Yields:
        (opcode, tool_id) tuples in ascending opcode order
    """
    for opcode, tool_id in sorted(OPCODE_TABLE.items()):
        yield opcode, tool_id


def iter_dynamic() -> Iterator[tuple[int, str]]:
    """
    Yield (opcode, tool_id) pairs for all dynamic registrations, sorted.

    Yields:
        (opcode, tool_id) tuples in ascending opcode order
    """
    with _registry_lock:
        snapshot = sorted(_dynamic_opcode_to_tool.items())
    for opcode, tool_id in snapshot:
        yield opcode, tool_id
