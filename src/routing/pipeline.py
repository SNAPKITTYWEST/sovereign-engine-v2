"""
Full Routing Pipeline — all 11 stages wired together.

Usage:
    pipeline = RoutingPipeline(
        experts={"code_agent": my_code_fn, "query_agent": my_query_fn},
        top_k=2
    )
    result = await pipeline.route("write a python fibonacci function")
    print(result.merged_output)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .parser import ASTBuilder, ParseResult
from .symbolic import SymbolicGraph, JordanTransformer, SymbolicGraphResult, JordanResult
from .jacobian import JacobianLens, JacobianAnalysis
from .constraints import ConstraintEval, ConstraintEvalResult
from .sparse import SparseActivation, RoutingWeights, RoutingNode, NANDFilter, build_default_routing_nodes
from .dispatch import AgentDispatch, DispatchResult, Expert


@dataclass
class PipelineTrace:
    """Full trace of all routing decisions — for debugging / observability."""
    input_text: str
    parse: ParseResult
    graph: SymbolicGraphResult
    jordan: JordanResult
    jacobian: JacobianAnalysis
    constraints: ConstraintEvalResult
    routing: RoutingWeights
    dispatch: DispatchResult

    def summary(self) -> dict[str, Any]:
        return {
            "intent":          self.parse.intent,
            "confidence":      round(self.parse.confidence, 4),
            "signals":         {k: round(v, 4) for k, v in self.parse.signals.items()},
            "stability_score": round(self.jordan.routing_features.get("stability_score", 0), 4),
            "spectral_radius": round(self.jordan.routing_features.get("spectral_radius", 0), 4),
            "condition_number": round(self.jacobian.condition_number, 4),
            "dead_experts":    self.jacobian.dead_experts,
            "blocked_experts": [r.expert for r in self.constraints.per_expert if not r.allowed],
            "active_experts":  self.routing.active_experts,
            "nand_suppressed": self.routing.nand_suppressed,
            "weights":         {k: round(v, 4) for k, v in self.routing.weights.items() if v > 0},
            "success_count":   self.dispatch.success_count,
            "failed_experts":  self.dispatch.failed_experts,
        }


class RoutingPipeline:
    """
    Sovereign MoE Routing Pipeline.

    Stages:
      1.  RegexParser          — tokenize input
      2.  ASTBuilder           — build parse tree
      3.  SymbolicGraph        — AST → adjacency matrix
      4.  JordanTransformer    — eigendecompose graph
      5.  JacobianLens         — routing sensitivity analysis
      6.  ConstraintEval       — filter invalid paths
      7.  SparseActivation     — top-k gating
      8.  RoutingNodes         — per-expert gating scores
      9.  NANDFilter           — conflict resolution
      10. AgentDispatch        — fire experts concurrently
      11. MergeOutput          — weighted recombine
    """

    def __init__(
        self,
        experts: dict[str, Expert],
        top_k: int = 2,
        routing_nodes: dict[str, RoutingNode] | None = None,
        nand_conflicts: list[tuple[str, str]] | None = None,
        merge_strategy: str = "weighted_concat",
        expert_timeout_ms: int = 30000
    ):
        self.experts = experts
        self.expert_names = list(experts.keys())
        self.top_k = top_k

        # Build routing nodes (default if not provided)
        self.routing_nodes = routing_nodes or build_default_routing_nodes(self.expert_names)

        # NAND filter
        self.nand_filter = NANDFilter()
        for a, b in (nand_conflicts or []):
            self.nand_filter.register_conflict(a, b)

        # Stage components
        self._ast_builder = ASTBuilder()
        self._sym_graph = SymbolicGraph()
        self._jordan = JordanTransformer()
        self._jacobian = JacobianLens()
        self._constraint_eval = ConstraintEval()
        self._sparse = SparseActivation(
            top_k=top_k,
            routing_nodes=self.routing_nodes,
            nand_filter=self.nand_filter
        )
        self._dispatch = AgentDispatch(
            experts=experts,
            timeout_ms=expert_timeout_ms,
            merge_strategy=merge_strategy
        )

    async def route(
        self,
        input_text: str,
        context: dict[str, Any] | None = None
    ) -> DispatchResult:
        trace = await self.route_with_trace(input_text, context)
        return trace.dispatch

    async def route_with_trace(
        self,
        input_text: str,
        context: dict[str, Any] | None = None
    ) -> PipelineTrace:
        ctx = context or {}

        # Stage 1 + 2: Parse
        parse = self._ast_builder.full_parse(input_text)

        # Stage 3: Symbolic graph
        graph = self._sym_graph.build(parse)

        # Stage 4: Jordan analysis
        jordan = self._jordan.analyze(graph)

        # Stage 5: Jacobian lens
        def routing_fn(signals: dict[str, float]) -> dict[str, float]:
            scores = {}
            for name in self.expert_names:
                node = self.routing_nodes.get(name)
                scores[name] = node.gate(signals) if node else 0.0
            return scores

        jacobian = self._jacobian.analyze(
            routing_fn=routing_fn,
            signals=parse.signals,
            expert_names=self.expert_names
        )

        # Initial routing weights (pre-constraint) for constraint context
        pre_weights = routing_fn(parse.signals)

        # Stage 6: Constraint evaluation
        constraints = self._constraint_eval.evaluate(
            expert_names=self.expert_names,
            parse=parse,
            jordan=jordan,
            routing_weights=pre_weights
        )

        # Stage 7 + 8 + 9: Sparse activation + routing nodes + NAND filter
        routing = self._sparse.compute(
            signals=parse.signals,
            expert_names=self.expert_names,
            expert_mask=constraints.expert_mask,
            jordan_features=jordan.routing_features
        )

        # Stage 10 + 11: Dispatch + merge
        dispatch_result = await self._dispatch.dispatch(
            input_text=input_text,
            context={**ctx, "parse": parse, "routing": routing},
            routing=routing
        )

        trace = PipelineTrace(
            input_text=input_text,
            parse=parse,
            graph=graph,
            jordan=jordan,
            jacobian=jacobian,
            constraints=constraints,
            routing=routing,
            dispatch=dispatch_result
        )

        return trace

    def add_nand_conflict(self, expert_a: str, expert_b: str, reason: str = "") -> None:
        self.nand_filter.register_conflict(expert_a, expert_b, reason)

    def add_constraint(self, constraint) -> None:
        self._constraint_eval.add_constraint(constraint)

    def get_routing_node(self, expert_name: str) -> RoutingNode | None:
        return self.routing_nodes.get(expert_name)
