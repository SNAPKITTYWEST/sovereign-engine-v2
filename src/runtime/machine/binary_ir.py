"""
binary_ir.py — Binary intermediate representation for the sovereign routing pipeline.

Converts Python agent actions / parse results to a compact binary format (SOVEREIGN_IR)
suitable for high-speed dispatch, WORM commitment, and cross-process routing.

Format: SOVR magic + fixed header + node records + edge records + symbol table

Part of the SOVEREIGN_IR PYTHON_C_BRIDGE_IR pipeline.
Agent A (Cognition) — HyperKittyConstraintDSL v1.0
"""

from __future__ import annotations

import hashlib
import io
import math
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# IR format constants
# ---------------------------------------------------------------------------

IR_MAGIC            = b'SOVR'
IR_VERSION          = 1
IR_HEADER_SIZE      = 16    # magic(4) + version(1) + flags(1) + node_count(2) + edge_count(2) + timestamp(8)
IR_NODE_SIZE        = 32    # fixed per node
IR_EDGE_SIZE        = 16    # fixed per edge
IR_CHECKSUM_SIZE    = 32    # Blake2b-256 appended at end

# Header format: >4sBBHHQ  (big-endian)
# magic=4s, version=B, flags=B, node_count=H, edge_count=H, timestamp=Q
IR_HEADER_STRUCT    = struct.Struct('>4sBBHHQ')
assert IR_HEADER_STRUCT.size == IR_HEADER_SIZE

# Node record format: >HBBffIH10s (32 bytes big-endian)
# node_id=H, node_type=B, flags=B, routing_weight=f, entropy=f,
# symbol_offset=I, symbol_len=H, padding=10s
IR_NODE_STRUCT      = struct.Struct('>HBBffIH10s')
assert IR_NODE_STRUCT.size == IR_NODE_SIZE

# Edge record format: >HHfBB6s (16 bytes big-endian)
# src_id=H, dst_id=H, weight=f, edge_type=B, flags=B, padding=6s
IR_EDGE_STRUCT      = struct.Struct('>HHfBB6s')
assert IR_EDGE_STRUCT.size == IR_EDGE_SIZE


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class IRNodeType(IntEnum):
    INTENT     = 0
    ENTITY     = 1
    OPERATOR   = 2
    CONSTRAINT = 3
    PAYLOAD    = 4

    @classmethod
    def from_str(cls, s: str) -> 'IRNodeType':
        return cls[s.upper()]


class IREdgeType(IntEnum):
    PARENT_CHILD = 0
    SIBLING      = 1
    CROSS_REF    = 2

    @classmethod
    def from_str(cls, s: str) -> 'IREdgeType':
        return cls[s.upper()]


# Node flags
IR_NODE_FLAG_SEALED     = 0x01
IR_NODE_FLAG_WORM       = 0x02
IR_NODE_FLAG_TRUSTED    = 0x04
IR_NODE_FLAG_EPHEMERAL  = 0x08
IR_NODE_FLAG_ROUTED     = 0x10
IR_NODE_FLAG_ERROR      = 0x20

# Edge flags
IR_EDGE_FLAG_CRITICAL   = 0x01
IR_EDGE_FLAG_WEAK       = 0x02
IR_EDGE_FLAG_ASYNC      = 0x04

# IR flags (header)
IR_FLAG_COMPRESSED      = 0x01
IR_FLAG_SIGNED          = 0x02
IR_FLAG_CHECKSUMMED     = 0x04


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IRNode:
    node_id: int
    node_type: IRNodeType
    flags: int
    routing_weight: float
    entropy: float
    symbol: str

    def __post_init__(self):
        if isinstance(self.node_type, int):
            self.node_type = IRNodeType(self.node_type)
        # Clamp values to valid ranges
        self.routing_weight = max(0.0, min(1.0, float(self.routing_weight)))
        self.entropy = max(0.0, min(1.0, float(self.entropy)))

    def is_sealed(self) -> bool:
        return bool(self.flags & IR_NODE_FLAG_SEALED)

    def is_trusted(self) -> bool:
        return bool(self.flags & IR_NODE_FLAG_TRUSTED)

    def check_entropy_constraint(self) -> bool:
        """DSL constraint: entropy <= 0.20"""
        return self.entropy <= 0.20

    def with_flag(self, flag: int) -> 'IRNode':
        return IRNode(
            node_id=self.node_id,
            node_type=self.node_type,
            flags=self.flags | flag,
            routing_weight=self.routing_weight,
            entropy=self.entropy,
            symbol=self.symbol,
        )

    def to_dict(self) -> dict:
        return {
            'node_id': self.node_id,
            'node_type': self.node_type.name,
            'flags': self.flags,
            'routing_weight': self.routing_weight,
            'entropy': self.entropy,
            'symbol': self.symbol,
        }


@dataclass
class IREdge:
    src_id: int
    dst_id: int
    weight: float
    edge_type: IREdgeType
    flags: int

    def __post_init__(self):
        if isinstance(self.edge_type, int):
            self.edge_type = IREdgeType(self.edge_type)
        self.weight = max(0.0, min(1.0, float(self.weight)))

    def to_dict(self) -> dict:
        return {
            'src_id': self.src_id,
            'dst_id': self.dst_id,
            'weight': self.weight,
            'edge_type': self.edge_type.name,
            'flags': self.flags,
        }


