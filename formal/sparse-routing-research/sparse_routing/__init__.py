"""Sparse Latency Routing with Jacobian-Rank Adaptation — Python reference implementation.

Package layout (deliberately not a monolithic script — see docs/report.md
SECTION 12):

    model/          Node, Edge, SparseGraph — the graph data model
    tensor/         TensorNode — the recursive tensor model
    rank/           JacobianState, rank estimation (exact / numerical / structural)
    routing/        LatencyState, RoutingState, Dijkstra routing
    adaptation/     AdaptationRule, RoutingState transitions, the adaptation engine
    verification/   VerificationResult, the nine formal invariants (I1-I9)
    serialization/  deterministic state hashing, JSON state emission, replay
    parser/         lexer -> tokens -> AST -> validated model, from canonical XML
"""

__version__ = "1.0.0"
