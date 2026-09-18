"""Jacobian calculation, rank estimation -- I7, and the exact/numerical/
structural distinction (report SECTION 6/14)."""
import numpy as np
import pytest

from sparse_routing.rank import (
    JacobianState,
    exact_rank,
    finite_difference_jacobian,
    numerical_rank,
    structural_rank,
)


def test_exact_rank_of_rank_deficient_matrix(rank_deficient_matrix):
    result = exact_rank(rank_deficient_matrix)
    assert result.rank == 2
    assert result.source == "exact"


def test_exact_rank_of_identity(identity_matrix):
    result = exact_rank(identity_matrix)
    assert result.rank == 3
    assert result.source == "exact"


def test_numerical_rank_records_its_tolerance(rank_deficient_matrix):
    result = numerical_rank(rank_deficient_matrix)
    assert result.source == "numerical"
    assert result.tau is not None  # never silently omitted, even when defaulted
    assert result.rank == 2


def test_numerical_rank_explicit_tau_overrides_default(rank_deficient_matrix):
    result = numerical_rank(rank_deficient_matrix, tau=1e-10)
    assert result.tau == 1e-10


def test_finite_difference_jacobian_matches_closed_form_within_tolerance():
    """Deterministic linear example: f(x) = A @ x, so its true Jacobian is
    exactly A, independent of x. The finite-difference approximation
    (h=1e-3, chosen to keep floating-point rounding error small relative
    to the near-zero true singular value) must agree with A to within a
    small, explicitly checked, real error bound."""
    A = np.array([[1.0, 1.0, 0.0], [0.0, 1.0, 1.0], [1.0, 2.0, 1.0]])

    def f(x):
        return A @ x

    x0 = np.array([1.0, 2.0, 3.0])
    J_fd = finite_difference_jacobian(f, x0, h=1e-3)
    max_error = np.max(np.abs(J_fd - A))
    assert max_error < 1e-8  # real, measured error -- see docs/report.md SECTION 14


def test_numerical_rank_instability_with_small_h_is_real_and_reproducible():
    """Documents a genuine, reproducible finding (report SECTION 22): a
    too-small finite-difference step size introduces rounding-error noise
    into the smallest singular value that a default tolerance can
    misclassify as nonzero, disagreeing with the true rank. This is
    stated as a known instability, not hidden."""
    A = np.array([[1.0, 1.0, 0.0], [0.0, 1.0, 1.0], [1.0, 2.0, 1.0]])  # true rank 2

    def f(x):
        return A @ x

    x0 = np.array([1.0, 2.0, 3.0])
    J_fd_tiny_h = finite_difference_jacobian(f, x0, h=1e-6)
    result = numerical_rank(J_fd_tiny_h)  # default tau
    # With h=1e-6, rounding-error noise in the 3rd singular value exceeds
    # the default tolerance, so numerical rank disagrees with true rank 2.
    assert result.rank == 3
    assert result.singular_values[-1] > result.tau


def test_structural_rank_is_capped_and_labeled(rank_deficient_matrix):
    result = structural_rank(active_tensor_dependency_count=5, cap=3)
    assert result.rank == 3
    assert result.source == "structural"
    result2 = structural_rank(active_tensor_dependency_count=1, cap=3)
    assert result2.rank == 1


def test_I7_rank_validity(identity_matrix):
    js = JacobianState("f", 3, 3, thresholds_min=0, thresholds_max=3, slack=0)
    js.rank_estimate = exact_rank(identity_matrix)
    js.check_rank_validity()  # 0 <= 3 <= 3, should not raise


def test_threshold_consistency_rejects_impossible_bounds():
    js = JacobianState("f", 3, 3, thresholds_min=3, thresholds_max=1, slack=0)
    with pytest.raises(ValueError):
        js.check_threshold_consistency()

    js2 = JacobianState("f", 2, 3, thresholds_min=0, thresholds_max=3, slack=0)  # upper bound is 2
    with pytest.raises(ValueError):
        js2.check_threshold_consistency()


def test_rank_mismatch_against_configured_thresholds(rank_deficient_matrix):
    """Real rank is 2, but thresholds declare only rank 3 acceptable."""
    js = JacobianState("f", 3, 3, thresholds_min=3, thresholds_max=3, slack=0)
    js.rank_estimate = exact_rank(rank_deficient_matrix)
    with pytest.raises(ValueError, match="outside configured thresholds"):
        js.check_within_configured_thresholds()
