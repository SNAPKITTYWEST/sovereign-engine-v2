"""
DSL Validator for HyperKittyConstraintDSL.

Validates:
1. BooleanKernel (NAND truthtable, derived gates)
2. Entropy constraint (H ≤ 0.20 nats)
3. Trust axiom (active ⇒ trusted)
4. GlyphType constraints (injective mapping)
5. DAG validation (acyclic, reachable)

Pure Python stdlib: hashlib (Blake2b), math (log), collections, enum, dataclasses.
"""

import hashlib
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict, deque


class PROOF_STATUS(Enum):
    """Proof status for constraint validation results."""
    PROOF_TRUE = "PROOF_TRUE"
    PROOF_FALSE = "PROOF_FALSE"
    PROOF_INCOMPLETE = "PROOF_INCOMPLETE"


@dataclass
class ValidationResult:
    """Result of a single constraint validation."""
    passed: bool
    constraint: str
    detail: str
    proof_status: PROOF_STATUS = PROOF_STATUS.PROOF_INCOMPLETE


class DSLValidator:
    """Validator for HyperKittyConstraintDSL constraints."""

    def __init__(self):
        """Initialize validator with empty results list."""
        self.results: List[ValidationResult] = []

    # ========== BOOLEAN KERNEL VALIDATION ==========

    @staticmethod
    def nand(a: int, b: int) -> int:
        """
        NAND truthtable: NOT(a AND b).

        NAND(0,0) = 1
        NAND(0,1) = 1
        NAND(1,0) = 1
        NAND(1,1) = 0
        """
        return int(not (a and b))

    @staticmethod
    def not_gate(a: int) -> int:
        """
        NOT derived from NAND: NOT(A) = NAND(A,A).
        """
        return DSLValidator.nand(a, a)

    @staticmethod
    def and_gate(a: int, b: int) -> int:
        """
        AND derived: AND(A,B) = NOT(NAND(A,B)).
        """
        return DSLValidator.not_gate(DSLValidator.nand(a, b))

    @staticmethod
    def or_gate(a: int, b: int) -> int:
        """
        OR derived: OR(A,B) = NAND(NOT(A),NOT(B)).
        """
        return DSLValidator.nand(
            DSLValidator.not_gate(a),
            DSLValidator.not_gate(b)
        )

    @staticmethod
    def implies_gate(a: int, b: int) -> int:
        """
        IMPLIES derived: IMPLIES(A,B) = NAND(A,NOT(B)).
        False only when A=1 and B=0.
        """
        return DSLValidator.nand(a, DSLValidator.not_gate(b))

    @staticmethod
    def equal_gate(a: int, b: int) -> int:
        """
        EQUAL derived: EQUAL(A,B) = AND(IMPLIES(A,B),IMPLIES(B,A)).
        True when A and B have same truth value.
        """
        return DSLValidator.and_gate(
            DSLValidator.implies_gate(a, b),
            DSLValidator.implies_gate(b, a)
        )

    def validate_nand_truthtable(self) -> ValidationResult:
        """
        Validate NAND truth table exhaustively.

        Expected:
        - NAND(0,0) = 1
        - NAND(0,1) = 1
        - NAND(1,0) = 1
        - NAND(1,1) = 0
        """
        expected = {
            (0, 0): 1,
            (0, 1): 1,
            (1, 0): 1,
            (1, 1): 0,
        }

        for (a, b), expected_result in expected.items():
            actual = self.nand(a, b)
            if actual != expected_result:
                return ValidationResult(
                    passed=False,
                    constraint="NAND_TRUTHTABLE",
                    detail=f"NAND({a},{b}) = {actual}, expected {expected_result}",
                    proof_status=PROOF_STATUS.PROOF_FALSE
                )

        return ValidationResult(
            passed=True,
            constraint="NAND_TRUTHTABLE",
            detail="NAND truth table: 4/4 entries correct",
            proof_status=PROOF_STATUS.PROOF_TRUE
        )

    def validate_not_derivation(self) -> ValidationResult:
        """
        Validate NOT derived from NAND: NOT(A) = NAND(A,A).
        """
        for a in [0, 1]:
            derived = self.not_gate(a)
            expected = int(not a)
            if derived != expected:
                return ValidationResult(
                    passed=False,
                    constraint="NOT_DERIVATION",
                    detail=f"NOT({a}) = {derived}, expected {expected}",
                    proof_status=PROOF_STATUS.PROOF_FALSE
                )

        return ValidationResult(
            passed=True,
            constraint="NOT_DERIVATION",
            detail="NOT gate: 2/2 truth values verified",
            proof_status=PROOF_STATUS.PROOF_TRUE
        )

    def validate_and_derivation(self) -> ValidationResult:
        """
        Validate AND derived from NAND: AND(A,B) = NOT(NAND(A,B)).
        """
        for a in [0, 1]:
            for b in [0, 1]:
                derived = self.and_gate(a, b)
                expected = int(a and b)
                if derived != expected:
                    return ValidationResult(
                        passed=False,
                        constraint="AND_DERIVATION",
                        detail=f"AND({a},{b}) = {derived}, expected {expected}",
                        proof_status=PROOF_STATUS.PROOF_FALSE
                    )

        return ValidationResult(
            passed=True,
            constraint="AND_DERIVATION",
            detail="AND gate: 4/4 truth values verified",
            proof_status=PROOF_STATUS.PROOF_TRUE
        )

    def validate_or_derivation(self) -> ValidationResult:
        """
        Validate OR derived from NAND: OR(A,B) = NAND(NOT(A),NOT(B)).
        """
        for a in [0, 1]:
            for b in [0, 1]:
                derived = self.or_gate(a, b)
                expected = int(a or b)
                if derived != expected:
                    return ValidationResult(
                        passed=False,
                        constraint="OR_DERIVATION",
                        detail=f"OR({a},{b}) = {derived}, expected {expected}",
                        proof_status=PROOF_STATUS.PROOF_FALSE
                    )

        return ValidationResult(
            passed=True,
            constraint="OR_DERIVATION",
            detail="OR gate: 4/4 truth values verified",
            proof_status=PROOF_STATUS.PROOF_TRUE
        )

    def validate_implies_derivation(self) -> ValidationResult:
        """
        Validate IMPLIES derived from NAND: IMPLIES(A,B) = NAND(A,NOT(B)).
        False only when A=1 and B=0.
        """
        for a in [0, 1]:
            for b in [0, 1]:
                derived = self.implies_gate(a, b)
                expected = int(not a or b)
                if derived != expected:
                    return ValidationResult(
                        passed=False,
                        constraint="IMPLIES_DERIVATION",
                        detail=f"IMPLIES({a},{b}) = {derived}, expected {expected}",
                        proof_status=PROOF_STATUS.PROOF_FALSE
                    )

        return ValidationResult(
            passed=True,
            constraint="IMPLIES_DERIVATION",
            detail="IMPLIES gate: 4/4 truth values verified",
            proof_status=PROOF_STATUS.PROOF_TRUE
        )

    def validate_equal_derivation(self) -> ValidationResult:
        """
        Validate EQUAL derived from NAND: EQUAL(A,B) = AND(IMPLIES(A,B),IMPLIES(B,A)).
        True when A and B have same truth value.
        """
        for a in [0, 1]:
            for b in [0, 1]:
                derived = self.equal_gate(a, b)
                expected = int(a == b)
                if derived != expected:
                    return ValidationResult(
                        passed=False,
                        constraint="EQUAL_DERIVATION",
                        detail=f"EQUAL({a},{b}) = {derived}, expected {expected}",
                        proof_status=PROOF_STATUS.PROOF_FALSE
                    )

        return ValidationResult(
            passed=True,
            constraint="EQUAL_DERIVATION",
            detail="EQUAL gate: 4/4 truth values verified",
            proof_status=PROOF_STATUS.PROOF_TRUE
        )

    def validate_boolean_kernel(self) -> bool:
        """
        Validate entire boolean kernel: all 6 gate derivations.

        Returns True if all gates pass their truth tables.
        """
        checks = [
            self.validate_nand_truthtable(),
            self.validate_not_derivation(),
            self.validate_and_derivation(),
            self.validate_or_derivation(),
            self.validate_implies_derivation(),
            self.validate_equal_derivation(),
        ]

        all_passed = all(check.passed for check in checks)
        self.results.extend(checks)

        return all_passed

    # ========== ENTROPY CONSTRAINT VALIDATION ==========

    def validate_entropy(self, distribution: Dict[str, float], max_entropy: float = 0.20) -> bool:
        """
        Validate entropy constraint: H ≤ max_entropy nats.

        Shannon entropy: H = -Σ pᵢ log(pᵢ)

        Args:
            distribution: dict mapping route/state names to probabilities
            max_entropy: maximum allowed entropy (default 0.20 nats)

        Returns:
            True if entropy satisfies constraint.
        """
        # Check for empty distribution
        if not distribution:
            result = ValidationResult(
                passed=False,
                constraint="ENTROPY",
                detail="Distribution is empty",
                proof_status=PROOF_STATUS.PROOF_FALSE
            )
            self.results.append(result)
            return False

        # Normalize distribution
        total = sum(distribution.values())
        if total <= 0:
            result = ValidationResult(
                passed=False,
                constraint="ENTROPY",
                detail="Distribution total is <= 0",
                proof_status=PROOF_STATUS.PROOF_FALSE
            )
            self.results.append(result)
            return False

        normalized = {k: v / total for k, v in distribution.items()}

        # Calculate Shannon entropy: H = -Σ pᵢ log(pᵢ)
        entropy = 0.0
        for prob in normalized.values():
            if prob > 0:
                entropy -= prob * math.log(prob)

        passed = entropy <= max_entropy
        result = ValidationResult(
            passed=passed,
            constraint="ENTROPY",
            detail=f"H = {entropy:.6f} nats (limit: {max_entropy})",
            proof_status=PROOF_STATUS.PROOF_TRUE if passed else PROOF_STATUS.PROOF_FALSE
        )
        self.results.append(result)

        return passed

    # ========== TRUST AXIOM VALIDATION ==========

    def validate_trust(self, active_set: Set[str], trusted_set: Set[str]) -> bool:
        """
        Validate trust axiom: active(I) ⇒ trusted(I).

        Constraint: every agent instance in active_set must be in trusted_set.

        Args:
            active_set: set of currently active agent IDs
            trusted_set: set of trusted agent IDs

        Returns:
            True if all active agents are trusted.
        """
        untrusted_active = active_set - trusted_set
        passed = len(untrusted_active) == 0

        detail = "All active agents are trusted"
        if untrusted_active:
            detail = f"Untrusted active agents: {sorted(untrusted_active)}"

        result = ValidationResult(
            passed=passed,
            constraint="TRUST_AXIOM",
            detail=detail,
            proof_status=PROOF_STATUS.PROOF_TRUE if passed else PROOF_STATUS.PROOF_FALSE
        )
        self.results.append(result)

        return passed

    # ========== GLYPH TYPE VALIDATION ==========

    def validate_glyph_types(self, mapping: Dict[str, str]) -> bool:
        """
        Validate GlyphType constraint.

        Constraints:
        1. Each glyph maps to exactly one semantic type (by construction)
        2. No two glyphs map to same type (injective)
        3. All types in universe covered (surjective within declared types)

        Args:
            mapping: dict from glyph name to semantic type name

        Returns:
            True if mapping is injective.
        """
        if not mapping:
            result = ValidationResult(
                passed=False,
                constraint="GLYPH_TYPES",
                detail="Mapping is empty",
                proof_status=PROOF_STATUS.PROOF_FALSE
            )
            self.results.append(result)
            return False

        # Check injectivity: no two glyphs map to same type
        type_to_glyphs: Dict[str, List[str]] = defaultdict(list)
        for glyph, glyph_type in mapping.items():
            type_to_glyphs[glyph_type].append(glyph)

        # Find violations of injectivity
        duplicates = {t: glyphs for t, glyphs in type_to_glyphs.items() if len(glyphs) > 1}
        if duplicates:
            detail = f"Non-injective: {dict(duplicates)}"
            result = ValidationResult(
                passed=False,
                constraint="GLYPH_TYPES",
                detail=detail,
                proof_status=PROOF_STATUS.PROOF_FALSE
            )
            self.results.append(result)
            return False

        result = ValidationResult(
            passed=True,
            constraint="GLYPH_TYPES",
            detail=f"Injective mapping verified: {len(mapping)} glyphs → {len(type_to_glyphs)} types",
            proof_status=PROOF_STATUS.PROOF_TRUE
        )
        self.results.append(result)

        return True

    # ========== DAG VALIDATION ==========

    def validate_dag(self, adjacency: Dict[str, List[str]]) -> bool:
        """
        Validate DAG (directed acyclic graph) constraint.

        Constraints:
        1. Graph must be acyclic (no cycles)
        2. Topological sort must succeed
        3. No orphan nodes (all nodes reachable from at least one root)

        Args:
            adjacency: dict mapping node names to list of neighbor nodes

        Returns:
            True if graph is a valid DAG with no orphans.
        """
        if not adjacency:
            result = ValidationResult(
                passed=True,
                constraint="DAG_VALIDATION",
                detail="Empty graph is acyclic",
                proof_status=PROOF_STATUS.PROOF_TRUE
            )
            self.results.append(result)
            return True

        # Get all nodes in graph
        all_nodes = set(adjacency.keys())
        for neighbors in adjacency.values():
            all_nodes.update(neighbors)

        # Check for cycles using DFS with recursion stack
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def has_cycle(node: str) -> bool:
            """DFS cycle detection using recursion stack."""
            visited.add(node)
            rec_stack.add(node)

            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        # Check all nodes for cycles
        for node in all_nodes:
            if node not in visited:
                if has_cycle(node):
                    result = ValidationResult(
                        passed=False,
                        constraint="DAG_VALIDATION",
                        detail="Cycle detected in routing graph",
                        proof_status=PROOF_STATUS.PROOF_FALSE
                    )
                    self.results.append(result)
                    return False

        # Calculate in-degree for each node
        in_degree = defaultdict(int)
        for node in all_nodes:
            if node not in in_degree:
                in_degree[node] = 0

        for neighbors in adjacency.values():
            for neighbor in neighbors:
                in_degree[neighbor] += 1

        # Find root nodes (in-degree = 0)
        roots = {node for node in all_nodes if in_degree[node] == 0}

        if not roots:
            result = ValidationResult(
                passed=False,
                constraint="DAG_VALIDATION",
                detail="No root nodes: all nodes have incoming edges",
                proof_status=PROOF_STATUS.PROOF_FALSE
            )
            self.results.append(result)
            return False

        # BFS from all roots to find reachable nodes
        reachable = set()
        queue = deque(roots)
        reachable.update(roots)

        while queue:
            node = queue.popleft()
            for neighbor in adjacency.get(node, []):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

        # Check for orphan nodes (unreachable from roots)
        orphans = all_nodes - reachable
        if orphans:
            result = ValidationResult(
                passed=False,
                constraint="DAG_VALIDATION",
                detail=f"Orphan nodes (unreachable): {sorted(orphans)}",
                proof_status=PROOF_STATUS.PROOF_FALSE
            )
            self.results.append(result)
            return False

        result = ValidationResult(
            passed=True,
            constraint="DAG_VALIDATION",
            detail=f"DAG valid: {len(all_nodes)} nodes, {len(roots)} roots, acyclic, fully reachable",
            proof_status=PROOF_STATUS.PROOF_TRUE
        )
        self.results.append(result)

        return True

    # ========== COMPOSITE VALIDATION ==========

    def validate_all(self) -> Tuple[bool, List[ValidationResult]]:
        """
        Run all validations and return combined result.

        Currently runs boolean kernel validation.
        Other validations (entropy, trust, glyph, dag) must be called explicitly.

        Returns:
            (all_passed, results_list)
        """
        self.results = []
        boolean_valid = self.validate_boolean_kernel()
        return boolean_valid, self.results