@dataclass
class IRGraph:
    nodes: list[IRNode] = field(default_factory=list)
    edges: list[IREdge] = field(default_factory=list)
    timestamp_ns: int = field(default_factory=lambda: time.time_ns())

    def add_node(self, node: IRNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: IREdge) -> None:
        self.edges.append(edge)

    def get_node(self, node_id: int) -> Optional[IRNode]:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges)

    def neighbors(self, node_id: int) -> list[int]:
        """Return list of dst_ids reachable from node_id."""
        return [e.dst_id for e in self.edges if e.src_id == node_id]

    def parents(self, node_id: int) -> list[int]:
        """Return list of src_ids that have edges to node_id."""
        return [e.src_id for e in self.edges if e.dst_id == node_id]

    def subgraph(self, node_ids: set[int]) -> 'IRGraph':
        """Return a new IRGraph containing only the specified nodes and their edges."""
        nodes = [n for n in self.nodes if n.node_id in node_ids]
        edges = [e for e in self.edges
                 if e.src_id in node_ids and e.dst_id in node_ids]
        return IRGraph(nodes=nodes, edges=edges, timestamp_ns=self.timestamp_ns)

    def mean_entropy(self) -> float:
        if not self.nodes:
            return 0.0
        return sum(n.entropy for n in self.nodes) / len(self.nodes)

    def max_entropy(self) -> float:
        if not self.nodes:
            return 0.0
        return max(n.entropy for n in self.nodes)

    def entropy_compliant(self) -> bool:
        """DSL constraint: all node entropy <= 0.20"""
        return all(n.entropy <= 0.20 for n in self.nodes)

    def symbols(self) -> list[str]:
        return [n.symbol for n in self.nodes]

    def to_adjacency_list(self) -> dict[int, list[int]]:
        adj: dict[int, list[int]] = {n.node_id: [] for n in self.nodes}
        for e in self.edges:
            if e.src_id in adj:
                adj[e.src_id].append(e.dst_id)
        return adj

    def topological_sort(self) -> list[int]:
        """Kahn's algorithm. Returns ordered node IDs or raises on cycle."""
        in_degree: dict[int, int] = {n.node_id: 0 for n in self.nodes}
        adj = self.to_adjacency_list()
        for e in self.edges:
            in_degree[e.dst_id] = in_degree.get(e.dst_id, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.nodes):
            raise IRError("Cycle detected in IRGraph")
        return result

    def summary(self) -> str:
        return (
            f"IRGraph: {self.node_count()} nodes, {self.edge_count()} edges, "
            f"mean_entropy={self.mean_entropy():.4f}, "
            f"compliant={self.entropy_compliant()}, "
            f"ts={self.timestamp_ns}"
        )


class IRError(Exception):
    pass


# ---------------------------------------------------------------------------
# Symbol table helpers
# ---------------------------------------------------------------------------

class SymbolTable:
    """
    Variable-length symbol table stored as length-prefixed UTF-8 strings.
    Each entry: uint16 BE length + UTF-8 bytes.
    """

    def __init__(self):
        self._symbols: list[str] = []
        self._index: dict[str, int] = {}
        self._offsets: list[int] = []
        self._current_offset = 0

    def intern(self, symbol: str) -> tuple[int, int]:
        """
        Add symbol if not present.
        Returns (offset_in_table, byte_length_of_encoded_symbol).
        """
        if symbol in self._index:
            idx = self._index[symbol]
            return self._offsets[idx], len(symbol.encode('utf-8'))

        encoded = symbol.encode('utf-8')
        offset = self._current_offset
        self._offsets.append(offset)
        self._index[symbol] = len(self._symbols)
        self._symbols.append(symbol)
        # Each entry: 2-byte length prefix + data
        self._current_offset += 2 + len(encoded)
        return offset, len(encoded)

    def encode(self) -> bytes:
        """Encode the entire symbol table to bytes."""
        out = bytearray()
        for sym in self._symbols:
            encoded = sym.encode('utf-8')
            out.extend(struct.pack('>H', len(encoded)))
            out.extend(encoded)
        return bytes(out)

    def decode_at(self, data: bytes, offset: int) -> str:
        """Decode one symbol from the table at the given byte offset."""
        if offset + 2 > len(data):
            return ''
        length = struct.unpack_from('>H', data, offset)[0]
        start = offset + 2
        if start + length > len(data):
            return ''
        return data[start:start + length].decode('utf-8', errors='replace')

    def size(self) -> int:
        return self._current_offset

    def __len__(self) -> int:
        return len(self._symbols)


# ---------------------------------------------------------------------------
# BinaryIREncoder
# ---------------------------------------------------------------------------

class BinaryIREncoder:
    """
    Encodes an IRGraph to the SOVEREIGN_IR binary format.

    Layout:
      [header 16 bytes]
      [node records: N * 32 bytes]
      [edge records: M * 16 bytes]
      [symbol table: variable]
      [Blake2b-256 checksum: 32 bytes]
    """

    def encode(self, graph: IRGraph) -> bytes:
        """Encode the full graph to bytes."""
        # Build symbol table first so we know offsets
        sym_table = SymbolTable()
        sym_offsets: list[tuple[int, int]] = []  # (offset, length)
        for node in graph.nodes:
            off, length = sym_table.intern(node.symbol)
            sym_offsets.append((off, length))

        sym_bytes = sym_table.encode()
        header = self.encode_header(graph)

        # Encode nodes
        node_bytes = bytearray()
        for i, node in enumerate(graph.nodes):
            sym_off, sym_len = sym_offsets[i]
            node_bytes.extend(self.encode_node(node, sym_off, sym_len))

        # Encode edges
        edge_bytes = bytearray()
        for edge in graph.edges:
            edge_bytes.extend(self.encode_edge(edge))

        payload = header + bytes(node_bytes) + bytes(edge_bytes) + sym_bytes

        # Compute and append checksum
        checksum = self._compute_checksum(payload)
        return payload + checksum

    def encode_header(self, graph: IRGraph) -> bytes:
        flags = IR_FLAG_CHECKSUMMED
        return IR_HEADER_STRUCT.pack(
            IR_MAGIC,
            IR_VERSION,
            flags,
            len(graph.nodes),
            len(graph.edges),
            graph.timestamp_ns & 0xFFFFFFFFFFFFFFFF,
        )

    def encode_node(self, node: IRNode, sym_offset: int, sym_len: int | None = None) -> bytes:
        """Encode a single node record (32 bytes)."""
        if sym_len is None:
            sym_len = len(node.symbol.encode('utf-8'))

        # Clamp floats to valid float32 range
        rw = self._clamp_f32(node.routing_weight)
        ent = self._clamp_f32(node.entropy)

        return IR_NODE_STRUCT.pack(
            node.node_id & 0xFFFF,
            int(node.node_type) & 0xFF,
            node.flags & 0xFF,
            rw,
            ent,
            sym_offset & 0xFFFFFFFF,
            sym_len & 0xFFFF,
            b'\x00' * 10,   # padding
        )

    def encode_edge(self, edge: IREdge) -> bytes:
        """Encode a single edge record (16 bytes)."""
        w = self._clamp_f32(edge.weight)
        return IR_EDGE_STRUCT.pack(
            edge.src_id & 0xFFFF,
            edge.dst_id & 0xFFFF,
            w,
            int(edge.edge_type) & 0xFF,
            edge.flags & 0xFF,
            b'\x00' * 6,    # padding
        )

    def encode_symbol_table(self, symbols: list[str]) -> bytes:
        """Encode a list of symbols."""
        sym_table = SymbolTable()
        for s in symbols:
            sym_table.intern(s)
        return sym_table.encode()

    def _clamp_f32(self, value: float) -> float:
        """Clamp to float32 range."""
        if math.isnan(value):
            return 0.0
        if math.isinf(value):
            return 1.0 if value > 0 else 0.0
        return max(-3.4e38, min(3.4e38, float(value)))

    def _compute_checksum(self, data: bytes) -> bytes:
        return hashlib.blake2b(data, digest_size=32).digest()


