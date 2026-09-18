"""The adaptation engine (report SECTION 16): a deterministic state
transition function S_t -> S_{t+1} = F(S_t), built from exactly the
pipeline SECTION 16 specifies:

    observe() -> measure_latency() -> estimate_rank() -> evaluate_routes()
    -> propose_adaptation() -> verify_adaptation() -> commit_state()

If verify_adaptation() fails (or the proposal is infeasible), commit_state()
does NOT commit: the previous valid state is preserved (I9), and the
rejection is recorded in the engine's own bookkeeping (`rejected_count`,
`history_of_attempts`) so a caller (the experiment, the tests) can report
it as a real event, not silence it.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sparse_routing.model import Edge, SparseGraph
from sparse_routing.rank import JacobianState, RankEstimate
from sparse_routing.routing import LatencyState, RoutingState
from sparse_routing.serialization.state import NetworkState, build_network_state
from sparse_routing.tensor import TensorNode
from sparse_routing.verification import VerificationResult, verify_all

CONDITIONS = (
    "latency_exceeds_threshold",
    "rank_decreases",
    "rank_increases",
    "tensor_dimension_changes",
    "sparsity_exceeds_maximum",
)
ACTIONS = (
    "evaluate_alternate_route",
    "evaluate_redundant_edge_removal",
    "evaluate_capacity_expansion",
    "recompute_dependent_routing_metadata",
    "reject_topology_expansion",
)


@dataclass(frozen=True)
class AdaptationRule:
    id: str
    condition: str
    action: str

    def __post_init__(self) -> None:
        if self.condition not in CONDITIONS:
            raise ValueError(f"unknown adaptation condition: {self.condition!r}")
        if self.action not in ACTIONS:
            raise ValueError(f"unknown adaptation action: {self.action!r}")


DEFAULT_RULES: Tuple[AdaptationRule, ...] = (
    AdaptationRule("r1", "latency_exceeds_threshold", "evaluate_alternate_route"),
    AdaptationRule("r2", "rank_decreases", "evaluate_redundant_edge_removal"),
    AdaptationRule("r3", "rank_increases", "evaluate_capacity_expansion"),
    AdaptationRule("r4", "tensor_dimension_changes", "recompute_dependent_routing_metadata"),
    AdaptationRule("r5", "sparsity_exceeds_maximum", "reject_topology_expansion"),
)


@dataclass
class AdaptationProposal:
    """The output of propose_adaptation(): every triggering condition
    found (I8's 'traceable to an explicit rule' -- each entry here names
    the rule that fired), which edges would be pruned if committed, and
    whether the proposal is feasible at all."""

    triggering_conditions: List[str] = field(default_factory=list)
    edges_to_prune: List[str] = field(default_factory=list)
    feasible: bool = True
    infeasible_reason: str = ""


def _find_redundant_edge(graph: SparseGraph) -> Optional[str]:
    """Deterministic pick: among active edges whose destination has more
    than one active incoming edge (so removing this one would not
    disconnect that destination), choose the lowest routing_priority,
    tie-broken by lexicographically smallest edge id. O(|E|^2) worst case
    (in_degree is O(|E|) and is called once per edge) -- acceptable for
    the small graphs this reference implementation targets; see
    docs/report.md SECTION 22 for why this was not optimized further."""
    candidate: Optional[str] = None
    candidate_priority = None
    for eid in sorted(graph.edges.keys()):
        e = graph.edges[eid]
        if not e.is_active:
            continue
        if graph.in_degree(e.destination, active_only=True) > 1:
            if candidate is None or e.routing_priority < candidate_priority or (
                e.routing_priority == candidate_priority and eid < candidate
            ):
                candidate = eid
                candidate_priority = e.routing_priority
    return candidate


class AdaptationEngine:
    """Owns the live SparseGraph/TensorNode/JacobianState/LatencyState and
    the S_0 -> S_1 -> ... -> S_n history. Every public method below
    corresponds directly to one item in report SECTION 16's required
    pipeline."""

    def __init__(
        self,
        network_name: str,
        network_version: str,
        graph: SparseGraph,
        tensor_root: Optional[TensorNode],
        jacobian_state: Optional[JacobianState],
        routing_state: RoutingState,
        latency_state: LatencyState,
        rules: Tuple[AdaptationRule, ...] = DEFAULT_RULES,
        max_recursion_depth: int = 8,
    ) -> None:
        self.network_name = network_name
        self.network_version = network_version
        self.graph = graph
        self.tensor_root = tensor_root
        self.jacobian_state = jacobian_state
        self.routing_state = routing_state
        self.latency_state = latency_state
        self.rules = rules
        self.max_recursion_depth = max_recursion_depth

        self.history: List[NetworkState] = []
        self.rejected_count = 0
        self._prev_tensor_shapes: Dict[str, tuple] = self._current_tensor_shapes()

    def _current_tensor_shapes(self) -> Dict[str, tuple]:
        if self.tensor_root is None:
            return {}
        return {t.id: t.shape for t in self.tensor_root.flatten()}

    def _rule_declared(self, condition: str) -> bool:
        return any(r.condition == condition for r in self.rules)

    # -- SECTION 16 pipeline ------------------------------------------------

    def observe(self) -> Dict[str, object]:
        """Raw, un-evaluated observation of the current graph/tensor
        state -- no comparison to previous state happens here yet."""
        return {
            "sparsity_ratio": self.graph.sparsity_ratio(),
            "tensor_shapes": self._current_tensor_shapes(),
            "active_edge_count": sum(1 for _ in self.graph.active_edges()),
        }

    def measure_latency(self, benchmark: bool = False):
        return self.latency_state.compute(self.graph, self.routing_state.root, benchmark=benchmark)

    def estimate_rank(self, rank_estimate: RankEstimate) -> None:
        """Rank estimation itself (exact/numerical/structural) is
        performed by sparse_routing.rank -- this method's job is only to
        record the result onto this engine's JacobianState, so every
        subsequent step in the pipeline reads it from one place."""
        if self.jacobian_state is None:
            raise ValueError("no JacobianState configured on this engine")
        self.jacobian_state.rank_estimate = rank_estimate
        self.jacobian_state.check_rank_validity()  # I7, fail fast

    def evaluate_routes(self) -> bool:
        """Returns True if the current minimal route satisfies the
        latency objective (does NOT exceed threshold)."""
        return not self.latency_state.exceeds_threshold()

    def propose_adaptation(self, previous_rank: Optional[int]) -> AdaptationProposal:
        proposal = AdaptationProposal()

        if self.latency_state.exceeds_threshold():
            proposal.triggering_conditions.append("latency_exceeds_threshold")
            if self._rule_declared("latency_exceeds_threshold"):
                # Dijkstra already found the true latency-minimal route
                # under the active topology (report SECTION 5): if that
                # minimal route itself exceeds threshold, no alternate
                # route in this topology can do better. This is a real
                # proof of infeasibility given nonnegative edge weights
                # (I3), not a simulated one.
                proposal.feasible = False
                proposal.infeasible_reason = (
                    f"route_total_latency={self.latency_state.route_total_latency()} "
                    f"exceeds threshold={self.latency_state.threshold}; no alternate route "
                    f"in this topology can improve on Dijkstra's minimum"
                )

        current_rank = self.jacobian_state.rank_estimate.rank if (self.jacobian_state and self.jacobian_state.rank_estimate) else None
        if previous_rank is not None and current_rank is not None:
            if current_rank < previous_rank:
                proposal.triggering_conditions.append("rank_decreases")
                if self._rule_declared("rank_decreases"):
                    redundant = _find_redundant_edge(self.graph)
                    if redundant is not None:
                        proposal.edges_to_prune.append(redundant)
            elif current_rank > previous_rank:
                proposal.triggering_conditions.append("rank_increases")
                if self._rule_declared("rank_increases"):
                    if not self.routing_state.allow_expansion:
                        # This engine never fabricates edges that aren't
                        # already declared -- there is no larger topology
                        # to "expand" into, so the expansion is rejected,
                        # not silently granted.
                        proposal.triggering_conditions.append("sparsity_exceeds_maximum")

        current_shapes = self._current_tensor_shapes()
        if current_shapes != self._prev_tensor_shapes:
            proposal.triggering_conditions.append("tensor_dimension_changes")
            # rule r4's action, recompute_dependent_routing_metadata, is a
            # no-op marker here: this engine recomputes routing metadata
            # (latency, rank validity) from live objects on every step
            # regardless, so there is nothing additional to "recompute" --
            # the condition is still recorded for I8 traceability.

        if self.graph.sparsity_ratio() > self.routing_state.sparsity_max_ratio:
            if "sparsity_exceeds_maximum" not in proposal.triggering_conditions:
                proposal.triggering_conditions.append("sparsity_exceeds_maximum")
            proposal.feasible = False
            proposal.infeasible_reason = (
                f"sparsity ratio {self.graph.sparsity_ratio()} exceeds "
                f"max_ratio {self.routing_state.sparsity_max_ratio}"
            )

        return proposal

    def verify_adaptation(self, proposal: AdaptationProposal) -> VerificationResult:
        """Builds a TRIAL copy of the graph with the proposal's edge
        prunes applied, and runs the full I1-I7 verification suite
        against that trial copy -- the real graph is never mutated here,
        only a deepcopy, so a failed verification leaves the live state
        completely untouched even before commit_state() runs."""
        trial_graph = copy.deepcopy(self.graph)
        for eid in proposal.edges_to_prune:
            trial_graph.edges[eid].activation_state = "pruned"

        return verify_all(
            trial_graph,
            self.tensor_root,
            self.jacobian_state,
            self.routing_state.sparsity_max_ratio,
            self.max_recursion_depth,
        )

    def commit_state(
        self,
        proposal: AdaptationProposal,
        verification: VerificationResult,
        timestamp_utc: Optional[str] = None,
    ) -> NetworkState:
        """I9: an infeasible proposal or a failed verification NEVER
        replaces the previous valid state. On success, edge prunes are
        applied to the REAL graph (only now, after verification passed)
        and a new NetworkState is appended to history."""
        committed = proposal.feasible and verification.all_passed

        if not committed:
            self.rejected_count += 1
            if self.history:
                return self.history[-1]
            # No previous state exists yet (this was the very first
            # observation) -- there is nothing valid to "preserve" other
            # than an explicit empty/rejected marker.
            state = build_network_state(
                index=0,
                network_name=self.network_name,
                network_version=self.network_version,
                graph=self.graph,
                tensor_root=self.tensor_root,
                rank_value=self.jacobian_state.rank_estimate.rank if (self.jacobian_state and self.jacobian_state.rank_estimate) else None,
                rank_source=self.jacobian_state.rank_estimate.source if (self.jacobian_state and self.jacobian_state.rank_estimate) else None,
                route_total_latency=None,
                bottleneck_node=None,
                prev_hash="GENESIS",
                adaptation_applied=False,
                triggering_conditions=proposal.triggering_conditions,
                changed_nodes=[],
                changed_edges=[],
                verification_passed=False,
                timestamp_utc=timestamp_utc,
            )
            return state

        for eid in proposal.edges_to_prune:
            self.graph.edges[eid].activation_state = "pruned"

        prev_hash = self.history[-1].hash if self.history else "GENESIS"
        self._prev_tensor_shapes = self._current_tensor_shapes()

        state = build_network_state(
            index=len(self.history),
            network_name=self.network_name,
            network_version=self.network_version,
            graph=self.graph,
            tensor_root=self.tensor_root,
            rank_value=self.jacobian_state.rank_estimate.rank if (self.jacobian_state and self.jacobian_state.rank_estimate) else None,
            rank_source=self.jacobian_state.rank_estimate.source if (self.jacobian_state and self.jacobian_state.rank_estimate) else None,
            route_total_latency=self.latency_state.route_total_latency(),
            bottleneck_node=self.latency_state.bottleneck_node(),
            prev_hash=prev_hash,
            adaptation_applied=bool(proposal.edges_to_prune),
            triggering_conditions=proposal.triggering_conditions,
            changed_nodes=[],
            changed_edges=list(proposal.edges_to_prune),
            verification_passed=True,
            timestamp_utc=timestamp_utc,
        )
        self.history.append(state)
        return state

    def step(self, previous_rank: Optional[int], rank_estimate: RankEstimate, benchmark: bool = False) -> NetworkState:
        """Convenience wrapper chaining the full SECTION 16 pipeline for
        one discrete timestep. Returns the resulting NetworkState (which
        is the PREVIOUS state, unchanged, if this step's proposal was
        rejected -- see commit_state's I9 handling)."""
        self.observe()
        self.measure_latency(benchmark=benchmark)
        self.estimate_rank(rank_estimate)
        self.evaluate_routes()
        proposal = self.propose_adaptation(previous_rank)
        verification = self.verify_adaptation(proposal)
        return self.commit_state(proposal, verification)
