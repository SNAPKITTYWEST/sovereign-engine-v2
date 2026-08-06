"""
Stage 6: ConstraintEval

Evaluates constraint rules against the current parse + signals.
Filters invalid expert activation paths before sparse gating.

Constraints are first-class: they come from:
  1. Static rules (always apply)
  2. AST-derived constraints (from CONSTRAINT tokens)
  3. Jordan stability rules (from JordanResult)
  4. User-defined rules (injected at runtime)

Output: a boolean mask over experts — True = allowed, False = blocked.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any

from .parser import ParseResult
from .symbolic import JordanResult


@dataclass
class Constraint:
    name: str
    description: str
    check: Callable[[dict[str, Any]], bool]  # returns True = PASS (expert allowed)
    priority: int = 0  # higher priority evaluated first


@dataclass
class ConstraintResult:
    expert: str
    allowed: bool
    violated_constraints: list[str]
    passed_constraints: list[str]


@dataclass
class ConstraintEvalResult:
    expert_mask: dict[str, bool]          # expert_name -> allowed
    per_expert: list[ConstraintResult]
    blocked_count: int
    active_count: int


class ConstraintEval:
    """
    Stage 6: Evaluate constraints to produce expert activation mask.
    """

    def __init__(self):
        self._constraints: list[Constraint] = []
        self._register_static_constraints()

    def add_constraint(self, constraint: Constraint) -> None:
        self._constraints.append(constraint)
        self._constraints.sort(key=lambda c: -c.priority)

    def evaluate(
        self,
        expert_names: list[str],
        parse: ParseResult,
        jordan: JordanResult,
        routing_weights: dict[str, float]
    ) -> ConstraintEvalResult:

        ctx: dict[str, Any] = {
            "intent":            parse.intent,
            "signals":           parse.signals,
            "confidence":        parse.confidence,
            "tokens":            parse.tokens,
            "jordan":            jordan,
            "routing_weights":   routing_weights,
            "stability_score":   jordan.routing_features.get("stability_score", 1.0),
            "spectral_radius":   jordan.routing_features.get("spectral_radius", 0.0),
        }

        expert_mask: dict[str, bool] = {}
        per_expert: list[ConstraintResult] = []

        for expert in expert_names:
            ctx["expert"] = expert
            ctx["expert_weight"] = routing_weights.get(expert, 0.0)

            violated: list[str] = []
            passed: list[str] = []

            for constraint in self._constraints:
                try:
                    ok = constraint.check(ctx)
                except Exception:
                    ok = True  # failing constraint = don't block

                if ok:
                    passed.append(constraint.name)
                else:
                    violated.append(constraint.name)

            allowed = len(violated) == 0
            expert_mask[expert] = allowed
            per_expert.append(ConstraintResult(
                expert=expert,
                allowed=allowed,
                violated_constraints=violated,
                passed_constraints=passed
            ))

        blocked = sum(1 for v in expert_mask.values() if not v)
        active = len(expert_names) - blocked

        return ConstraintEvalResult(
            expert_mask=expert_mask,
            per_expert=per_expert,
            blocked_count=blocked,
            active_count=active
        )

    def _register_static_constraints(self) -> None:
        """Register built-in constraints."""

        # Block experts with zero routing weight
        self.add_constraint(Constraint(
            name="non_zero_weight",
            description="Expert must have non-zero routing weight",
            check=lambda ctx: ctx["expert_weight"] > 1e-6,
            priority=100
        ))

        # Block all experts only if graph is catastrophically unstable
        # Gershgorin bounds are pessimistic on sparse graphs so threshold is generous
        self.add_constraint(Constraint(
            name="jordan_stability",
            description="Block expert if spectral radius > 10 (catastrophically unstable graph)",
            check=lambda ctx: ctx["spectral_radius"] <= 10.0,
            priority=90
        ))

        # Code experts require code signal
        self.add_constraint(Constraint(
            name="code_expert_requires_code_signal",
            description="Code-specialist experts require code signal > 0",
            check=lambda ctx: not (
                "code" in ctx["expert"].lower() and
                ctx["signals"].get("code_signal", 0) < 0.01 and
                ctx["intent"] not in ("code", "mixed")
            ),
            priority=80
        ))

        # Query experts require query signal
        self.add_constraint(Constraint(
            name="query_expert_requires_query_signal",
            description="Query-specialist experts require query signal > 0",
            check=lambda ctx: not (
                "query" in ctx["expert"].lower() and
                ctx["signals"].get("query_signal", 0) < 0.01 and
                ctx["intent"] not in ("query", "mixed")
            ),
            priority=80
        ))

        # Minimum confidence threshold
        self.add_constraint(Constraint(
            name="minimum_confidence",
            description="Overall parse confidence must be > 0.001",
            check=lambda ctx: ctx["confidence"] > 0.001,
            priority=70
        ))