# ---------------------------------------------------------------------------
# BinaryIRDecoder
# ---------------------------------------------------------------------------

class BinaryIRDecoder:
    """
    Decodes SOVEREIGN_IR binary format to an IRGraph.
    """

    def decode(self, data: bytes) -> IRGraph:
        """Decode binary data to IRGraph."""
        if not self.verify_magic(data):
            raise IRError(f"Invalid IR magic: {data[:4]!r}")

        if len(data) < IR_HEADER_SIZE + IR_CHECKSUM_SIZE:
            raise IRError(f"Data too short: {len(data)} bytes")

        # Verify checksum (last 32 bytes)
        if not self.verify_checksum(data):
            raise IRError("IR checksum mismatch — data corrupted")

        header = self.decode_header(data)
        node_count = header['node_count']
        edge_count = header['edge_count']
        timestamp_ns = header['timestamp_ns']

        # Calculate offsets
        nodes_start = IR_HEADER_SIZE
        edges_start = nodes_start + node_count * IR_NODE_SIZE
        sym_start   = edges_start + edge_count * IR_EDGE_SIZE
        sym_end     = len(data) - IR_CHECKSUM_SIZE

        sym_table_bytes = data[sym_start:sym_end]

        # Decode nodes
        nodes = []
        for i in range(node_count):
            offset = nodes_start + i * IR_NODE_SIZE
            node = self.decode_node(data, offset, sym_table_bytes)
            nodes.append(node)

        # Decode edges
        edges = []
        for i in range(edge_count):
            offset = edges_start + i * IR_EDGE_SIZE
            edge = self.decode_edge(data, offset)
            edges.append(edge)

        return IRGraph(
            nodes=nodes,
            edges=edges,
            timestamp_ns=timestamp_ns,
        )

    def decode_header(self, data: bytes) -> dict:
        """Decode the 16-byte header."""
        magic, version, flags, node_count, edge_count, timestamp_ns = \
            IR_HEADER_STRUCT.unpack_from(data, 0)
        return {
            'magic': magic,
            'version': version,
            'flags': flags,
            'node_count': node_count,
            'edge_count': edge_count,
            'timestamp_ns': timestamp_ns,
        }

    def decode_node(self, data: bytes, offset: int, sym_table: bytes) -> IRNode:
        """Decode a 32-byte node record."""
        node_id, node_type, flags, routing_weight, entropy, \
            symbol_offset, symbol_len, _padding = \
            IR_NODE_STRUCT.unpack_from(data, offset)

        # Decode symbol from symbol table
        symbol = self._decode_symbol(sym_table, symbol_offset, symbol_len)

        return IRNode(
            node_id=node_id,
            node_type=IRNodeType(node_type % len(IRNodeType)),
            flags=flags,
            routing_weight=float(routing_weight),
            entropy=float(entropy),
            symbol=symbol,
        )

    def decode_edge(self, data: bytes, offset: int) -> IREdge:
        """Decode a 16-byte edge record."""
        src_id, dst_id, weight, edge_type, flags, _padding = \
            IR_EDGE_STRUCT.unpack_from(data, offset)

        return IREdge(
            src_id=src_id,
            dst_id=dst_id,
            weight=float(weight),
            edge_type=IREdgeType(edge_type % len(IREdgeType)),
            flags=flags,
        )

    def _decode_symbol(self, sym_table: bytes, offset: int, length: int) -> str:
        """Decode symbol from the symbol table at given offset."""
        if not sym_table or offset + 2 > len(sym_table):
            return ''
        stored_len = struct.unpack_from('>H', sym_table, offset)[0]
        start = offset + 2
        if start + stored_len > len(sym_table):
            return ''
        raw = sym_table[start:start + stored_len]
        return raw.decode('utf-8', errors='replace')

    def verify_magic(self, data: bytes) -> bool:
        return len(data) >= 4 and data[:4] == IR_MAGIC

    def verify_checksum(self, data: bytes) -> bool:
        """Verify Blake2b checksum (last 32 bytes)."""
        if len(data) < IR_CHECKSUM_SIZE:
            return False
        payload = data[:-IR_CHECKSUM_SIZE]
        expected = data[-IR_CHECKSUM_SIZE:]
        computed = hashlib.blake2b(payload, digest_size=32).digest()
        return computed == expected

    def decode_raw_header(self, data: bytes) -> tuple[int, int, int, int, int]:
        """Returns (version, flags, node_count, edge_count, timestamp_ns)."""
        h = self.decode_header(data)
        return h['version'], h['flags'], h['node_count'], h['edge_count'], h['timestamp_ns']


# ---------------------------------------------------------------------------
# IRBuilder — fluent graph construction
# ---------------------------------------------------------------------------

