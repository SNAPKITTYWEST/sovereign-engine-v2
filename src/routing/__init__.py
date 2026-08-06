"""
Sovereign Routing Engine
Custom sparse-activation MoE pipeline

Stages:
  1. RegexParser       — tokenize + extract signals
  2. ASTBuilder        — structured parse tree
  3. SymbolicGraph     — weighted adjacency matrix
  4. JordanTransformer — eigendecompose, stability scores
  5. JacobianLens      — routing sensitivity analysis
  6. ConstraintEval    — filter invalid expert paths
  7. SparseActivation  — top-k gating + routing weights
  8. RoutingNodes      — per-expert gating functions
  9. NANDFilter        — conflict resolution
  10. AgentDispatch    — fire selected experts
  11. MergeOutput      — weighted recombine
"""

from .pipeline import RoutingPipeline
from .sparse import SparseActivation, RoutingWeights
from .dispatch import AgentDispatch, DispatchResult

__all__ = ["RoutingPipeline", "SparseActivation", "RoutingWeights", "AgentDispatch", "DispatchResult"]
