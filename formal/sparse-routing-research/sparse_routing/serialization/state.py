"""Deterministic, cryptographically hash-chained state (report SECTION 17).

    S_0 -> S_1 -> S_2 -> ... -> S_n

Every transition records: previous state hash, the triggering observation,
which nodes/edges/tensor changed, the latency measurement, the Jacobian
rank, and a verification result -- then a SHA-256 digest of a canonical,
order-independent serialization of all of that (never of Python's
`repr()`/`str()` of live objects, whose formatting is not a stable
contract across versions).

MECHANICALLY CHECKED: two NetworkState objects built from the same graph,
tensor, rank, and latency values, with the same prev_hash, produce
byte-identical canonical payloads and therefore identical hashes --
verified by tests/test_state_hashing.py, which builds the same state
twice from independently-constructed objects and asserts equal hashes,
and by tests/test_replay.py, which re-runs an entire adaptation sequence
and asserts every hash in the chain matches the first run's.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from sparse_routing.model import SparseGraph
from sparse_routing.rank import JacobianState
from sparse_routing.tensor import TensorNode


def canonical_payload(
    network_name: str,
    network_version: str,
    graph: SparseGraph,
    tensor_root: Optional[TensorNode],
    rank_value: Optional[int],
    rank_source: Optional[str],
    route_total_latency: Optional[float],
    bottleneck_node: Optional[str],
    prev_hash: str,
) -> bytes:
    """The exact byte string that gets hashed. Order is fixed (sorted
    ids) so the result does not depend on dict/insertion order or on
    which Python version produced it -- the same discipline the
    companion Bash implementation's canonical_payload() uses, so the two
    independent implementations can, in principle, be cross-checked
    against the same topology (see docs/report.md SECTION 9)."""
    lines: List[str] = []
    lines.append(f"NETWORK|{network_name}|{network_version}")
    for nid in graph.node_ids_sorted():
        node = graph.nodes[nid]
        lines.append(f"NODE|{node.id}|{node.priority}")
    for eid in sorted(graph.edges.keys()):
        e = graph.edges[eid]
        lines.append(f"EDGE|{e.id}|{e.source}|{e.destination}|{e.latency}|{e.activation_state}|{e.tensor_dependency}")
    if tensor_root is not None:
        for t in sorted(tensor_root.flatten(), key=lambda n: n.id):
            lines.append(f"TENSOR|{t.id}|{','.join(map(str, t.shape))}|{t.dtype}")
    lines.append(f"RANK|{rank_value}|{rank_source}")
    lines.append(f"LATENCY|{route_total_latency}|{bottleneck_node}")
    lines.append(f"PREV|{prev_hash}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def state_hash(*args, **kwargs) -> str:
    return hashlib.sha256(canonical_payload(*args, **kwargs)).hexdigest()


@dataclass
class NetworkState:
    """One S_i in the chain S_0 -> S_1 -> ... -> S_n."""

    index: int
    network_name: str
    network_version: str
    prev_hash: str
    hash: str
    rank: Optional[int]
    rank_source: Optional[str]
    route_total_latency: Optional[float]
    bottleneck_node: Optional[str]
    adaptation_applied: bool
    triggering_conditions: List[str] = field(default_factory=list)
    changed_nodes: List[str] = field(default_factory=list)
    changed_edges: List[str] = field(default_factory=list)
    verification_passed: bool = True
    timestamp_utc: Optional[str] = None   # NOT part of the hashed payload -- see canonical_payload

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @staticmethod
    def from_json(text: str) -> "NetworkState":
        data = json.loads(text)
        return NetworkState(**data)


def build_network_state(
    index: int,
    network_name: str,
    network_version: str,
    graph: SparseGraph,
    tensor_root: Optional[TensorNode],
    rank_value: Optional[int],
    rank_source: Optional[str],
    route_total_latency: Optional[float],
    bottleneck_node: Optional[str],
    prev_hash: str,
    adaptation_applied: bool,
    triggering_conditions: List[str],
    changed_nodes: List[str],
    changed_edges: List[str],
    verification_passed: bool,
    timestamp_utc: Optional[str] = None,
) -> NetworkState:
    h = state_hash(
        network_name, network_version, graph, tensor_root,
        rank_value, rank_source, route_total_latency, bottleneck_node, prev_hash,
    )
    return NetworkState(
        index=index,
        network_name=network_name,
        network_version=network_version,
        prev_hash=prev_hash,
        hash=h,
        rank=rank_value,
        rank_source=rank_source,
        route_total_latency=route_total_latency,
        bottleneck_node=bottleneck_node,
        adaptation_applied=adaptation_applied,
        triggering_conditions=list(triggering_conditions),
        changed_nodes=list(changed_nodes),
        changed_edges=list(changed_edges),
        verification_passed=verification_passed,
        timestamp_utc=timestamp_utc,
    )
