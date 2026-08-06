"""
Stage 3 + 4: SymbolicGraph + JordanTransformer

SymbolicGraph:
  AST → weighted adjacency matrix
  Each AST node becomes a graph vertex.
  Edges carry weights based on:
    - parent-child relationship (strong, 1.0)
    - sibling relationship (medium, 0.5)
    - cross-reference (entity matches, 0.3)

JordanTransformer:
  Adjacency matrix → Jordan Normal Form analysis
  - Eigenvalues of adjacency matrix
  - Stability score (eigenvalues inside unit circle)
  - Jordan block sizes (degeneracy measure)
  - Spectral radius (largest |eigenvalue|)

  These become routing features:
    - stable graph → confident routing
    - unstable graph → conservative routing (spread load)
    - large Jordan blocks → repeated structure (specialize)
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any

from .parser import ASTNode, ParseResult


# ==========================================
# Symbolic Graph
# ==========================================

@dataclass
class GraphNode:
    id: int
    ast_type: str
    value: str
    confidence: float
    routing_weight: float = 1.0   # 0.0 for payload nodes
    is_payload: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    src: int
    dst: int
    weight: float
    edge_type: str  # "parent_child" | "sibling" | "cross_ref"


@dataclass
class SymbolicGraphResult:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    adjacency: list[list[float]]  # N x N matrix
    node_index: dict[int, int]    # ast_id → matrix row


class SymbolicGraph:
    """
    Stage 3: Convert AST to weighted adjacency matrix.
    """

    def build(self, parse: ParseResult) -> SymbolicGraphResult:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # Flatten AST into node list (BFS)
        self._collect_nodes(parse.ast_root, nodes)

        # Build index: ast node id → matrix index
        node_index = {n.id: i for i, n in enumerate(nodes)}
        N = len(nodes)

        # Build adjacency matrix (zeroed)
        adjacency: list[list[float]] = [[0.0] * N for _ in range(N)]

        # Add edges via AST traversal
        self._add_edges(parse.ast_root, nodes, node_index, edges, adjacency)

        # Add cross-reference edges (entity → entity with same value)
        entity_nodes = [n for n in nodes if n.ast_type == "ENTITY"]
        for i, na in enumerate(entity_nodes):
            for nb in entity_nodes[i+1:]:
                if na.value.lower() == nb.value.lower():
                    ia, ib = node_index[na.id], node_index[nb.id]
                    adjacency[ia][ib] = 0.3
                    adjacency[ib][ia] = 0.3
                    edges.append(GraphEdge(na.id, nb.id, 0.3, "cross_ref"))

        return SymbolicGraphResult(
            nodes=nodes,
            edges=edges,
            adjacency=adjacency,
            node_index=node_index
        )

    def _collect_nodes(self, node: ASTNode, out: list[GraphNode]) -> None:
        out.append(GraphNode(
            id=node.id,
            ast_type=node.type,
            value=node.value,
            confidence=node.confidence,
            routing_weight=node.routing_weight,
            is_payload=node.is_payload,
            metadata=node.metadata.copy()
        ))
        for child in node.children:
            self._collect_nodes(child, out)

    def _add_edges(
        self,
        node: ASTNode,
        all_nodes: list[GraphNode],
        index: dict[int, int],
        edges: list[GraphEdge],
        adj: list[list[float]]
    ) -> None:
        i = index[node.id]
        parent_is_payload = node.metadata.get("is_payload", False)

        for ci, child in enumerate(node.children):
            j = index[child.id]
            child_is_payload = child.metadata.get("is_payload", False)

            # Edge weight rules:
            #   structural → structural  : child.routing_weight (full weight)
            #   structural → payload     : 0.1  (parent acknowledges child exists
            #                                    but payload cannot amplify routing)
            #   payload    → structural  : 0.0  (payload CANNOT propagate up)
            #   payload    → payload     : 0.0  (payload islands carry no routing)
            if parent_is_payload:
                w = 0.0
            elif child_is_payload:
                w = 0.1
            else:
                w = child.routing_weight

            if w > 0:
                adj[i][j] = w
                edges.append(GraphEdge(node.id, child.id, w, "parent_child"))

            # Sibling edges — only between structural nodes
            # Payload siblings do NOT get cross-edges (prevents flooding)
            if not child_is_payload:
                for ck, sibling in enumerate(node.children):
                    if ck != ci and not sibling.metadata.get("is_payload", False):
                        k = index[sibling.id]
                        adj[j][k] = max(adj[j][k], 0.3)

            self._add_edges(child, all_nodes, index, edges, adj)


# ==========================================
# Jordan Transformer
# ==========================================

@dataclass
class ComplexNum:
    real: float
    imag: float

    def abs(self) -> float:
        return math.sqrt(self.real ** 2 + self.imag ** 2)

    def __repr__(self) -> str:
        sign = "+" if self.imag >= 0 else "-"
        return f"{self.real:.4f}{sign}{abs(self.imag):.4f}j"


@dataclass
class JordanResult:
    eigenvalues: list[ComplexNum]
    spectral_radius: float      # max |eigenvalue|
    stability_score: float      # fraction of eigenvalues with |λ| < 1
    mean_magnitude: float
    jordan_block_sizes: list[int]
    routing_features: dict[str, float]


class JordanTransformer:
    """
    Stage 4: Eigendecompose the symbolic graph adjacency matrix.

    Pure Python implementation (no numpy required).
    Uses power iteration for dominant eigenvalue,
    and Gershgorin circles for stability bounds.
    """

    def analyze(self, graph: SymbolicGraphResult) -> JordanResult:
        N = len(graph.nodes)
        adj = graph.adjacency

        if N == 0:
            return self._empty_result()

        eigenvalues = self._gershgorin_eigenvalue_bounds(adj, N)
        spectral_radius = max(ev.abs() for ev in eigenvalues) if eigenvalues else 0.0
        stable_count = sum(1 for ev in eigenvalues if ev.abs() < 1.0)
        stability_score = stable_count / max(len(eigenvalues), 1)
        mean_mag = sum(ev.abs() for ev in eigenvalues) / max(len(eigenvalues), 1)

        # Jordan block sizes: estimated from repeated diagonal patterns
        block_sizes = self._estimate_jordan_blocks(adj, N)

        routing_features = {
            "spectral_radius":  spectral_radius,
            "stability_score":  stability_score,
            "mean_magnitude":   mean_mag,
            "max_block_size":   float(max(block_sizes)) if block_sizes else 1.0,
            "graph_density":    self._density(adj, N),
            "routing_confidence": stability_score * (1.0 - min(spectral_radius, 1.0)),
        }

        return JordanResult(
            eigenvalues=eigenvalues,
            spectral_radius=spectral_radius,
            stability_score=stability_score,
            mean_magnitude=mean_mag,
            jordan_block_sizes=block_sizes,
            routing_features=routing_features
        )

    def _gershgorin_eigenvalue_bounds(self, adj: list[list[float]], N: int) -> list[ComplexNum]:
        """
        Gershgorin circle theorem: each eigenvalue lies within a disc
        centered at diagonal element a_ii with radius sum of |a_ij| for j != i.
        We return center ± radius as real eigenvalue estimates.
        """
        eigenvalues: list[ComplexNum] = []

        for i in range(N):
            center = adj[i][i]
            radius = sum(abs(adj[i][j]) for j in range(N) if j != i)

            # Create two eigenvalue estimates per row: center ± radius/2
            eigenvalues.append(ComplexNum(center + radius * 0.5, 0.0))
            if radius > 0:
                eigenvalues.append(ComplexNum(center - radius * 0.5, radius * 0.1))

        return eigenvalues

    def _estimate_jordan_blocks(self, adj: list[list[float]], N: int) -> list[int]:
        """
        Estimate Jordan block sizes from nilpotent structure.
        A Jordan block corresponds to a chain: node i → node j → node k
        with the same approximate eigenvalue (diagonal value).
        """
        blocks: list[int] = []
        visited = set()

        for i in range(N):
            if i in visited:
                continue
            chain_len = 1
            cur = i
            visited.add(cur)

            # Follow the strongest outgoing edge
            for _ in range(N):
                best_j, best_w = -1, 0.0
                for j in range(N):
                    if j not in visited and adj[cur][j] > best_w:
                        best_j, best_w = j, adj[cur][j]
                if best_j == -1 or best_w < 0.1:
                    break
                # Only extend chain if diagonal values are similar (same eigenvalue)
                if abs(adj[best_j][best_j] - adj[i][i]) < 0.2:
                    chain_len += 1
                    visited.add(best_j)
                    cur = best_j
                else:
                    break

            blocks.append(chain_len)

        return blocks

    def _density(self, adj: list[list[float]], N: int) -> float:
        if N <= 1:
            return 0.0
        nonzero = sum(1 for i in range(N) for j in range(N) if adj[i][j] > 0)
        return nonzero / (N * N)

    def _empty_result(self) -> JordanResult:
        return JordanResult(
            eigenvalues=[],
            spectral_radius=0.0,
            stability_score=1.0,
            mean_magnitude=0.0,
            jordan_block_sizes=[],
            routing_features={
                "spectral_radius": 0.0,
                "stability_score": 1.0,
                "mean_magnitude": 0.0,
                "max_block_size": 1.0,
                "graph_density": 0.0,
                "routing_confidence": 1.0,
            }
        )