def generate_proof_hash(results: List[ValidationResult]) -> str:
    """
    Generate Blake2b hash over all constraint validation results.

    Encodes each result as canonical string:
        constraint:passed:proof_status:detail

    Sorts results for deterministic ordering, then computes Blake2b-256 hash.

    Args:
        results: list of ValidationResult objects

    Returns:
        Hex digest of Blake2b-256 hash (64 characters).
    """
    result_strings = []

    for result in results:
        # Canonical encoding: constraint:passed:proof_status:detail
        encoded = f"{result.constraint}:{result.passed}:{result.proof_status.value}:{result.detail}"
        result_strings.append(encoded)

    # Sort for deterministic ordering
    result_strings.sort()

    # Concatenate with newlines
    combined = "\n".join(result_strings)

    # Compute Blake2b-256 hash
    hasher = hashlib.blake2b(digest_size=32)
    hasher.update(combined.encode('utf-8'))

    return hasher.hexdigest()


# ========== EXAMPLE USAGE AND TESTS ==========

if __name__ == "__main__":
    print("=" * 70)
    print("DSL Validator - HyperKittyConstraintDSL")
    print("=" * 70)

    validator = DSLValidator()

    # Test 1: Boolean Kernel
    print("\n[1] Boolean Kernel Validation")
    print("-" * 70)
    bool_valid, bool_results = validator.validate_all()
    for result in bool_results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"  {status:8} {result.constraint:25} {result.detail}")
    print(f"\n  Overall: {'✓ VALID' if bool_valid else '✗ INVALID'}")

    # Test 2: Entropy
    print("\n[2] Entropy Constraint Validation")
    print("-" * 70)
    validator.results = []
    dist = {"route_a": 0.3, "route_b": 0.5, "route_c": 0.2}
    entropy_valid = validator.validate_entropy(dist, max_entropy=0.20)
    for result in validator.results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"  {status:8} {result.constraint:25} {result.detail}")

    # Test 3: Trust Axiom
    print("\n[3] Trust Axiom Validation")
    print("-" * 70)
    validator.results = []
    active = {"agent_1", "agent_2", "agent_3"}
    trusted = {"agent_1", "agent_2", "agent_3", "agent_4"}
    trust_valid = validator.validate_trust(active, trusted)
    for result in validator.results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"  {status:8} {result.constraint:25} {result.detail}")

    # Test 4: Glyph Types
    print("\n[4] Glyph Type Validation")
    print("-" * 70)
    validator.results = []
    glyph_map = {"aleph": "number", "beth": "letter", "gimel": "symbol"}
    glyph_valid = validator.validate_glyph_types(glyph_map)
    for result in validator.results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"  {status:8} {result.constraint:25} {result.detail}")

    # Test 5: DAG
    print("\n[5] DAG Validation")
    print("-" * 70)
    validator.results = []
    adjacency = {
        "start": ["middle"],
        "middle": ["end"],
        "end": []
    }
    dag_valid = validator.validate_dag(adjacency)
    for result in validator.results:
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"  {status:8} {result.constraint:25} {result.detail}")

    # Generate proof hash
    print("\n[6] Proof Hash Generation")
    print("-" * 70)
    all_results = bool_results + validator.results
    proof_hash = generate_proof_hash(all_results)
    print(f"  Blake2b-256: {proof_hash}")
    print(f"  Total constraints validated: {len(all_results)}")