class IRBuilder:
    """
    Fluent builder for constructing IRGraph instances.

    Manages auto-incrementing IDs and entropy validation.
    """

    def __init__(self):
        self._graph = IRGraph()
        self._next_id = 0

    def add_intent(
        self,
        symbol: str,
        routing_weight: float = 1.0,
        entropy: float = 0.0,
        flags: int = 0,
    ) -> int:
        """Add an INTENT node. Returns node_id."""
        return self._add_node(IRNodeType.INTENT, symbol, routing_weight, entropy, flags)

    def add_entity(
        self,
        symbol: str,
        routing_weight: float = 1.0,
        entropy: float = 0.0,
        flags: int = 0,
    ) -> int:
        return self._add_node(IRNodeType.ENTITY, symbol, routing_weight, entropy, flags)

    def add_operator(
        self,
        symbol: str,
        routing_weight: float = 1.0,
        entropy: float = 0.0,
        flags: int = 0,
    ) -> int:
        return self._add_node(IRNodeType.OPERATOR, symbol, routing_weight, entropy, flags)

    def add_constraint(
        self,
        symbol: str,
        routing_weight: float = 0.8,
        entropy: float = 0.0,
        flags: int = 0,
    ) -> int:
        return self._add_node(IRNodeType.CONSTRAINT, symbol, routing_weight, entropy, flags)

    def add_payload(
        self,
        symbol: str,
        routing_weight: float = 0.5,
        entropy: float = 0.0,
        flags: int = 0,
    ) -> int:
        return self._add_node(IRNodeType.PAYLOAD, symbol, routing_weight, entropy, flags)

    def _add_node(
        self,
        node_type: IRNodeType,
        symbol: str,
        routing_weight: float,
        entropy: float,
        flags: int,
    ) -> int:
        nid = self._next_id
        self._next_id += 1
        node = IRNode(
            node_id=nid,
            node_type=node_type,
            flags=flags,
            routing_weight=routing_weight,
            entropy=entropy,
            symbol=symbol,
        )
        self._graph.add_node(node)
        return nid

    def connect(
        self,
        src_id: int,
        dst_id: int,
        weight: float = 1.0,
        edge_type: IREdgeType = IREdgeType.PARENT_CHILD,
        flags: int = 0,
    ) -> 'IRBuilder':
        """Add a directed edge."""
        self._graph.add_edge(IREdge(
            src_id=src_id,
            dst_id=dst_id,
            weight=weight,
            edge_type=edge_type,
            flags=flags,
        ))
        return self

    def build(self) -> IRGraph:
        return self._graph

    def reset(self) -> 'IRBuilder':
        self._graph = IRGraph()
        self._next_id = 0
        return self


# ---------------------------------------------------------------------------
# ASTParseToBinaryIR — converts parser output to IR
# ---------------------------------------------------------------------------

class ASTParseToBinaryIR:
    """
    Converts parse results and routing traces to IRGraph.

    Handles both Python AST nodes (via ast module) and the sovereign
    routing.parser.ParseResult / routing.pipeline.PipelineTrace shapes.
    """

    def from_parse_result(self, parse: Any) -> IRGraph:
        """
        Convert a ParseResult-shaped object to IRGraph.

        Expected parse result shape:
          parse.intent: str
          parse.entities: list[str]
          parse.operators: list[str]
          parse.constraints: list[str]
          parse.payload: Any
        """
        builder = IRBuilder()

        intent_str = getattr(parse, 'intent', str(parse))
        intent_id = builder.add_intent(intent_str, routing_weight=1.0, entropy=0.05)

        for ent in getattr(parse, 'entities', []):
            eid = builder.add_entity(str(ent), entropy=0.02)
            builder.connect(intent_id, eid, edge_type=IREdgeType.PARENT_CHILD)

        for op in getattr(parse, 'operators', []):
            oid = builder.add_operator(str(op), entropy=0.0)
            builder.connect(intent_id, oid, edge_type=IREdgeType.SIBLING)

        for con in getattr(parse, 'constraints', []):
            cid = builder.add_constraint(str(con), entropy=0.0,
                                          flags=IR_NODE_FLAG_SEALED)
            builder.connect(intent_id, cid, edge_type=IREdgeType.CROSS_REF)

        payload = getattr(parse, 'payload', None)
        if payload is not None:
            pid = builder.add_payload(str(payload), entropy=0.10)
            builder.connect(intent_id, pid, edge_type=IREdgeType.PARENT_CHILD)

        return builder.build()

    def from_routing_trace(self, trace: Any) -> IRGraph:
        """
        Convert a PipelineTrace-shaped object to IRGraph.

        Expected trace shape:
          trace.steps: list of objects with .name, .opcode, .result, .entropy
          trace.pipeline_id: str
        """
        builder = IRBuilder()

        pipeline_id = getattr(trace, 'pipeline_id', 'pipeline')
        root_id = builder.add_intent(pipeline_id, routing_weight=1.0)

        for step in getattr(trace, 'steps', []):
            step_name = getattr(step, 'name', str(step))
            step_entropy = float(getattr(step, 'entropy', 0.0))
            step_opcode = int(getattr(step, 'opcode', 0))

            # Encode opcode into routing weight
            routing_weight = (step_opcode % 256) / 255.0

            nid = builder.add_operator(
                step_name,
                routing_weight=routing_weight,
                entropy=step_entropy,
            )
            builder.connect(root_id, nid, weight=1.0 - step_entropy)

        return builder.build()

    def from_ast(self, tree: Any, filename: str = '<unknown>') -> IRGraph:
        """
        Convert a Python ast.Module or ast.expr to IRGraph.
        Each AST node becomes an IRNode; child relationships become edges.
        """
        import ast
        builder = IRBuilder()
        visited: dict[int, int] = {}  # id(ast_node) -> ir_node_id

        def visit(node: Any, parent_ir_id: int | None = None) -> int:
            node_id_key = id(node)
            if node_id_key in visited:
                return visited[node_id_key]

            class_name = type(node).__name__
            node_type = _ast_class_to_ir_type(class_name)
            entropy = _estimate_ast_entropy(node)

            nid = builder._add_node(node_type, class_name, 0.5, entropy, 0)
            visited[node_id_key] = nid

            if parent_ir_id is not None:
                builder.connect(parent_ir_id, nid, edge_type=IREdgeType.PARENT_CHILD)

            for child in ast.iter_child_nodes(node):
                visit(child, nid)

            return nid

        if hasattr(tree, 'body'):  # ast.Module
            root_id = builder.add_intent(filename, routing_weight=1.0)
            for stmt in tree.body:
                visit(stmt, root_id)
        else:
            visit(tree, None)

        return builder.build()


