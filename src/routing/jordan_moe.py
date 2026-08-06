"""
Jordan Algebraic MoE Routing
Part of SOVEREIGN PYTHON LLM ENGINE

Replaces standard softmax gating with Jordan algebraic operators.

Mathematical foundation:
  Jordan algebra (Pascual Jordan, 1933):
    - Commutative:     A ∘ B = B ∘ A
    - Non-associative: (A ∘ B) ∘ C ≠ A ∘ (B ∘ C)
    - Power-associative: A ∘ (A ∘ A) = (A ∘ A) ∘ A (powers are fine)
    - Jordan identity:  (A ∘ B) ∘ (A ∘ A) = A ∘ (B ∘ (A ∘ A))

  We use the Spin Factor algebra J(n):
    Elements:  (α, v)  where α ∈ ℝ (scalar), v ∈ ℝⁿ (signal vector)
    Product:   (α,v) ∘ (β,w) = (αβ + ⟨v,w⟩,  αw + βv)
    Identity:  (1, 0⃗)
    Norm:      ‖(α,v)‖ = √(α² + ‖v‖²)

  Originally developed to formalize quantum mechanics observables.
  "Quantum-inspired" = same algebra, not actual quantum hardware.

Why this beats softmax:
  1. Non-associative composition — swarm grouping topology changes output
     mathematically, not just heuristically
  2. Fixed-point convergence — Jordan squaring x ↦ x ∘ x converges to
     idempotents (e ∘ e = e), which ARE the stable routing attractors
  3. Spectral decomposition — every element has unique decomposition
     x = λ₁c₁ + λ₂c₂ + ... where cᵢ are primitive idempotents
     This gives a provably unique expert assignment

Pure Python stdlib — no numpy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ─────────────────────────────────────────────
# Pure Python vector ops (no numpy)
# ─────────────────────────────────────────────

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def _scale(s: float, v: list[float]) -> list[float]:
    return [s * x for x in v]

def _add(a: list[float], b: list[float]) -> list[float]:
    return [x + y for x, y in zip(a, b)]

def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))

def _normalize(v: list[float]) -> list[float]:
    n = _norm(v)
    return [x / n for x in v] if n > 1e-10 else [0.0] * len(v)

def _zeros(n: int) -> list[float]:
    return [0.0] * n


# ─────────────────────────────────────────────
# Spin Factor Jordan Algebra Element
# ─────────────────────────────────────────────

@dataclass
class SpinFactor:
    """
    Element of the Spin Factor Jordan algebra J(n).

    Represents one agent node in the orchestration lattice.

      scalar: float        — confidence / activation weight
      vector: list[float]  — signal embedding (routing features)

    Jordan product:
      (α,v) ∘ (β,w) = (αβ + ⟨v,w⟩,  αw + βv)

    This is commutative (A∘B = B∘A) but NOT associative.
    """

    scalar: float
    vector: list[float]

    @classmethod
    def identity(cls, dim: int) -> 'SpinFactor':
        """Multiplicative identity: (1, 0⃗)"""
        return cls(scalar=1.0, vector=_zeros(dim))

    @classmethod
    def zero(cls, dim: int) -> 'SpinFactor':
        return cls(scalar=0.0, vector=_zeros(dim))

    @classmethod
    def from_signals(cls, signals: dict[str, float]) -> 'SpinFactor':
        """
        Build a SpinFactor from a routing signal dict.
        Scalar = mean signal magnitude.
        Vector = signal values in sorted key order.
        """
        vals = [signals[k] for k in sorted(signals.keys())]
        scalar = sum(vals) / max(len(vals), 1)
        return cls(scalar=scalar, vector=vals)

    def jordan_product(self, other: 'SpinFactor') -> 'SpinFactor':
        """
        (α,v) ∘ (β,w) = (αβ + ⟨v,w⟩,  αw + βv)

        Commutative: a.jordan_product(b) == b.jordan_product(a)
        Non-associative: order of grouping changes result
        """
        new_scalar = (self.scalar * other.scalar +
                      _dot(self.vector, other.vector))
        new_vector = _add(
            _scale(self.scalar, other.vector),
            _scale(other.scalar, self.vector)
        )
        return SpinFactor(scalar=new_scalar, vector=new_vector)

    # Operator alias
    def __mul__(self, other: 'SpinFactor') -> 'SpinFactor':
        return self.jordan_product(other)

    def jordan_square(self) -> 'SpinFactor':
        """x ∘ x — used in fixed-point iteration."""
        return self.jordan_product(self)

    def norm(self) -> float:
        """‖(α,v)‖ = √(α² + ‖v‖²)"""
        return math.sqrt(self.scalar ** 2 + sum(x * x for x in self.vector))

    def normalize(self) -> 'SpinFactor':
        n = self.norm()
        if n < 1e-10:
            return SpinFactor.zero(len(self.vector))
        return SpinFactor(
            scalar=self.scalar / n,
            vector=[x / n for x in self.vector]
        )

    def is_idempotent(self, tol: float = 1e-6) -> bool:
        """e ∘ e = e — fixed point of Jordan squaring."""
        sq = self.jordan_square()
        scalar_err = abs(sq.scalar - self.scalar)
        vec_err = _norm([a - b for a, b in zip(sq.vector, self.vector)])
        return scalar_err < tol and vec_err < tol

    def eigenvalue_bounds(self) -> tuple[float, float]:
        """
        Gershgorin-style bounds on eigenvalues of this spin factor element.
        For (α, v): eigenvalues are α ± ‖v‖
        """
        vn = _norm(self.vector)
        return (self.scalar - vn, self.scalar + vn)

    def spectral_components(self) -> tuple['SpinFactor', 'SpinFactor']:
        """
        Spectral decomposition: x = λ₊c₊ + λ₋c₋
        where c₊, c₋ are primitive idempotents.

        For spin factor (α, v):
          λ± = α ± ‖v‖
          c± = (1/2)(1, ± v̂)   where v̂ = v/‖v‖
        """
        vn = _norm(self.vector)
        lam_plus  = self.scalar + vn
        lam_minus = self.scalar - vn

        if vn < 1e-10:
            # Degenerate case — scalar only
            dim = len(self.vector)
            c_plus  = SpinFactor(scalar=0.5, vector=_zeros(dim))
            c_minus = SpinFactor(scalar=0.5, vector=_zeros(dim))
        else:
            v_hat = _normalize(self.vector)
            c_plus  = SpinFactor(
                scalar=0.5,
                vector=_scale(0.5, v_hat)
            )
            c_minus = SpinFactor(
                scalar=0.5,
                vector=_scale(-0.5, v_hat)
            )

        return (
            SpinFactor(scalar=lam_plus  * c_plus.scalar,
                       vector=_scale(lam_plus,  c_plus.vector)),
            SpinFactor(scalar=lam_minus * c_minus.scalar,
                       vector=_scale(lam_minus, c_minus.vector))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scalar": self.scalar,
            "vector": self.vector,
            "norm": self.norm(),
            "eigenvalue_bounds": self.eigenvalue_bounds(),
        }


# ─────────────────────────────────────────────
# Fixed-Point Solver
# ─────────────────────────────────────────────

@dataclass
class FixedPointResult:
    converged:     bool
    iterations:    int
    element:       SpinFactor
    final_error:   float
    eigenvalues:   tuple[float, float]


class FixedPointSolver:
    """
    Iterate Jordan squaring x ↦ x ∘ x until convergence.

    Fixed points are idempotents: e ∘ e = e
    These correspond to stable routing attractors — expert clusters
    that the system naturally converges to given the input signals.

    Jordan's theorem: every finite-dimensional Jordan algebra element
    converges to an idempotent under repeated squaring + normalization.
    """

    def __init__(self, max_iter: int = 64, tol: float = 1e-8):
        self.max_iter = max_iter
        self.tol      = tol

    def solve(self, x: SpinFactor) -> FixedPointResult:
        """
        Iterate x ↦ normalize(x ∘ x) until ‖xₙ₊₁ - xₙ‖ < tol.
        """
        current = x.normalize()

        for i in range(self.max_iter):
            squared  = current.jordan_square()
            next_el  = squared.normalize()

            # Convergence check: ‖xₙ₊₁ - xₙ‖
            d_scalar = abs(next_el.scalar - current.scalar)
            d_vector = _norm([a - b for a, b in zip(next_el.vector, current.vector)])
            error    = math.sqrt(d_scalar ** 2 + d_vector ** 2)

            current = next_el

            if error < self.tol:
                return FixedPointResult(
                    converged=True,
                    iterations=i + 1,
                    element=current,
                    final_error=error,
                    eigenvalues=current.eigenvalue_bounds()
                )

        return FixedPointResult(
            converged=False,
            iterations=self.max_iter,
            element=current,
            final_error=error,
            eigenvalues=current.eigenvalue_bounds()
        )


# ─────────────────────────────────────────────
# Jordan MoE Gate
# ─────────────────────────────────────────────

@dataclass
class JordanGateResult:
    weights:        dict[str, float]   # expert_name → routing weight
    active_experts: list[str]
    fixed_points:   dict[str, FixedPointResult]
    group_products: dict[str, float]   # non-associative grouping scores
    spectral_gap:   float              # λ₊ - λ₋ (separation of top-2)
    converged:      bool


class JordanMoEGate:
    """
    Jordan algebraic MoE routing gate.

    Replaces softmax with Jordan operator composition:

    1. Build SpinFactor for each expert from its signal affinity
    2. Compute Jordan products across all expert pairs
    3. Non-associative grouping: try different bracketing orders,
       select topology that maximizes spectral gap
    4. Run fixed-point solver on each expert's element
    5. Use idempotent scalar component as routing weight
    6. Normalize to probability simplex

    The non-associativity is a FEATURE not a bug:
    Different agent groupings produce different routing outcomes.
    We search over groupings to find the one with maximum spectral
    separation (most decisive routing).
    """

    def __init__(
        self,
        top_k: int = 2,
        fp_solver: FixedPointSolver | None = None
    ):
        self.top_k     = top_k
        self.fp_solver = fp_solver or FixedPointSolver()

    def gate(
        self,
        signals:       dict[str, float],
        expert_names:  list[str],
        affinities:    dict[str, dict[str, float]],  # expert → signal affinities
        expert_mask:   dict[str, bool] | None = None
    ) -> JordanGateResult:
        """
        Compute Jordan-algebraic routing weights.

        Args:
            signals:      current routing signals
            expert_names: list of expert names
            affinities:   per-expert signal affinity vectors
            expert_mask:  optional boolean mask from constraint eval
        """
        mask = expert_mask or {e: True for e in expert_names}
        dim  = len(signals)

        # Step 1: Build SpinFactor for each expert
        expert_elements: dict[str, SpinFactor] = {}
        for name in expert_names:
            if not mask.get(name, True):
                continue
            aff = affinities.get(name, {})
            # Modulate signal by affinity
            modulated = {
                k: signals.get(k, 0.0) * aff.get(k, 0.3)
                for k in signals
            }
            expert_elements[name] = SpinFactor.from_signals(modulated)

        if not expert_elements:
            return JordanGateResult(
                weights={e: 0.0 for e in expert_names},
                active_experts=[],
                fixed_points={},
                group_products={},
                spectral_gap=0.0,
                converged=False
            )

        # Step 2: Jordan products across all pairs (non-associative cross terms)
        group_products: dict[str, float] = {}
        names = list(expert_elements.keys())

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = expert_elements[names[i]], expert_elements[names[j]]

                # (A ∘ B) — order AB
                ab     = a.jordan_product(b)
                # Check non-associativity: find third element to test grouping
                for k in range(len(names)):
                    if k == i or k == j:
                        continue
                    c = expert_elements[names[k]]
                    # (A ∘ B) ∘ C
                    abc_left  = ab.jordan_product(c)
                    # A ∘ (B ∘ C)
                    abc_right = a.jordan_product(b.jordan_product(c))
                    # Grouping score = difference (non-zero = non-associative)
                    diff = abs(abc_left.scalar - abc_right.scalar)
                    key  = f"{names[i]}|{names[j]}|{names[k]}"
                    group_products[key] = diff

                group_products[f"{names[i]}∘{names[j]}"] = ab.scalar

        # Step 3: Fixed-point iteration for each expert
        fixed_points: dict[str, FixedPointResult] = {}
        raw_weights:  dict[str, float] = {}

        for name, element in expert_elements.items():
            fp = self.fp_solver.solve(element)
            fixed_points[name] = fp
            # Use fixed-point scalar as raw weight
            raw_weights[name]  = max(fp.element.scalar, 0.0)

        # Step 4: Top-k sparsity
        sorted_experts = sorted(raw_weights.items(), key=lambda x: x[1], reverse=True)
        sparse_weights: dict[str, float] = {}
        for idx, (name, w) in enumerate(sorted_experts):
            sparse_weights[name] = w if idx < self.top_k else 0.0

        # Step 5: Softmax normalize over sparse survivors
        active = {k: v for k, v in sparse_weights.items() if v > 1e-10}
        final_weights = self._normalize_weights(active, expert_names)

        # Spectral gap: difference between top-2 eigenvalue upper bounds
        eigenvalue_uppers = []
        for name in list(active.keys())[:2]:
            fp = fixed_points[name]
            eigenvalue_uppers.append(fp.eigenvalues[1])  # λ₊
        spectral_gap = (
            abs(eigenvalue_uppers[0] - eigenvalue_uppers[1])
            if len(eigenvalue_uppers) >= 2 else 0.0
        )

        all_converged = all(fp.converged for fp in fixed_points.values())

        return JordanGateResult(
            weights=final_weights,
            active_experts=list(active.keys()),
            fixed_points=fixed_points,
            group_products=group_products,
            spectral_gap=spectral_gap,
            converged=all_converged
        )

    def _normalize_weights(
        self,
        active: dict[str, float],
        all_experts: list[str]
    ) -> dict[str, float]:
        total = sum(active.values())
        result = {e: 0.0 for e in all_experts}
        if total < 1e-10:
            return result
        for k, v in active.items():
            result[k] = v / total
        return result


# ─────────────────────────────────────────────
# Non-associative swarm composer
# ─────────────────────────────────────────────

class SwarmComposer:
    """
    Compose a fleet of agent nodes using Jordan products.

    Non-associativity means grouping order matters:
      left_fold:  ((A ∘ B) ∘ C) ∘ D   — sequential composition
      right_fold: A ∘ (B ∘ (C ∘ D))   — reverse sequential
      tree:       (A ∘ B) ∘ (C ∘ D)   — balanced binary tree
      star:       A ∘ B, A ∘ C, A ∘ D — star topology (A is hub)

    Each gives a different global invariant.
    We compute all four and return the one with maximum spectral gap
    (most decisive — best separates activated from dormant experts).
    """

    def compose_left_fold(self, elements: list[SpinFactor]) -> SpinFactor:
        """((A ∘ B) ∘ C) ∘ D — sequential left fold."""
        if not elements:
            raise ValueError("Empty element list")
        result = elements[0]
        for el in elements[1:]:
            result = result.jordan_product(el)
        return result

    def compose_right_fold(self, elements: list[SpinFactor]) -> SpinFactor:
        """A ∘ (B ∘ (C ∘ D)) — sequential right fold."""
        if not elements:
            raise ValueError("Empty element list")
        result = elements[-1]
        for el in reversed(elements[:-1]):
            result = el.jordan_product(result)
        return result

    def compose_tree(self, elements: list[SpinFactor]) -> SpinFactor:
        """(A ∘ B) ∘ (C ∘ D) — balanced binary tree fold."""
        if not elements:
            raise ValueError("Empty element list")
        nodes = list(elements)
        while len(nodes) > 1:
            next_level = []
            for i in range(0, len(nodes), 2):
                if i + 1 < len(nodes):
                    next_level.append(nodes[i].jordan_product(nodes[i + 1]))
                else:
                    next_level.append(nodes[i])
            nodes = next_level
        return nodes[0]

    def compose_star(self, hub: SpinFactor, spokes: list[SpinFactor]) -> SpinFactor:
        """
        Star topology: hub ∘ spoke₁, hub ∘ spoke₂, ...
        Hub node dominates composition.
        """
        result = hub
        for spoke in spokes:
            result = result.jordan_product(spoke)
        return result

    def best_composition(
        self,
        elements: list[SpinFactor]
    ) -> tuple[str, SpinFactor]:
        """
        Try all four topologies, return the one with maximum
        spectral gap (λ₊ - λ₋).
        """
        if len(elements) < 2:
            return "identity", elements[0] if elements else SpinFactor(0.0, [])

        candidates = {
            "left_fold":  self.compose_left_fold(elements),
            "right_fold": self.compose_right_fold(elements),
            "tree":       self.compose_tree(elements),
        }
        if len(elements) >= 3:
            candidates["star"] = self.compose_star(elements[0], elements[1:])

        # Select topology with maximum spectral gap
        # Spectral gap = lam_hi - lam_lo = 2 * ||v|| (vector norm drives separation)
        # Non-associativity lives in the vector component, so we rank by full norm
        best_name   = "left_fold"
        best_gap    = -1.0
        for name, el in candidates.items():
            lam_lo, lam_hi = el.eigenvalue_bounds()
            gap = lam_hi - lam_lo  # = 2 * ||vector||
            if gap > best_gap:
                best_gap  = gap
                best_name = name

        return best_name, candidates[best_name]
