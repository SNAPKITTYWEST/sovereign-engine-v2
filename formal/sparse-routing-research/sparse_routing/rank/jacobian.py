"""Jacobian state and rank estimation (report SECTION 6 and SECTION 14).

    y = f(x),  J(x) = df/dx,  r_J = rank(J)

FORMALLY DEFINED: J(x) as the matrix of partial derivatives, and rank(J)
as its usual linear-algebra rank (dimension of the column space).

DEPENDENCY DISCLOSURE (required by report SECTION 14): this module does
NOT use automatic differentiation. `finite_difference_jacobian` computes
a NUMERICAL approximation to J via central finite differences; it is not
exact and its error is bounded by the step size `h` and the function's
local curvature, not zero. Where the true J is known in closed form (the
deterministic example in `experiments/run_experiment.py` is linear, so its
J is exactly its coefficient matrix, independent of x), that closed-form
matrix is used directly and labeled EXACT, and the finite-difference
approximation is compared against it so its error is a real measured
number, not an assumption.

HEURISTIC (explicitly labeled, never conflated with the two rank
categories above): `structural_rank` counts distinct active tensor
dependencies in a routing graph as a proxy for "how many independent
paths carry distinguishable state." It is NOT a claim about rank(J) and
is capped only so it stays in the same numeric range for comparison
purposes, not because that cap has any linear-algebra meaning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

import numpy as np


@dataclass
class RankEstimate:
    """The result of one rank computation, always carrying its own
    provenance (`source`) and, for numerical estimates, the exact
    tolerance used -- so a caller can never receive a rank value without
    also being told how it was obtained. This is the mechanism that makes
    'never silently choose a tolerance' true structurally rather than by
    convention."""

    rank: int
    source: str                      # "exact" | "numerical" | "structural"
    tau: Optional[float] = None      # tolerance used, only meaningful for "numerical"
    singular_values: List[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.source not in ("exact", "numerical", "structural"):
            raise ValueError(f"unknown rank source: {self.source!r}")
        if self.source == "numerical" and self.tau is None:
            raise ValueError("a 'numerical' RankEstimate must record the tolerance (tau) it used")


def finite_difference_jacobian(
    f: Callable[[np.ndarray], np.ndarray],
    x0: np.ndarray,
    h: float = 1e-6,
) -> np.ndarray:
    """Central-difference NUMERICAL Jacobian approximation.

        J[:, j] ~= (f(x0 + h*e_j) - f(x0 - h*e_j)) / (2h)

    NUMERICALLY TESTED, not exact: truncation error is O(h^2); as h -> 0,
    floating-point cancellation error grows as O(eps/h). `h` is an
    explicit, caller-visible parameter with a stated default -- it is
    never chosen silently inside a black box.

    Complexity: O(n) evaluations of f (n = len(x0)), each of cost O(f).
    """
    x0 = np.asarray(x0, dtype=float)
    n = x0.shape[0]
    y0 = np.asarray(f(x0), dtype=float)
    m = y0.shape[0]
    J = np.zeros((m, n), dtype=float)
    for j in range(n):
        e_j = np.zeros(n)
        e_j[j] = 1.0
        plus = np.asarray(f(x0 + h * e_j), dtype=float)
        minus = np.asarray(f(x0 - h * e_j), dtype=float)
        J[:, j] = (plus - minus) / (2 * h)
    return J


def numerical_rank(J: np.ndarray, tau: Optional[float] = None) -> RankEstimate:
    """rank(J) = number of singular values sigma_i satisfying sigma_i > tau.

    If `tau` is not given, the default matches numpy/LAPACK convention
    (`max(J.shape) * eps * sigma_max`) -- but the value actually used is
    ALWAYS returned in the result, so a caller reading `RankEstimate.tau`
    never has to guess what tolerance was applied, even when it was
    defaulted rather than supplied.
    """
    J = np.asarray(J, dtype=float)
    singular_values = np.linalg.svd(J, compute_uv=False)
    if tau is None:
        eps = np.finfo(J.dtype if J.dtype.kind == "f" else float).eps
        sigma_max = float(singular_values[0]) if singular_values.size else 0.0
        tau = max(J.shape) * eps * sigma_max
    rank = int(np.sum(singular_values > tau))
    return RankEstimate(rank=rank, source="numerical", tau=float(tau), singular_values=[float(s) for s in singular_values])


def exact_rank(J: np.ndarray) -> RankEstimate:
    """Rank of a matrix known in closed form (e.g. the constant Jacobian
    of a linear f). This still runs SVD under the hood (there is no
    "more exact" numerical algorithm than SVD for rank), but is labeled
    EXACT because J itself is not an approximation -- there is no
    finite-difference or automatic-differentiation error in how J was
    obtained, only ordinary floating-point rounding in evaluating known
    constants, which is negligible for the small integer/rational
    matrices used in this reference implementation's example."""
    estimate = numerical_rank(J)
    return RankEstimate(rank=estimate.rank, source="exact", tau=None, singular_values=estimate.singular_values)


def structural_rank(active_tensor_dependency_count: int, cap: int) -> RankEstimate:
    """HEURISTIC. See module docstring: capped count of distinct active
    tensor dependencies, never described as rank(J) itself."""
    return RankEstimate(rank=min(active_tensor_dependency_count, cap), source="structural")


@dataclass
class JacobianState:
    """J_t of report SECTION 7's state tuple S_t = (G_t, T_t, J_t, L_t)."""

    function_name: str
    input_dim: int
    output_dim: int
    matrix: Optional[np.ndarray] = None      # None if no real matrix/function is available
    rank_estimate: Optional[RankEstimate] = None
    thresholds_min: int = 0
    thresholds_max: int = 0
    slack: int = 0

    def upper_bound(self) -> int:
        return min(self.input_dim, self.output_dim)

    def check_threshold_consistency(self) -> None:
        """Configuration sanity, checked before any rank is even computed:
        the declared [min, max] window must itself be achievable for a
        map of this input/output dimension."""
        ub = self.upper_bound()
        if self.thresholds_min < 0 or self.thresholds_max > ub or self.thresholds_min > self.thresholds_max:
            raise ValueError(
                f"jacobian/rank thresholds [{self.thresholds_min},{self.thresholds_max}] "
                f"are invalid for a {self.input_dim}x{self.output_dim} map (max possible rank {ub})"
            )

    def check_rank_validity(self) -> None:
        """I7: 0 <= rank(J) <= min(dim(input), dim(output))."""
        if self.rank_estimate is None:
            raise ValueError("check_rank_validity called before a rank was estimated")
        r = self.rank_estimate.rank
        ub = self.upper_bound()
        if not (0 <= r <= ub):
            raise ValueError(f"I7 violation: rank {r} outside valid range [0,{ub}]")

    def check_within_configured_thresholds(self) -> None:
        """Not one of I1-I9, but a configured operational bound (this
        system's equivalent of the Bash engine's I9 'rank mismatch'
        check) -- kept separate from I7 because I7 is a mathematical
        validity constraint, while this is a policy choice the operator
        configured."""
        if self.rank_estimate is None:
            raise ValueError("check_within_configured_thresholds called before a rank was estimated")
        r = self.rank_estimate.rank
        if not (self.thresholds_min <= r <= self.thresholds_max):
            raise ValueError(
                f"rank {r} ({self.rank_estimate.source}) outside configured thresholds "
                f"[{self.thresholds_min},{self.thresholds_max}]"
            )