def _ast_class_to_ir_type(class_name: str) -> IRNodeType:
    INTENT_NODES = {'Module', 'FunctionDef', 'AsyncFunctionDef', 'ClassDef'}
    OPERATOR_NODES = {'BinOp', 'UnaryOp', 'BoolOp', 'Compare', 'Call', 'Assign',
                      'AugAssign', 'Return', 'Yield'}
    CONSTRAINT_NODES = {'If', 'While', 'For', 'Try', 'With', 'Assert'}
    PAYLOAD_NODES = {'Constant', 'Name', 'Attribute', 'Subscript', 'Starred'}

    if class_name in INTENT_NODES:
        return IRNodeType.INTENT
    elif class_name in OPERATOR_NODES:
        return IRNodeType.OPERATOR
    elif class_name in CONSTRAINT_NODES:
        return IRNodeType.CONSTRAINT
    elif class_name in PAYLOAD_NODES:
        return IRNodeType.PAYLOAD
    return IRNodeType.ENTITY


def _estimate_ast_entropy(node: Any) -> float:
    """Estimate entropy for an AST node (lower = more deterministic)."""
    import ast
    child_count = sum(1 for _ in ast.iter_child_nodes(node))
    # Entropy rises with branching factor
    if child_count == 0:
        return 0.01
    elif child_count <= 2:
        return 0.05
    elif child_count <= 5:
        return 0.10
    elif child_count <= 10:
        return 0.15
    else:
        return 0.19  # Stay below 0.20


# ---------------------------------------------------------------------------
# IRDiff — compare two IRGraphs
# ---------------------------------------------------------------------------

class IRDiff:
    """Compute structural differences between two IRGraphs."""

    def diff(self, a: IRGraph, b: IRGraph) -> dict:
        """Return a dict describing differences."""
        added_nodes = []
        removed_nodes = []
        changed_nodes = []

        a_nodes = {n.node_id: n for n in a.nodes}
        b_nodes = {n.node_id: n for n in b.nodes}

        for nid, node in b_nodes.items():
            if nid not in a_nodes:
                added_nodes.append(nid)
            else:
                a_node = a_nodes[nid]
                if (a_node.node_type != node.node_type
                        or a_node.symbol != node.symbol
                        or abs(a_node.routing_weight - node.routing_weight) > 1e-6):
                    changed_nodes.append(nid)

        for nid in a_nodes:
            if nid not in b_nodes:
                removed_nodes.append(nid)

        a_edges = {(e.src_id, e.dst_id) for e in a.edges}
        b_edges = {(e.src_id, e.dst_id) for e in b.edges}
        added_edges = list(b_edges - a_edges)
        removed_edges = list(a_edges - b_edges)

        return {
            'added_nodes': added_nodes,
            'removed_nodes': removed_nodes,
            'changed_nodes': changed_nodes,
            'added_edges': added_edges,
            'removed_edges': removed_edges,
            'structurally_equal': (
                not added_nodes and not removed_nodes and
                not changed_nodes and not added_edges and not removed_edges
            ),
        }


# ---------------------------------------------------------------------------
# IRSerializer — JSON-compatible dict output
# ---------------------------------------------------------------------------

class IRSerializer:
    """Convert IRGraph to/from JSON-serializable dicts."""

    def to_dict(self, graph: IRGraph) -> dict:
        return {
            'timestamp_ns': graph.timestamp_ns,
            'nodes': [n.to_dict() for n in graph.nodes],
            'edges': [e.to_dict() for e in graph.edges],
        }

    def from_dict(self, d: dict) -> IRGraph:
        nodes = [
            IRNode(
                node_id=n['node_id'],
                node_type=IRNodeType[n['node_type']],
                flags=n['flags'],
                routing_weight=n['routing_weight'],
                entropy=n['entropy'],
                symbol=n['symbol'],
            )
            for n in d.get('nodes', [])
        ]
        edges = [
            IREdge(
                src_id=e['src_id'],
                dst_id=e['dst_id'],
                weight=e['weight'],
                edge_type=IREdgeType[e['edge_type']],
                flags=e['flags'],
            )
            for e in d.get('edges', [])
        ]
        return IRGraph(
            nodes=nodes,
            edges=edges,
            timestamp_ns=d.get('timestamp_ns', time.time_ns()),
        )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    # Build a simple graph
    builder = IRBuilder()
    root = builder.add_intent("route:tool_dispatch", routing_weight=1.0, entropy=0.05)
    e1 = builder.add_entity("tool:read_file", routing_weight=0.9, entropy=0.02)
    e2 = builder.add_entity("tool:write_file", routing_weight=0.8, entropy=0.02)
    op = builder.add_operator("op:dispatch", entropy=0.0)
    builder.connect(root, e1)
    builder.connect(root, e2)
    builder.connect(op, root, edge_type=IREdgeType.CROSS_REF)
    graph = builder.build()

    assert graph.node_count() == 4
    assert graph.edge_count() == 3
    assert graph.entropy_compliant()

    # Encode
    encoder = BinaryIREncoder()
    data = encoder.encode(graph)
    assert data[:4] == IR_MAGIC
    assert len(data) > IR_HEADER_SIZE + IR_CHECKSUM_SIZE

    # Decode
    decoder = BinaryIRDecoder()
    assert decoder.verify_magic(data)
    assert decoder.verify_checksum(data)

    restored = decoder.decode(data)
    assert restored.node_count() == graph.node_count()
    assert restored.edge_count() == graph.edge_count()
    assert restored.nodes[0].symbol == "route:tool_dispatch"
    assert restored.nodes[0].node_type == IRNodeType.INTENT
    assert abs(restored.nodes[0].entropy - 0.05) < 1e-5

    # Diff
    diff_tool = IRDiff()
    result = diff_tool.diff(graph, restored)
    assert result['structurally_equal']

    # Serialization
    ser = IRSerializer()
    d = ser.to_dict(graph)
    restored2 = ser.from_dict(d)
    assert restored2.node_count() == graph.node_count()

    # Symbol table
    st = SymbolTable()
    off1, _ = st.intern("hello")
    off2, _ = st.intern("world")
    assert off1 == 0
    encoded = st.encode()
    assert decoder._decode_symbol(encoded, off1, 5) == "hello"
    assert decoder._decode_symbol(encoded, off2, 5) == "world"

    return True


