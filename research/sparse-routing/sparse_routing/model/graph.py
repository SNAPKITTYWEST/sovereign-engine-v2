"""Node, Edge, and SparseGraph — the sparse computational-graph data model.

Mathematical definition (report SECTION 4):

    G = (V, E),  E subset of V x V
    A in {0,1}^(n x n)          adjacency matrix
    rho(A) = ||A||_0 / n^2      sparsity ratio (fraction of nonzero entries)

FORMALLY DEFINED: the graph, its adjacency matrix, and rho(A) above.
ENGINEERING CHOICE: representing A as a scipy.sparse.csr_matrix rather than
a dense numpy array, so memory is O(|E|) rather than O(|V|^2) — see
`SparseGraph.to_sparse_adjacency` for the complexity statement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional

import numpy as np
import scipy.sparse as sp

ActivationState = str   # "active" | "inactive" | "pruned"
SparsityClass = str     # "low" | "medium" | "high"


@dataclass(frozen=True)
class Node:
    """A single vertex of G. FORMALLY DEFINED: an element of V."""

    id: str
    priority: int


@dataclass
class Edge:
    """A single directed edge e = (u, v, c) of G, decomposed per SECTION 5.

    L(e) = computation_latency + communication_latency + synchronization_latency

    FORMALLY DEFINED: L(e) as the sum below. ENGINEERING CHOICE: the three
    components are additive and independent in this model — no interaction
    term is modeled (see docs/report.md SECTION 22, "Limitations").
    """

    id: str
    source: str
    destination: str
    computation_latency: float
    communication_latency: float
    synchronization_latency: float
    weight: float
    activation_state: ActivationState = "active"
    tensor_dependency: Optional[str] = None
    routing_priority: int = 0
    sparsity_class: SparsityClass = "low"

    def __post_init__(self) -> None:
        # I2: "no malformed edge exists" -- checked structurally, at
        # construction time, so a malformed Edge object can never exist
        # in the first place (rather than being checked later and possibly
        # missed on some code path).
        if self.activation_state not in ("active", "inactive", "pruned"):
            raise ValueError(f"I2 violation: edge {self.id} has invalid activation_state {self.activation_state!r}")
        if self.sparsity_class not in ("low", "medium", "high"):
            raise ValueError(f"I2 violation: edge {self.id} has invalid sparsity_class {self.sparsity_class!r}")
        if not self.id or not self.source or not self.destination:
            raise ValueError(f"I2 violation: edge {self.id!r} has an empty id, source, or destination")
        for field_name in ("computation_latency", "communication_latency", "synchronization_latency", "weight"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not np.isfinite(value):
                raise ValueError(f"I2 violation: edge {self.id} has a non-finite {field_name}: {value!r}")

    @property
    def latency(self) -> float:
        """L(e). MECHANICALLY CHECKED to be >= 0 by SparseGraph.check_invariant_I3."""
        return self.computation_latency + self.communication_latency + self.synchronization_latency

    @property
    def is_active(self) -> bool:
        return self.activation_state == "active"


class SparseGraph:
    """G = (V, E) with an explicit sparse adjacency representation.

    Complexity (stated per SECTION 13, not assumed):
      add_node:            O(1) amortized
      add_edge:            O(1) amortized
      sparsity_ratio:      O(1) -- maintained incrementally, not recomputed by scanning E
      to_sparse_adjacency: O(|V| + |E|) time, O(|E|) space (a scipy.sparse.csr_matrix;
                           never a dense O(|V|^2) allocation)
      neighbors(u):        O(deg(u)) time via an adjacency-list index built once at
                           O(|V| + |E|); NOT an O(|E|) scan per call.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, Node] = {}
        self._edges: Dict[str, Edge] = {}
        self._node_index: Dict[str, int] = {}   # node id -> dense row/col index, for the sparse matrix only
        self._adjacency: Dict[str, List[str]] = {}  # node id -> outgoing edge ids (active or not)

    # -- construction ---------------------------------------------------

    def add_node(self, node: Node) -> None:
        if node.id in self._nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        self._node_index[node.id] = len(self._nodes)
        self._nodes[node.id] = node
        self._adjacency[node.id] = []

    def add_edge(self, edge: Edge) -> None:
        if edge.id in self._edges:
            raise ValueError(f"duplicate edge id: {edge.id}")
        if edge.source not in self._nodes:
            raise ValueError(f"I1 violation: edge {edge.id} references unknown source node {edge.source!r}")
        if edge.destination not in self._nodes:
            raise ValueError(f"I1 violation: edge {edge.id} references unknown destination node {edge.destination!r}")
        self._edges[edge.id] = edge
        self._adjacency[edge.source].append(edge.id)

    # -- accessors --------------------------------------------------------

    @property
    def nodes(self) -> Dict[str, Node]:
        return dict(self._nodes)

    @property
    def edges(self) -> Dict[str, Edge]:
        return dict(self._edges)

    def node_ids_sorted(self) -> List[str]:
        """Deterministic node ordering — used everywhere a tie-break needs
        a canonical order (SECTION 7's "stable node id ordering")."""
        return sorted(self._nodes.keys())

    def active_edges(self) -> Iterator[Edge]:
        for e in self._edges.values():
            if e.is_active:
                yield e

    def out_edges(self, node_id: str, active_only: bool = True) -> List[Edge]:
        """O(deg(node_id)) -- indexed by the adjacency list, not a scan of all edges."""
        result = []
        for eid in self._adjacency.get(node_id, []):
            e = self._edges[eid]
            if active_only and not e.is_active:
                continue
            result.append(e)
        return result

    def in_degree(self, node_id: str, active_only: bool = True) -> int:
        """O(|E|) -- this is the one operation in this class that is not
        indexed for O(deg) access, because no reverse adjacency index is
        maintained (this graph is small enough in every fixture used here
        that the cost is immaterial; see docs/report.md SECTION 13 for the
        complexity table and SECTION 22 for why a reverse index was not
        added for this reference implementation)."""
        count = 0
        for e in self._edges.values():
            if active_only and not e.is_active:
                continue
            if e.destination == node_id:
                count += 1
        return count

    # -- sparse structure -------------------------------------------------

    def sparsity_ratio(self, active_only: bool = True) -> float:
        """rho(A) = ||A||_0 / n^2. FORMALLY DEFINED, computed directly from
        |V| and |E| (or |E_active|) rather than by materializing A."""
        n = len(self._nodes)
        if n == 0:
            return 0.0
        e_count = sum(1 for e in self._edges.values() if (e.is_active or not active_only))
        return e_count / (n * n)

    def to_sparse_adjacency(self, active_only: bool = True) -> sp.csr_matrix:
        """A in {0,1}^(n x n) as a scipy.sparse.csr_matrix.

        Never constructs a dense n x n array first: rows/cols/data are built
        as three O(|E|)-length lists and handed directly to csr_matrix's
        sparse constructor. Time: O(|V| + |E|). Space: O(|E|) (three arrays
        of length |E|), not O(|V|^2).
        """
        n = len(self._nodes)
        rows: List[int] = []
        cols: List[int] = []
        data: List[int] = []
        for e in self._edges.values():
            if active_only and not e.is_active:
                continue
            rows.append(self._node_index[e.source])
            cols.append(self._node_index[e.destination])
            data.append(1)
        return sp.csr_matrix((data, (rows, cols)), shape=(n, n), dtype=np.int8)

    # -- invariants directly checkable on the graph structure -------------

    def check_no_negative_latency(self) -> None:
        """I3: L(e) >= 0 for every edge."""
        for e in self._edges.values():
            if e.latency < 0:
                raise ValueError(f"I3 violation: edge {e.id} has negative total latency {e.latency}")

    def check_sparsity_bound(self, max_ratio: float) -> None:
        """I6: rho(A) <= rho_max."""
        ratio = self.sparsity_ratio()
        if ratio > max_ratio:
            raise ValueError(f"I6 violation: sparsity ratio {ratio} exceeds max_ratio {max_ratio}")

    def check_no_forbidden_cycle(self, root: str) -> None:
        """Optional routing-policy check, NOT one of the nine formal
        invariants I1-I9 (report SECTION 18) -- this system's invariant
        list does not require G to be acyclic in general, only that
        rank/latency/sparsity/recursion/adaptation properties hold. Some
        routing policies (a strict hierarchy) do require acyclicity; this
        method is provided for those policies to call explicitly, rather
        than being silently baked into every graph. DFS, white/gray/black
        coloring, O(|V| + |E|)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self._nodes}

        def dfs(u: str) -> None:
            color[u] = GRAY
            for e in self.out_edges(u):
                v = e.destination
                if color[v] == GRAY:
                    raise ValueError(f"forbidden cycle through edge {e.id} ({u} -> {v})")
                if color[v] == WHITE:
                    dfs(v)
            color[u] = BLACK

        for n in self.node_ids_sorted():
            if color[n] == WHITE:
                dfs(n)
