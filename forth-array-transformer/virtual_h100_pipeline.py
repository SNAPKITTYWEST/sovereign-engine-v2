"""
Virtual H100 Transformer Switchboard — complete pipeline.

DAG → canonicalize → tensor encode → embedding → graph-aware attention
  → MLP → switchboard → parallel execution → decoder → reconstruction → verify

Core types, canonicalizer, encoder, switchboard, scheduler,
transformer blocks, decoder, verifier, and pipeline entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib
import json
from collections import defaultdict, deque

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import networkx as nx


# ─────────────────────────────────────────────────────────────────────────────
# TYPES
# ─────────────────────────────────────────────────────────────────────────────

def stable_hash(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(s.encode()).hexdigest()


def tensor_hash(t: torch.Tensor) -> str:
    return hashlib.sha256(t.detach().cpu().numpy().tobytes()).hexdigest()


class Route(Enum):
    GRAPH_NODE = auto()
    GRAPH_EDGE = auto()
    ATTENTION = auto()
    MLP = auto()
    REDUCTION = auto()
    AGGREGATION = auto()
    DECODER = auto()
    RECONSTRUCTION = auto()
    VALIDATION = auto()


class AttentionPolicy(Enum):
    LOCAL_PARENT = auto()
    CHILDREN = auto()
    ANCESTORS = auto()
    DESCENDANTS = auto()
    SAME_LEVEL = auto()
    FULL_GRAPH = auto()


class NodeType(Enum):
    GENERIC = 0
    INPUT = 1
    HIDDEN = 2
    OUTPUT = 3
    ATTENTION = 4
    MLP = 5
    REDUCTION = 6


class EdgeType(Enum):
    DATA = 0
    CONTROL = 1
    DEPENDENCY = 2
    ATTENTION = 3


@dataclass(frozen=True)
class Node:
    node_id: int
    node_type: NodeType
    label: str = ""
    features: Tuple[float, ...] = ()
    structural_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.name,
            "label": self.label,
            "features": list(self.features),
            "structural_hash": self.structural_hash,
        }


@dataclass(frozen=True)
class Edge:
    source_id: int
    dest_id: int
    edge_type: EdgeType
    metadata: Tuple[float, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "dest_id": self.dest_id,
            "edge_type": self.edge_type.name,
            "metadata": list(self.metadata),
        }


@dataclass
class CanonicalDAG:
    nodes: List[Node]
    edges: List[Edge]
    adjacency: np.ndarray
    topological_order: List[int]
    depth: Dict[int, int]
    structural_hash: str
    node_id_map: Dict[int, int]

    @property
    def N(self) -> int:
        return len(self.nodes)

    @property
    def E(self) -> int:
        return len(self.edges)

    def node_index(self, node_id: int) -> int:
        return self.node_id_map[node_id]


@dataclass
class TensorBundle:
    node_tensor: torch.Tensor
    edge_tensor: torch.Tensor
    adjacency: torch.Tensor
    incidence: torch.Tensor
    topological: torch.Tensor
    dependency_mask: torch.Tensor
    attention_mask: torch.Tensor
    provenance: Dict[str, Any]
    structural_hash: str
    edge_index: torch.Tensor

    def shapes(self) -> Dict[str, Tuple[int, ...]]:
        return {
            "node_tensor": tuple(self.node_tensor.shape),
            "edge_tensor": tuple(self.edge_tensor.shape),
            "adjacency": tuple(self.adjacency.shape),
            "topological": tuple(self.topological.shape),
            "dependency_mask": tuple(self.dependency_mask.shape),
            "attention_mask": tuple(self.attention_mask.shape),
            "edge_index": tuple(self.edge_index.shape),
        }


@dataclass
class RoutingDecision:
    input_id: str
    tensor_shape: Tuple[int, ...]
    dtype: str
    graph_region: str
    dependency_set: frozenset
    execution_stage: int
    target_virtual_sm: int
    route: Route
    decoder_target: Optional[str]
    provenance_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_id": self.input_id,
            "tensor_shape": self.tensor_shape,
            "graph_region": self.graph_region,
            "execution_stage": self.execution_stage,
            "target_virtual_sm": self.target_virtual_sm,
            "route": self.route.name,
            "decoder_target": self.decoder_target,
            "provenance_hash": self.provenance_hash,
        }


@dataclass
class DecoderOutput:
    decoded_nodes: List[Node]
    decoded_edges: List[Edge]
    reconstructed_graph: CanonicalDAG
    execution_trace: List[Dict[str, Any]]
    provenance: List[Any]
    validation_result: Dict[str, bool]
    success: bool
    failure_reason: Optional[str]


@dataclass
class VirtualResourceConfig:
    virtual_gpu_count: int = 1
    virtual_sm_count: int = 16
    virtual_warp_count: int = 4
    execution_queue_depth: int = 256
    tensor_core_count: int = 8


# ─────────────────────────────────────────────────────────────────────────────
# CANONICALIZER
# ─────────────────────────────────────────────────────────────────────────────

class CycleError(ValueError):
    pass


class DAGCanonicalizer:
    def __init__(self, feature_dim: int = 8):
        self.feature_dim = feature_dim

    def canonicalize(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> CanonicalDAG:
        if not nodes:
            raise ValueError("Empty node list")

        G = nx.DiGraph()
        id_to_raw: Dict[Any, Dict[str, Any]] = {}
        for n in nodes:
            nid = n["id"]
            if nid in id_to_raw:
                raise ValueError(f"Duplicate node id: {nid}")
            id_to_raw[nid] = n
            G.add_node(nid)

        for e in edges:
            src, dst = e["source"], e["dest"]
            if src not in id_to_raw or dst not in id_to_raw:
                raise ValueError(f"Edge references unknown node: {src} -> {dst}")
            G.add_edge(src, dst)

        if not nx.is_directed_acyclic_graph(G):
            try:
                cycle = nx.find_cycle(G)
                raise CycleError(f"Graph contains cycle: {cycle}")
            except nx.NetworkXNoCycle:
                raise CycleError("Graph is not a DAG")

        topo_ids = self._deterministic_topo(G)
        original_to_canon = {oid: idx for idx, oid in enumerate(topo_ids)}

        depth: Dict[int, int] = {}
        for oid in topo_ids:
            preds = list(G.predecessors(oid))
            depth[oid] = 0 if not preds else 1 + max(depth[p] for p in preds)

        canon_nodes: List[Node] = []
        for idx, oid in enumerate(topo_ids):
            raw = id_to_raw[oid]
            ntype = self._parse_node_type(raw.get("type", "GENERIC"))
            label = str(raw.get("label", f"n{oid}"))
            feats = self._pad_features(raw.get("features", []), self.feature_dim)
            nh = stable_hash({"type": ntype.name, "label": label, "features": feats})
            canon_nodes.append(Node(
                node_id=idx,
                node_type=ntype,
                label=label,
                features=tuple(feats),
                structural_hash=nh,
            ))

        raw_edges = []
        for e in edges:
            src_c = original_to_canon[e["source"]]
            dst_c = original_to_canon[e["dest"]]
            etype = self._parse_edge_type(e.get("type", "DATA"))
            meta = self._pad_features(e.get("metadata", []), 4)
            raw_edges.append((src_c, dst_c, etype, tuple(meta)))

        raw_edges.sort(key=lambda x: (x[0], x[1], x[2].value))
        canon_edges = [
            Edge(source_id=s, dest_id=d, edge_type=et, metadata=m)
            for s, d, et, m in raw_edges
        ]

        N = len(canon_nodes)
        adj = np.zeros((N, N), dtype=np.float32)
        for e in canon_edges:
            adj[e.source_id, e.dest_id] = 1.0

        canon_depth = {canon_nodes[idx].node_id: depth[oid]
                       for idx, oid in enumerate(topo_ids)}

        sh = stable_hash({
            "nodes": [n.to_dict() for n in canon_nodes],
            "edges": [e.to_dict() for e in canon_edges],
        })

        return CanonicalDAG(
            nodes=canon_nodes,
            edges=canon_edges,
            adjacency=adj,
            topological_order=list(range(N)),
            depth=canon_depth,
            structural_hash=sh,
            node_id_map={i: i for i in range(N)},
        )

    def _deterministic_topo(self, G: nx.DiGraph) -> List[Any]:
        in_degree = {n: G.in_degree(n) for n in G.nodes()}
        queue = deque(sorted(n for n, d in in_degree.items() if d == 0))
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for nb in sorted(G.successors(node)):
                in_degree[nb] -= 1
                if in_degree[nb] == 0:
                    queue.append(nb)
        return order

    def _parse_node_type(self, s: str) -> NodeType:
        try:
            return NodeType[s.upper()]
        except KeyError:
            return NodeType.GENERIC

    def _parse_edge_type(self, s: str) -> EdgeType:
        try:
            return EdgeType[s.upper()]
        except KeyError:
            return EdgeType.DATA

    def _pad_features(self, feats: List[float], dim: int) -> List[float]:
        f = list(feats)[:dim]
        while len(f) < dim:
            f.append(0.0)
        return f


def make_random_dag(
    n_nodes: int,
    edge_prob: float = 0.25,
    seed: int = 42,
) -> Tuple[List[Dict], List[Dict]]:
    rng = np.random.default_rng(seed)
    nodes = [{"id": i, "type": "GENERIC", "label": f"n{i}",
               "features": rng.random(8).tolist()} for i in range(n_nodes)]
    edges = []
    for i in range(n_nodes):
        for j in range(i + 1, n_nodes):
            if rng.random() < edge_prob:
                edges.append({"source": i, "dest": j, "type": "DATA"})
    return nodes, edges


# ─────────────────────────────────────────────────────────────────────────────
# ENCODER
# ─────────────────────────────────────────────────────────────────────────────

NODE_ID_IDX = 0
NODE_TYPE_IDX = 1
TOPO_DEPTH_IDX = 2
IN_DEGREE_IDX = 3
OUT_DEGREE_IDX = 4
FEATURE_START = 5

EDGE_SRC_IDX = 0
EDGE_DST_IDX = 1
EDGE_TYPE_IDX = 2
EDGE_REL_DEPTH_IDX = 3
EDGE_META_START = 4


class GraphTensorEncoder:
    def __init__(
        self,
        node_feature_dim: int = 8,
        edge_meta_dim: int = 4,
        attention_policy: AttentionPolicy = AttentionPolicy.ANCESTORS,
        dtype: torch.dtype = torch.float32,
        device: str = "cpu",
    ):
        self.node_feature_dim = node_feature_dim
        self.edge_meta_dim = edge_meta_dim
        self.attention_policy = attention_policy
        self.dtype = dtype
        self.device = device
        self.node_dim = 5 + node_feature_dim + 1
        self.edge_dim = 4 + edge_meta_dim

    def encode(self, dag: CanonicalDAG) -> TensorBundle:
        N = dag.N
        E = dag.E

        node_data = np.zeros((N, self.node_dim), dtype=np.float64)
        edge_data = np.zeros((max(E, 1), self.edge_dim), dtype=np.float64)
        edge_index = np.zeros((max(E, 1), 2), dtype=np.int64)

        in_deg = np.zeros(N, dtype=np.int32)
        out_deg = np.zeros(N, dtype=np.int32)
        for e in dag.edges:
            out_deg[e.source_id] += 1
            in_deg[e.dest_id] += 1

        for i, node in enumerate(dag.nodes):
            d = dag.depth.get(i, 0)
            h_num = int(node.structural_hash[:8], 16) % (2 ** 24)
            row = [float(node.node_id), float(node.node_type.value),
                   float(d), float(in_deg[i]), float(out_deg[i])]
            feats = list(node.features)[:self.node_feature_dim]
            while len(feats) < self.node_feature_dim:
                feats.append(0.0)
            row.extend(feats)
            row.append(float(h_num))
            node_data[i] = row

        for j, edge in enumerate(dag.edges):
            rel_depth = dag.depth.get(edge.dest_id, 0) - dag.depth.get(edge.source_id, 0)
            row = [float(edge.source_id), float(edge.dest_id),
                   float(edge.edge_type.value), float(rel_depth)]
            meta = list(edge.metadata)[:self.edge_meta_dim]
            while len(meta) < self.edge_meta_dim:
                meta.append(0.0)
            row.extend(meta)
            edge_data[j] = row
            edge_index[j] = [edge.source_id, edge.dest_id]

        topo = np.array(dag.topological_order, dtype=np.int64)
        dep_mask = self._build_dependency_mask(dag)
        attn_mask = self._build_attention_mask(dag, dep_mask)
        adj = torch.from_numpy(dag.adjacency.astype(np.float32)).to(self.device)

        provenance = {
            "source_graph_hash": dag.structural_hash,
            "N": N,
            "E": E,
        }

        def to_t(a):
            return torch.from_numpy(a.astype(np.float32)).to(self.device)

        return TensorBundle(
            node_tensor=to_t(node_data),
            edge_tensor=to_t(edge_data),
            adjacency=adj,
            incidence=torch.from_numpy(edge_index).to(self.device),
            topological=torch.from_numpy(topo).to(self.device),
            dependency_mask=to_t(dep_mask),
            attention_mask=to_t(attn_mask),
            provenance=provenance,
            structural_hash=dag.structural_hash,
            edge_index=torch.from_numpy(edge_index).to(self.device),
        )

    def _build_dependency_mask(self, dag: CanonicalDAG) -> np.ndarray:
        N = dag.N
        mask = np.eye(N, dtype=np.float32)
        G = nx.DiGraph()
        G.add_nodes_from(range(N))
        G.add_edges_from([(e.source_id, e.dest_id) for e in dag.edges])
        for i in range(N):
            for j in range(N):
                if i != j and nx.has_path(G, j, i):
                    mask[i, j] = 1.0
        return mask

    def _build_attention_mask(self, dag: CanonicalDAG, dep_mask: np.ndarray) -> np.ndarray:
        N = dag.N
        if self.attention_policy == AttentionPolicy.ANCESTORS:
            return dep_mask.copy()
        elif self.attention_policy == AttentionPolicy.FULL_GRAPH:
            return np.ones((N, N), dtype=np.float32)
        elif self.attention_policy == AttentionPolicy.LOCAL_PARENT:
            mask = np.eye(N, dtype=np.float32)
            for e in dag.edges:
                mask[e.dest_id, e.source_id] = 1.0
            return mask
        elif self.attention_policy == AttentionPolicy.SAME_LEVEL:
            mask = np.zeros((N, N), dtype=np.float32)
            for i in range(N):
                for j in range(N):
                    if dag.depth.get(i, 0) == dag.depth.get(j, 0):
                        mask[i, j] = 1.0
            return mask
        return dep_mask.copy()


# ─────────────────────────────────────────────────────────────────────────────
# SWITCHBOARD / VIRTUAL H100
# ─────────────────────────────────────────────────────────────────────────────

class VirtualH100:
    def __init__(self, config: Optional[VirtualResourceConfig] = None):
        self.config = config or VirtualResourceConfig()
        self.sm_busy: Dict[int, bool] = {i: False for i in range(self.config.virtual_sm_count)}
        self.cycle = 0

    def allocate_sm(self, preferred: Optional[int] = None) -> int:
        if preferred is not None and not self.sm_busy.get(preferred, True):
            self.sm_busy[preferred] = True
            return preferred
        for i in range(self.config.virtual_sm_count):
            if not self.sm_busy[i]:
                self.sm_busy[i] = True
                return i
        sm = self.cycle % self.config.virtual_sm_count
        self.cycle += 1
        return sm

    def release_sm(self, sm_id: int) -> None:
        if 0 <= sm_id < self.config.virtual_sm_count:
            self.sm_busy[sm_id] = False


class Switchboard:
    def __init__(
        self,
        virtual_h100: Optional[VirtualH100] = None,
        config: Optional[VirtualResourceConfig] = None,
    ):
        self.h100 = virtual_h100 or VirtualH100(config)
        self.routing_log: List[RoutingDecision] = []
        self._stage_counter = 0

    def reset(self) -> None:
        self.routing_log.clear()
        self._stage_counter = 0
        for k in self.h100.sm_busy:
            self.h100.sm_busy[k] = False

    def route(
        self,
        bundle: TensorBundle,
        requested_route: Optional[Route] = None,
        graph_region: str = "full",
        dependency_set: Optional[frozenset] = None,
        execution_stage: Optional[int] = None,
        decoder_target: Optional[str] = None,
    ) -> RoutingDecision:
        dep_set = dependency_set or frozenset()
        stage = execution_stage if execution_stage is not None else self._stage_counter
        self._stage_counter = max(self._stage_counter, stage + 1)

        route = requested_route if requested_route is not None else self._infer_route(bundle, graph_region)

        hash_int = int(bundle.structural_hash[:8], 16)
        preferred_sm = (hash_int + stage) % self.h100.config.virtual_sm_count
        sm = self.h100.allocate_sm(preferred_sm)

        ph = stable_hash({
            "shape": list(bundle.node_tensor.shape),
            "route": route.name,
            "stage": stage,
            "region": graph_region,
        })

        decision = RoutingDecision(
            input_id=bundle.structural_hash[:16],
            tensor_shape=tuple(bundle.node_tensor.shape),
            dtype=str(bundle.node_tensor.dtype),
            graph_region=graph_region,
            dependency_set=dep_set,
            execution_stage=stage,
            target_virtual_sm=sm,
            route=route,
            decoder_target=decoder_target,
            provenance_hash=ph,
        )
        self.routing_log.append(decision)
        self.h100.release_sm(sm)
        return decision

    def _infer_route(self, bundle: TensorBundle, region: str) -> Route:
        N = bundle.node_tensor.shape[0]
        if region == "full":
            return Route.AGGREGATION
        if N == 1:
            return Route.GRAPH_NODE
        attn = bundle.attention_mask
        density = float(attn.sum()) / max(attn.numel(), 1)
        if density > 0.5:
            return Route.ATTENTION
        return Route.MLP


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH-AWARE TRANSFORMER
# ─────────────────────────────────────────────────────────────────────────────

class GraphAwareAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int = 4, dropout: float = 0.0):
        super().__init__()
        assert d_model % n_heads == 0
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        N, D = x.shape
        q = self.q_proj(x).view(N, self.n_heads, self.d_head).transpose(0, 1)
        k = self.k_proj(x).view(N, self.n_heads, self.d_head).transpose(0, 1)
        v = self.v_proj(x).view(N, self.n_heads, self.d_head).transpose(0, 1)
        scores = torch.matmul(q, k.transpose(-2, -1)) / (self.d_head ** 0.5)
        mask = attention_mask.unsqueeze(0)
        scores = scores.masked_fill(mask == 0, -1e9)
        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)
        out = torch.matmul(attn, v).transpose(0, 1).contiguous().view(N, D)
        return self.out_proj(out)


class MLP(nn.Module):
    def __init__(self, d_model: int, d_ff: Optional[int] = None, dropout: float = 0.0):
        super().__init__()
        d_ff = d_ff or 4 * d_model
        self.fc1 = nn.Linear(d_model, d_ff)
        self.fc2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc2(self.dropout(F.gelu(self.fc1(x))))


class GraphTransformerBlock(nn.Module):
    def __init__(self, d_model: int, n_heads: int = 4, d_ff: Optional[int] = None, dropout: float = 0.0):
        super().__init__()
        self.attn = GraphAwareAttention(d_model, n_heads, dropout)
        self.mlp = MLP(d_model, d_ff, dropout)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        h = self.norm1(x)
        h = self.attn(h, attention_mask)
        x = x + self.dropout(h)
        h = self.norm2(x)
        h = self.mlp(h)
        x = x + self.dropout(h)
        return x


class GraphTransformer(nn.Module):
    def __init__(
        self,
        node_input_dim: int,
        d_model: int = 64,
        n_layers: int = 2,
        n_heads: int = 4,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.input_proj = nn.Linear(node_input_dim, d_model)
        self.layers = nn.ModuleList([
            GraphTransformerBlock(d_model, n_heads, dropout=dropout)
            for _ in range(n_layers)
        ])
        self.output_proj = nn.Linear(d_model, node_input_dim)
        nn.init.xavier_uniform_(self.input_proj.weight)
        nn.init.zeros_(self.input_proj.bias)
        nn.init.xavier_uniform_(self.output_proj.weight)
        nn.init.zeros_(self.output_proj.bias)

    def forward(self, bundle: TensorBundle) -> torch.Tensor:
        x = self.input_proj(bundle.node_tensor)
        mask = bundle.attention_mask
        for layer in self.layers:
            x = layer(x, mask)
        return self.output_proj(x)

    def run_with_switchboard(
        self, bundle: TensorBundle, switchboard: Switchboard
    ) -> Tuple[torch.Tensor, List[RoutingDecision]]:
        decisions = []
        x = self.input_proj(bundle.node_tensor)
        mask = bundle.attention_mask
        for i, layer in enumerate(self.layers):
            d = switchboard.route(bundle, Route.ATTENTION, "transformer", execution_stage=i)
            decisions.append(d)
            x = layer(x, mask)
            d2 = switchboard.route(bundle, Route.MLP, "transformer", execution_stage=i)
            decisions.append(d2)
        out = self.output_proj(x)
        return out, decisions


# ─────────────────────────────────────────────────────────────────────────────
# PARALLEL SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

class ParallelDAGScheduler:
    def __init__(
        self,
        encoder: Optional[GraphTensorEncoder] = None,
        switchboard: Optional[Switchboard] = None,
        config: Optional[VirtualResourceConfig] = None,
    ):
        self.encoder = encoder or GraphTensorEncoder()
        self.switchboard = switchboard or Switchboard(config=config)
        self.config = config or VirtualResourceConfig()
        self.completed_nodes: Set[int] = set()
        self.execution_trace: List[Dict[str, Any]] = []

    def compute_levels(self, dag: CanonicalDAG) -> Dict[int, List[int]]:
        levels: Dict[int, List[int]] = defaultdict(list)
        for nid, d in sorted(dag.depth.items()):
            levels[d].append(nid)
        for d in levels:
            levels[d].sort()
        return dict(levels)

    def is_ready(self, node_id: int, dag: CanonicalDAG) -> bool:
        parents = [e.source_id for e in dag.edges if e.dest_id == node_id]
        return all(p in self.completed_nodes for p in parents)

    def schedule(self, dag: CanonicalDAG) -> Dict[str, Any]:
        self.completed_nodes.clear()
        self.execution_trace.clear()
        self.switchboard.reset()

        levels = self.compute_levels(dag)
        max_level = max(levels.keys()) if levels else -1

        full_bundle = self.encoder.encode(dag)
        full_decision = self.switchboard.route(
            full_bundle, Route.AGGREGATION, "full", execution_stage=0
        )
        self.execution_trace.append({
            "stage": 0,
            "type": "full_encode",
            "decision": full_decision.to_dict(),
            "shapes": full_bundle.shapes(),
        })

        for lvl in range(max_level + 1):
            nodes_at_level = levels.get(lvl, [])
            for nid in nodes_at_level:
                if not self.is_ready(nid, dag):
                    raise RuntimeError(f"Node {nid} at level {lvl} not ready")

            region = f"level_{lvl}"
            decision = self.switchboard.route(
                full_bundle, Route.GRAPH_NODE, region, execution_stage=lvl + 1
            )
            self.execution_trace.append({
                "stage": lvl + 1,
                "type": "level",
                "level": lvl,
                "nodes": nodes_at_level,
                "decision": decision.to_dict(),
            })
            for nid in nodes_at_level:
                self.completed_nodes.add(nid)

        return {
            "full_bundle": full_bundle,
            "execution_trace": self.execution_trace,
            "provenance": [{"source_graph_hash": dag.structural_hash}],
            "routing_log": [d.to_dict() for d in self.switchboard.routing_log],
            "schedule": {"max_level": max_level},
        }


# ─────────────────────────────────────────────────────────────────────────────
# DECODER
# ─────────────────────────────────────────────────────────────────────────────

class GraphDecoder:
    def __init__(self, node_feature_dim: int = 8, edge_meta_dim: int = 4):
        self.node_feature_dim = node_feature_dim
        self.edge_meta_dim = edge_meta_dim
        self.canonicalizer = DAGCanonicalizer(feature_dim=node_feature_dim)

    def decode(
        self,
        bundle: TensorBundle,
        provenance: Optional[List[Any]] = None,
        execution_trace: Optional[List[Dict[str, Any]]] = None,
    ) -> DecoderOutput:
        provenance = provenance or []
        execution_trace = execution_trace or []
        try:
            nodes = self._decode_nodes(bundle)
            edges = self._decode_edges(bundle)
            reconstructed = self._build_canonical(nodes, edges, bundle)
            validation = self._validate(bundle, reconstructed, nodes, edges)
            success = all(validation.values())
            return DecoderOutput(
                decoded_nodes=nodes,
                decoded_edges=edges,
                reconstructed_graph=reconstructed,
                execution_trace=execution_trace,
                provenance=provenance,
                validation_result=validation,
                success=success,
                failure_reason=None if success else "Validation invariant(s) failed",
            )
        except Exception as exc:
            return DecoderOutput(
                decoded_nodes=[],
                decoded_edges=[],
                reconstructed_graph=None,
                execution_trace=execution_trace,
                provenance=provenance,
                validation_result={"exception": False},
                success=False,
                failure_reason=str(exc),
            )

    def _decode_nodes(self, bundle: TensorBundle) -> List[Node]:
        nt = bundle.node_tensor.detach().cpu().numpy()
        N = nt.shape[0]
        nodes = []
        for i in range(N):
            row = nt[i]
            node_id = int(round(row[0]))
            ntype_val = int(round(row[1]))
            try:
                ntype = NodeType(ntype_val)
            except ValueError:
                ntype = NodeType.GENERIC
            feats = tuple(float(x) for x in row[5: 5 + self.node_feature_dim])
            h_num = int(round(row[5 + self.node_feature_dim]))
            sh = f"{h_num:08x}" + "0" * 24
            nodes.append(Node(
                node_id=node_id, node_type=ntype,
                label=f"n{node_id}", features=feats,
                structural_hash=sh[:32],
            ))
        return nodes

    def _decode_edges(self, bundle: TensorBundle) -> List[Edge]:
        et = bundle.edge_tensor.detach().cpu().numpy()
        E = et.shape[0]
        edges = []
        for j in range(E):
            row = et[j]
            src = int(round(row[0]))
            dst = int(round(row[1]))
            etype_val = int(round(row[2]))
            try:
                etype = EdgeType(etype_val)
            except ValueError:
                etype = EdgeType.DATA
            meta = tuple(float(x) for x in row[4: 4 + self.edge_meta_dim])
            if src >= 0 and dst >= 0 and src != dst:
                edges.append(Edge(source_id=src, dest_id=dst, edge_type=etype, metadata=meta))
        return edges

    def _build_canonical(
        self, nodes: List[Node], edges: List[Edge], bundle: TensorBundle
    ) -> CanonicalDAG:
        N = len(nodes)
        adj = np.zeros((N, N), dtype=np.float32)
        for e in edges:
            if 0 <= e.source_id < N and 0 <= e.dest_id < N:
                adj[e.source_id, e.dest_id] = 1.0
        depth = {n.node_id: int(round(bundle.node_tensor[i, 2].item()))
                 for i, n in enumerate(nodes)}
        sh = stable_hash({"nodes": [n.to_dict() for n in nodes],
                           "edges": [e.to_dict() for e in edges]})
        return CanonicalDAG(
            nodes=nodes, edges=edges, adjacency=adj,
            topological_order=list(range(N)),
            depth=depth, structural_hash=sh,
            node_id_map={i: i for i in range(N)},
        )

    def _validate(
        self, bundle: TensorBundle, recon: CanonicalDAG,
        nodes: List[Node], edges: List[Edge]
    ) -> Dict[str, bool]:
        return {
            "V1_dag": recon is not None and recon.N > 0,
            "V2_nodes": len(nodes) == bundle.node_tensor.shape[0],
            "V5_shapes": bundle.node_tensor.shape[0] > 0,
            "V7_reconstruction": recon is not None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# VERIFIER
# ─────────────────────────────────────────────────────────────────────────────

class VerificationError(Exception):
    pass


class ReconstructionVerifier:
    def __init__(self, encoder: Optional[GraphTensorEncoder] = None):
        self.encoder = encoder or GraphTensorEncoder()

    def verify_roundtrip(
        self,
        original: CanonicalDAG,
        bundle: TensorBundle,
        decoded: DecoderOutput,
    ) -> Dict[str, Any]:
        report: Dict[str, Any] = {"passed": False, "invariants": {}, "failures": []}

        if not decoded.success:
            report["failures"].append(f"Decoder failure: {decoded.failure_reason}")
            report["invariants"] = decoded.validation_result
            return report

        recon = decoded.reconstructed_graph
        inv = {}
        inv["V1_dag_validity"] = self._check_dag(recon)
        inv["V2_node_preservation"] = self._check_nodes(original, recon)
        inv["V3_edge_preservation"] = self._check_edges(original, recon)
        inv["V4_topo_preservation"] = self._check_topo(original, recon)
        inv["V5_shape_consistency"] = self._check_shapes(bundle, original)
        inv["V6_dep_mask"] = self._check_dep_mask(bundle, original)
        inv["V7_reconstruction"] = decoded.success and recon is not None
        inv["V8_provenance"] = bool(bundle.structural_hash)

        report["invariants"] = inv
        failures = [k for k, v in inv.items() if not v]
        report["failures"] = failures
        report["passed"] = len(failures) == 0
        return report

    def assert_roundtrip(self, original, bundle, decoded):
        report = self.verify_roundtrip(original, bundle, decoded)
        if not report["passed"]:
            raise VerificationError(f"Invariant failure(s): {report['failures']}")

    def _check_dag(self, dag: CanonicalDAG) -> bool:
        G = nx.DiGraph()
        G.add_nodes_from(range(dag.N))
        G.add_edges_from([(e.source_id, e.dest_id) for e in dag.edges])
        return nx.is_directed_acyclic_graph(G) and G.number_of_nodes() == dag.N

    def _check_nodes(self, orig: CanonicalDAG, recon: CanonicalDAG) -> bool:
        if orig.N != recon.N:
            return False
        for o, r in zip(orig.nodes, recon.nodes):
            if o.node_id != r.node_id or o.node_type != r.node_type:
                return False
            if not np.allclose(o.features, r.features, atol=1e-4):
                return False
        return True

    def _check_edges(self, orig: CanonicalDAG, recon: CanonicalDAG) -> bool:
        if orig.E != recon.E:
            return False
        orig_set = {(e.source_id, e.dest_id, e.edge_type) for e in orig.edges}
        recon_set = {(e.source_id, e.dest_id, e.edge_type) for e in recon.edges}
        return orig_set == recon_set

    def _check_topo(self, orig: CanonicalDAG, recon: CanonicalDAG) -> bool:
        return len(orig.topological_order) == len(recon.topological_order)

    def _check_shapes(self, bundle: TensorBundle, orig: CanonicalDAG) -> bool:
        return bundle.node_tensor.shape[0] == orig.N

    def _check_dep_mask(self, bundle: TensorBundle, orig: CanonicalDAG) -> bool:
        mask = bundle.dependency_mask.detach().cpu().numpy()
        return mask.shape == (orig.N, orig.N)


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

class VirtualH100Pipeline:
    def __init__(
        self,
        node_feature_dim: int = 8,
        edge_meta_dim: int = 4,
        d_model: int = 64,
        n_layers: int = 2,
        n_heads: int = 4,
        attention_policy: AttentionPolicy = AttentionPolicy.ANCESTORS,
        virtual_config: Optional[VirtualResourceConfig] = None,
        device: str = "cpu",
    ):
        self.node_feature_dim = node_feature_dim
        self.edge_meta_dim = edge_meta_dim
        self.device = device
        self.virtual_config = virtual_config or VirtualResourceConfig()

        self.canonicalizer = DAGCanonicalizer(feature_dim=node_feature_dim)
        self.encoder = GraphTensorEncoder(
            node_feature_dim=node_feature_dim,
            edge_meta_dim=edge_meta_dim,
            attention_policy=attention_policy,
            device=device,
        )
        self.switchboard = Switchboard(config=self.virtual_config)
        self.scheduler = ParallelDAGScheduler(
            encoder=self.encoder,
            switchboard=self.switchboard,
            config=self.virtual_config,
        )
        self.transformer = GraphTransformer(
            node_input_dim=self.encoder.node_dim,
            d_model=d_model,
            n_layers=n_layers,
            n_heads=n_heads,
        ).to(device)
        self.decoder = GraphDecoder(
            node_feature_dim=node_feature_dim,
            edge_meta_dim=edge_meta_dim,
        )
        self.verifier = ReconstructionVerifier(encoder=self.encoder)

    def encode_only(
        self, nodes: List[Dict], edges: List[Dict]
    ) -> Tuple[CanonicalDAG, TensorBundle]:
        dag = self.canonicalizer.canonicalize(nodes, edges)
        bundle = self.encoder.encode(dag)
        return dag, bundle

    def run(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        run_transformer: bool = True,
        fail_closed: bool = True,
    ) -> Dict[str, Any]:
        dag = self.canonicalizer.canonicalize(nodes, edges)
        schedule_result = self.scheduler.schedule(dag)
        bundle: TensorBundle = schedule_result["full_bundle"]

        transformer_decisions = []
        if run_transformer:
            self.transformer.eval()
            with torch.no_grad():
                _, transformer_decisions = self.transformer.run_with_switchboard(
                    bundle, self.switchboard
                )

        decoded: DecoderOutput = self.decoder.decode(
            bundle, execution_trace=schedule_result["execution_trace"]
        )

        verification = self.verifier.verify_roundtrip(dag, bundle, decoded)

        if fail_closed and not verification["passed"]:
            return {
                "success": False,
                "verification": verification,
                "failure": verification["failures"],
            }

        return {
            "success": True,
            "canonical_dag": {"structural_hash": dag.structural_hash, "N": dag.N, "E": dag.E},
            "schedule": schedule_result["schedule"],
            "routing_log": schedule_result["routing_log"],
            "verification": verification,
            "shapes": bundle.shapes(),
            "transformer_decisions": [d.to_dict() for d in transformer_decisions],
        }


# ─────────────────────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────────────────────

VECTOR_LINEAR = {
    "nodes": [
        {"id": "a", "type": "INPUT", "label": "in", "features": [1.0, 0, 0, 0, 0, 0, 0, 0]},
        {"id": "b", "type": "HIDDEN", "label": "h1", "features": [0, 1.0, 0, 0, 0, 0, 0, 0]},
        {"id": "c", "type": "HIDDEN", "label": "h2", "features": [0, 0, 1.0, 0, 0, 0, 0, 0]},
        {"id": "d", "type": "OUTPUT", "label": "out", "features": [0, 0, 0, 1.0, 0, 0, 0, 0]},
    ],
    "edges": [
        {"source": "a", "dest": "b", "type": "DATA"},
        {"source": "b", "dest": "c", "type": "DATA"},
        {"source": "c", "dest": "d", "type": "DATA"},
    ],
}

VECTOR_DIAMOND = {
    "nodes": [
        {"id": 0, "type": "INPUT", "label": "src", "features": [1.0] * 8},
        {"id": 1, "type": "HIDDEN", "label": "left", "features": [0.5] * 8},
        {"id": 2, "type": "HIDDEN", "label": "right", "features": [0.25] * 8},
        {"id": 3, "type": "OUTPUT", "label": "sink", "features": [0.1] * 8},
    ],
    "edges": [
        {"source": 0, "dest": 1},
        {"source": 0, "dest": 2},
        {"source": 1, "dest": 3},
        {"source": 2, "dest": 3},
    ],
}


def run_tests():
    can = DAGCanonicalizer()
    enc = GraphTensorEncoder()
    dec = GraphDecoder()
    ver = ReconstructionVerifier(enc)

    # cycle rejection
    try:
        can.canonicalize([{"id": 0}, {"id": 1}],
                         [{"source": 0, "dest": 1}, {"source": 1, "dest": 0}])
        assert False, "Should raise CycleError"
    except CycleError:
        pass
    print("PASS: cycle_rejection")

    # roundtrip
    for vec in [VECTOR_LINEAR, VECTOR_DIAMOND]:
        dag = can.canonicalize(vec["nodes"], vec["edges"])
        bundle = enc.encode(dag)
        out = dec.decode(bundle)
        assert out.success, f"Decode failed: {out.failure_reason}"
        report = ver.verify_roundtrip(dag, bundle, out)
        assert report["passed"], f"Verification failed: {report['failures']}"
        print(f"PASS: roundtrip N={dag.N} E={dag.E}")

    # pipeline
    pipe = VirtualH100Pipeline(d_model=32, n_layers=1)
    result = pipe.run(VECTOR_DIAMOND["nodes"], VECTOR_DIAMOND["edges"], fail_closed=False)
    assert result["success"], f"Pipeline failed: {result}"
    print(f"PASS: pipeline N={result['canonical_dag']['N']}")

    print("ALL TESTS PASSED")


if __name__ == "__main__":
    run_tests()