# ---------------------------------------------------------------------------
# IROptimizer — graph optimization passes
# ---------------------------------------------------------------------------

class IROptimizer:
    """
    Optimization passes for IRGraph:
      1. Dead node elimination (nodes with no incoming/outgoing edges)
      2. Entropy clamping (clamp entropy to <= 0.20)
      3. Weight normalization (normalize all edge weights to [0,1])
      4. Redundant edge removal (duplicate src->dst edges)
      5. Constant propagation (nodes with same symbol -> shared reference)
    """

    def optimize(self, graph: IRGraph, passes: int = 3) -> tuple[IRGraph, dict]:
        """Apply all optimization passes; return (optimized graph, stats)."""
        stats = {
            'dead_removed': 0,
            'entropy_clamped': 0,
            'edges_removed': 0,
            'weights_normalized': 0,
        }
        current = graph
        for _ in range(passes):
            current, s = self._single_pass(current)
            for k in stats:
                stats[k] += s.get(k, 0)
        return current, stats

    def _single_pass(self, graph: IRGraph) -> tuple[IRGraph, dict]:
        stats: dict[str, int] = {}

        # Pass 1: clamp entropy
        nodes = []
        clamped = 0
        for node in graph.nodes:
            if node.entropy > 0.20:
                node = IRNode(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    flags=node.flags,
                    routing_weight=node.routing_weight,
                    entropy=min(node.entropy, 0.20),
                    symbol=node.symbol,
                )
                clamped += 1
            nodes.append(node)
        stats['entropy_clamped'] = clamped

        # Pass 2: remove duplicate edges
        seen_edges: set[tuple[int, int]] = set()
        edges = []
        dup = 0
        for edge in graph.edges:
            key = (edge.src_id, edge.dst_id)
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append(edge)
            else:
                dup += 1
        stats['edges_removed'] = dup

        # Pass 3: remove truly dead nodes (no edges at all)
        connected_ids: set[int] = set()
        for e in edges:
            connected_ids.add(e.src_id)
            connected_ids.add(e.dst_id)
        # Always keep nodes even if isolated — connectivity is optional
        # (only remove if flagged EPHEMERAL and truly isolated)
        live_nodes = []
        dead = 0
        for node in nodes:
            is_isolated = node.node_id not in connected_ids
            is_ephemeral = bool(node.flags & IR_NODE_FLAG_EPHEMERAL)
            if is_isolated and is_ephemeral and len(nodes) > 1:
                dead += 1
            else:
                live_nodes.append(node)
        stats['dead_removed'] = dead

        # Pass 4: normalize edge weights to [0,1]
        if edges:
            max_w = max(e.weight for e in edges)
            if max_w > 1.0:
                edges = [
                    IREdge(
                        src_id=e.src_id, dst_id=e.dst_id,
                        weight=e.weight / max_w,
                        edge_type=e.edge_type, flags=e.flags,
                    )
                    for e in edges
                ]
                stats['weights_normalized'] = len(edges)

        return IRGraph(nodes=live_nodes, edges=edges, timestamp_ns=graph.timestamp_ns), stats

    def fold_constants(self, graph: IRGraph) -> tuple[IRGraph, int]:
        """
        Fold nodes that have identical symbols into a single representative.
        All edges pointing to duplicates are redirected to the canonical node.
        Returns (new graph, number of folds).
        """
        symbol_to_canonical: dict[str, int] = {}
        id_remap: dict[int, int] = {}
        live_nodes = []
        folds = 0

        for node in graph.nodes:
            key = f"{node.node_type.value}:{node.symbol}"
            if key in symbol_to_canonical:
                id_remap[node.node_id] = symbol_to_canonical[key]
                folds += 1
            else:
                symbol_to_canonical[key] = node.node_id
                id_remap[node.node_id] = node.node_id
                live_nodes.append(node)

        # Remap edges
        edges = []
        seen: set[tuple[int, int]] = set()
        for e in graph.edges:
            src = id_remap.get(e.src_id, e.src_id)
            dst = id_remap.get(e.dst_id, e.dst_id)
            if src == dst:
                continue
            key = (src, dst)
            if key not in seen:
                seen.add(key)
                edges.append(IREdge(
                    src_id=src, dst_id=dst,
                    weight=e.weight, edge_type=e.edge_type, flags=e.flags,
                ))

        return IRGraph(nodes=live_nodes, edges=edges, timestamp_ns=graph.timestamp_ns), folds


# ---------------------------------------------------------------------------
# IRMerger — merge multiple IRGraphs
# ---------------------------------------------------------------------------

