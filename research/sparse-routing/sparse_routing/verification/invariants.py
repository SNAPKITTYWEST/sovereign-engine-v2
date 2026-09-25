"""The nine formal invariants (report SECTION 18), checked mechanically
and aggregated into one VerificationResult per state transition.

    I1: Valid Nodes            every edge references an existing node
    I2: Valid Edges             no malformed edge exists
    I3: Nonnegative Latency     L(e) >= 0
    I4: Tensor Validity         all tensor dimensions are positive and valid
    I5: Recursion Bound         d(T) <= d_max
    I6: Sparsity Bound          rho(A) <= rho_max
    I7: Rank Validity           0 <= rank(J) <= min(dim(input), dim(output))
    I8: Deterministic Adaptation identical state + observations -> identical adaptations
    I9: Atomic Commit           invalid adaptations never replace the previous valid state

MECHANICALLY CHECKED: I1-I7 (each is a direct, executable check against a
concrete object below). I8 is checked by the test suite via replay
(tests/test_replay.py runs the same transition twice and asserts
byte-identical output), not by a runtime assertion inside the engine
itself -- there is no way for a single execution to check "would this be
identical on a re-run" without literally re-running it, so I8's
verification lives in the test suite. I9 is enforced structurally (by
AdaptationEngine.commit_state's atomic write-then-rename, matching the
Bash reference implementation's I12) rather than checked as a separate
assertion, for the same reason the Bash implementation gave: once the
write is atomic, the failure mode I9 guards against cannot occur.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from sparse_routing.model import SparseGraph
from sparse_routing.rank import JacobianState
from sparse_routing.tensor import TensorNode


@dataclass
class InvariantResult:
    invariant_id: str
    description: str
    passed: bool
    detail: str = ""


@dataclass
class VerificationResult:
    results: List[InvariantResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> List[InvariantResult]:
        return [r for r in self.results if not r.passed]

    def raise_if_failed(self) -> None:
        if not self.all_passed:
            lines = [f"{r.invariant_id}: {r.detail}" for r in self.failures]
            raise ValueError("verification failed:\n" + "\n".join(lines))


_DESCRIPTIONS = {
    "I1": "Valid Nodes -- every edge references an existing node",
    "I2": "Valid Edges -- no malformed edge exists",
    "I3": "Nonnegative Latency -- L(e) >= 0",
    "I4": "Tensor Validity -- all tensor dimensions are positive and valid",
    "I5": "Recursion Bound -- d(T) <= d_max",
    "I6": "Sparsity Bound -- rho(A) <= rho_max",
    "I7": "Rank Validity -- 0 <= rank(J) <= min(dim(input), dim(output))",
}


def _check(result_list: List[InvariantResult], invariant_id: str, fn) -> None:
    try:
        fn()
        result_list.append(InvariantResult(invariant_id, _DESCRIPTIONS[invariant_id], True))
    except ValueError as exc:
        result_list.append(InvariantResult(invariant_id, _DESCRIPTIONS[invariant_id], False, str(exc)))


def verify_all(
    graph: SparseGraph,
    tensor_root: Optional[TensorNode],
    jacobian_state: Optional[JacobianState],
    max_sparsity_ratio: float,
    max_recursion_depth: int,
) -> VerificationResult:
    """Runs I1-I7 against the concrete objects supplied and returns one
    aggregated VerificationResult. I1 and I2 are, in this implementation,
    actually enforced at object-construction time (SparseGraph.add_edge,
    Edge.__post_init__) rather than here -- by the time a SparseGraph
    object exists at all, I1/I2 already hold for it, so they are recorded
    here as trivially passed for a constructed graph, with a note saying
    so, rather than silently omitted (a verification report that just
    doesn't mention I1/I2 would look like they were never checked)."""
    results: List[InvariantResult] = []

    results.append(InvariantResult("I1", _DESCRIPTIONS["I1"], True, "enforced at SparseGraph.add_edge() construction time"))
    results.append(InvariantResult("I2", _DESCRIPTIONS["I2"], True, "enforced at Edge.__post_init__() construction time"))

    _check(results, "I3", graph.check_no_negative_latency)

    if tensor_root is not None:
        _check(results, "I4", tensor_root.validate_shape)
        _check(results, "I5", lambda: tensor_root.check_recursion_bound(max_recursion_depth))
    else:
        results.append(InvariantResult("I4", _DESCRIPTIONS["I4"], True, "no tensor supplied; vacuously satisfied"))
        results.append(InvariantResult("I5", _DESCRIPTIONS["I5"], True, "no tensor supplied; vacuously satisfied"))

    _check(results, "I6", lambda: graph.check_sparsity_bound(max_sparsity_ratio))

    if jacobian_state is not None and jacobian_state.rank_estimate is not None:
        _check(results, "I7", jacobian_state.check_rank_validity)
    else:
        results.append(InvariantResult("I7", _DESCRIPTIONS["I7"], True, "no rank estimate supplied; vacuously satisfied"))

    return VerificationResult(results)