class IRMerger:
    """
    Merges multiple IRGraphs into a single graph.
    Handles ID conflicts by remapping node IDs.
    """

    def merge(self, *graphs: IRGraph) -> IRGraph:
        """Merge all provided graphs; remap IDs to avoid conflicts."""
        all_nodes: list[IRNode] = []
        all_edges: list[IREdge] = []
        id_offset = 0

        for graph in graphs:
            # Find max existing ID
            max_id = max((n.node_id for n in all_nodes), default=-1)
            id_offset = max_id + 1

            # Remap nodes
            for node in graph.nodes:
                new_node = IRNode(
                    node_id=node.node_id + id_offset,
                    node_type=node.node_type,
                    flags=node.flags,
                    routing_weight=node.routing_weight,
                    entropy=node.entropy,
                    symbol=node.symbol,
                )
                all_nodes.append(new_node)

            # Remap edges
            for edge in graph.edges:
                new_edge = IREdge(
                    src_id=edge.src_id + id_offset,
                    dst_id=edge.dst_id + id_offset,
                    weight=edge.weight,
                    edge_type=edge.edge_type,
                    flags=edge.flags,
                )
                all_edges.append(new_edge)

        return IRGraph(nodes=all_nodes, edges=all_edges)

    def merge_with_bridge(
        self,
        a: IRGraph,
        b: IRGraph,
        a_root: int,
        b_root: int,
        bridge_weight: float = 0.5,
    ) -> IRGraph:
        """
        Merge two graphs and add a bridging edge from a's root to b's root.
        """
        merged = self.merge(a, b)

        # Find the remapped IDs of the roots
        a_nodes_max = len(a.nodes) - 1
        a_root_new = a_root  # a is the first, no offset
        b_root_new = b_root + max(n.node_id for n in a.nodes) + 1 if a.nodes else b_root

        bridge = IREdge(
            src_id=a_root_new,
            dst_id=b_root_new,
            weight=bridge_weight,
            edge_type=IREdgeType.CROSS_REF,
            flags=IR_EDGE_FLAG_CRITICAL,
        )
        merged.edges.append(bridge)
        return merged


# ---------------------------------------------------------------------------
# IRWORMSeal — cryptographic sealing of IR graphs
# ---------------------------------------------------------------------------

class IRWORMSeal:
    """
    Cryptographically seals an IRGraph for WORM commitment.
    Uses Blake2b-256 over the binary-encoded graph body.
    """

    def seal(self, graph: IRGraph) -> dict:
        """
        Encode and seal the graph.
        Returns dict with 'data', 'checksum', 'timestamp_ns', 'node_count'.
        """
        encoder = BinaryIREncoder()
        data = encoder.encode(graph)
        checksum = hashlib.blake2b(data, digest_size=32).digest()
        return {
            'data': data,
            'checksum': checksum.hex(),
            'timestamp_ns': graph.timestamp_ns,
            'node_count': graph.node_count(),
            'edge_count': graph.edge_count(),
            'size_bytes': len(data),
            'mean_entropy': graph.mean_entropy(),
            'compliant': graph.entropy_compliant(),
        }

    def verify_seal(self, data: bytes, expected_checksum: str) -> bool:
        """Verify a sealed graph's checksum."""
        actual = hashlib.blake2b(data[:-32], digest_size=32).hexdigest()
        return actual == expected_checksum

    def seal_node(self, node: IRNode) -> str:
        """Compute a Blake2b fingerprint for a single node."""
        payload = (
            f"{node.node_id}:{node.node_type.value}:"
            f"{node.symbol}:{node.routing_weight:.6f}:{node.entropy:.6f}"
        ).encode('utf-8')
        return hashlib.blake2b(payload, digest_size=16).hexdigest()


# ---------------------------------------------------------------------------
# IRQueryEngine — query nodes and edges by predicates
# ---------------------------------------------------------------------------

class IRQueryEngine:
    """
    Query interface for IRGraph: filter nodes/edges by type, entropy, weight, symbol.
    """

    def __init__(self, graph: IRGraph):
        self._graph = graph

    def nodes_of_type(self, node_type: IRNodeType) -> list[IRNode]:
        return [n for n in self._graph.nodes if n.node_type == node_type]

    def nodes_by_entropy(self, max_entropy: float = 0.20) -> list[IRNode]:
        return [n for n in self._graph.nodes if n.entropy <= max_entropy]

    def nodes_by_symbol_prefix(self, prefix: str) -> list[IRNode]:
        return [n for n in self._graph.nodes if n.symbol.startswith(prefix)]

    def nodes_above_weight(self, min_weight: float) -> list[IRNode]:
        return [n for n in self._graph.nodes if n.routing_weight >= min_weight]

    def edges_from(self, src_id: int) -> list[IREdge]:
        return [e for e in self._graph.edges if e.src_id == src_id]

    def edges_to(self, dst_id: int) -> list[IREdge]:
        return [e for e in self._graph.edges if e.dst_id == dst_id]

    def edges_of_type(self, edge_type: IREdgeType) -> list[IREdge]:
        return [e for e in self._graph.edges if e.edge_type == edge_type]

    def shortest_path(self, src_id: int, dst_id: int) -> list[int]:
        """BFS shortest path between two node IDs. Returns list of node IDs."""
        if src_id == dst_id:
            return [src_id]

        adj = self._graph.to_adjacency_list()
        visited = {src_id}
        queue = [[src_id]]

        while queue:
            path = queue.pop(0)
            node = path[-1]
            for neighbor in adj.get(node, []):
                if neighbor == dst_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return []  # no path found

    def reachable_from(self, src_id: int) -> set[int]:
        """Return set of all node IDs reachable from src_id by DFS."""
        adj = self._graph.to_adjacency_list()
        visited: set[int] = set()
        stack = [src_id]
        while stack:
            node = stack.pop()
            if node not in visited:
                visited.add(node)
                for neighbor in adj.get(node, []):
                    if neighbor not in visited:
                        stack.append(neighbor)
        return visited

    def critical_path(self) -> list[int]:
        """
        Find the critical (highest-weight) path in the graph.
        Uses topological sort + dynamic programming.
        """
        try:
            order = self._graph.topological_sort()
        except IRError:
            return []

        if not order:
            return []

        # Weight of best path ending at each node
        best: dict[int, float] = {nid: 0.0 for nid in order}
        prev: dict[int, Optional[int]] = {nid: None for nid in order}

        for nid in order:
            node = self._graph.get_node(nid)
            if node:
                node_w = node.routing_weight
            else:
                node_w = 0.0
            for edge in self.edges_to(nid):
                candidate = best.get(edge.src_id, 0.0) + edge.weight + node_w
                if candidate > best[nid]:
                    best[nid] = candidate
                    prev[nid] = edge.src_id

        # Reconstruct path to max
        end = max(best, key=lambda k: best[k])
        path = []
        current: Optional[int] = end
        while current is not None:
            path.append(current)
            current = prev.get(current)
        return list(reversed(path))

    def entropy_violation_nodes(self) -> list[IRNode]:
        return [n for n in self._graph.nodes if n.entropy > 0.20]

    def high_degree_nodes(self, min_degree: int = 3) -> list[tuple[IRNode, int]]:
        """Return (node, degree) pairs for nodes with degree >= min_degree."""
        degree: dict[int, int] = {}
        for e in self._graph.edges:
            degree[e.src_id] = degree.get(e.src_id, 0) + 1
            degree[e.dst_id] = degree.get(e.dst_id, 0) + 1
        result = []
        for node in self._graph.nodes:
            d = degree.get(node.node_id, 0)
            if d >= min_degree:
                result.append((node, d))
        return sorted(result, key=lambda x: -x[1])


# ---------------------------------------------------------------------------
# IRSchemaValidator — validate IR graphs against a schema
# ---------------------------------------------------------------------------

@dataclass
class IRSchema:
    """Defines constraints that an IRGraph must satisfy."""
    max_nodes: int = 65535
    max_edges: int = 65535
    max_entropy: float = 0.20
    require_root: bool = True
    allow_cycles: bool = False
    min_routing_weight: float = 0.0
    required_node_types: list[IRNodeType] = field(default_factory=list)
    forbidden_symbols: list[str] = field(default_factory=list)


class IRSchemaValidator:
    """Validates an IRGraph against an IRSchema."""

    def validate(self, graph: IRGraph, schema: IRSchema) -> list[str]:
        """Return list of validation errors (empty if valid)."""
        errors = []

        if graph.node_count() > schema.max_nodes:
            errors.append(
                f"Too many nodes: {graph.node_count()} > {schema.max_nodes}"
            )

        if graph.edge_count() > schema.max_edges:
            errors.append(
                f"Too many edges: {graph.edge_count()} > {schema.max_edges}"
            )

        for node in graph.nodes:
            if node.entropy > schema.max_entropy:
                errors.append(
                    f"Node {node.node_id} ({node.symbol!r}) "
                    f"entropy {node.entropy:.4f} > {schema.max_entropy}"
                )
            if node.routing_weight < schema.min_routing_weight:
                errors.append(
                    f"Node {node.node_id} routing_weight "
                    f"{node.routing_weight:.4f} < {schema.min_routing_weight}"
                )
            for forbidden in schema.forbidden_symbols:
                if forbidden in node.symbol:
                    errors.append(
                        f"Node {node.node_id} contains forbidden symbol: {forbidden!r}"
                    )

        if schema.required_node_types:
            present_types = {n.node_type for n in graph.nodes}
            for req_type in schema.required_node_types:
                if req_type not in present_types:
                    errors.append(f"Required node type missing: {req_type.name}")

        if schema.require_root and graph.nodes:
            # Check for at least one node with no incoming edges
            has_root = any(
                not any(e.dst_id == node.node_id for e in graph.edges)
                for node in graph.nodes
            )
            if not has_root:
                errors.append("No root node found (all nodes have incoming edges)")

        if not schema.allow_cycles and graph.nodes:
            try:
                graph.topological_sort()
            except IRError:
                errors.append("Cycle detected in graph (cycles not allowed)")

        return errors

    def is_valid(self, graph: IRGraph, schema: IRSchema) -> bool:
        return len(self.validate(graph, schema)) == 0


# ---------------------------------------------------------------------------
# Default schema for sovereign routing
# ---------------------------------------------------------------------------

SOVEREIGN_IR_SCHEMA = IRSchema(
    max_nodes=4096,
    max_edges=16384,
    max_entropy=0.20,
    require_root=True,
    allow_cycles=False,
    min_routing_weight=0.0,
    required_node_types=[IRNodeType.INTENT],
    forbidden_symbols=[],
)


if __name__ == "__main__":
    assert _self_test(), "Self-test failed"
    print("binary_ir.py: all self-tests passed")

    # Demo: encode a simple routing graph
    b = IRBuilder()
    root = b.add_intent("dispatch:agent_farm", routing_weight=1.0, entropy=0.05)
    for i, tool in enumerate(["read", "write", "search", "commit"]):
        nid = b.add_entity(f"tool:{tool}", routing_weight=0.9 - i * 0.1, entropy=0.02)
        b.connect(root, nid)
    graph = b.build()

    encoder = BinaryIREncoder()
    data = encoder.encode(graph)
    print(f"Encoded graph: {len(data)} bytes")
    print(f"Header: {BinaryIRDecoder().decode_header(data)}")

    restored = BinaryIRDecoder().decode(data)
    print(f"Restored: {restored.summary()}")

    # Demo: optimizer
    opt = IROptimizer()
    optimized, stats = opt.optimize(graph)
    print(f"\nOptimizer stats: {stats}")

    # Demo: query engine
    qe = IRQueryEngine(graph)
    intents = qe.nodes_of_type(IRNodeType.INTENT)
    print(f"Intent nodes: {[n.symbol for n in intents]}")
    entities = qe.nodes_of_type(IRNodeType.ENTITY)
    print(f"Entity nodes: {[n.symbol for n in entities]}")
    path = qe.shortest_path(root, entities[0].node_id if entities else root)
    print(f"Path root->first entity: {path}")

    # Demo: schema validation
    validator = IRSchemaValidator()
    errors = validator.validate(graph, SOVEREIGN_IR_SCHEMA)
    print(f"\nSchema validation: {'PASS' if not errors else 'FAIL'}")
    if errors:
        for e in errors:
            print(f"  - {e}")

    # Demo: WORM seal
    seal = IRWORMSeal()
    sealed = seal.seal(graph)
    print(f"\nWORM seal: {sealed['checksum'][:16]}...")
    print(f"Seal stats: {sealed['size_bytes']} bytes, compliant={sealed['compliant']}")
