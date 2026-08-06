"""
ERE -- Expected Reasoning Error Protocol
Five-gate verification system for agent output.

Every agent output is ASSUMED WRONG until it passes all five gates.
The error is expected. The gate is the proof.

Gates:
  P1 -- No Secrets   (hardcoded credentials)
  P2 -- No Eval      (code injection)
  P3 -- Loop Safety  (infinite loops without break)
  P4 -- No Telemetry (analytics beacons)
  P5 -- Audit Hash   (SHA-256 seal, only if P1-P4 pass)

Tournament result: METATRON, ENKI, TITAN all passed.
WORM seal: 512227a50babc21070fc3d4e...

npm package: @snapkitty/ere-verify (MIT)
"""

from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class EREResult:
    passed: bool
    gates: dict[str, bool]
    seal: str | None        # SHA-256(agent:intent:output) if all pass
    violations: list[str]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "gates": self.gates,
            "seal": self.seal,
            "violations": self.violations,
        }


class EREGate:
    """
    Five-gate verification system.

    Usage:
        gate = EREGate()
        result = gate.check(agent_id="react_agent", intent="write code", output=code)
        if not result.passed:
            # do not propagate
            log_violations(result.violations)
        else:
            # result.seal is the P5 cryptographic commitment
            propagate(output, seal=result.seal)
    """

    # P1: Hardcoded secrets
    P1_PATTERNS: list[re.Pattern] = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),
        re.compile(r'api[_-]?key\s*[=:]\s*[\'"][^\'"]{8,}', re.IGNORECASE),
        re.compile(r'password\s*[=:]\s*[\'"][^\'"]{4,}', re.IGNORECASE),
        re.compile(r'secret\s*[=:]\s*[\'"][^\'"]{8,}', re.IGNORECASE),
        re.compile(r'token\s*[=:]\s*[\'"][^\'"]{20,}', re.IGNORECASE),
        re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    ]

    # P2: Code injection
    P2_PATTERNS: list[re.Pattern] = [
        re.compile(r"eval\s*\("),
        re.compile(r"exec\s*\("),
        re.compile(r"__import__\s*\("),
        re.compile(r"compile\s*\(.*exec", re.DOTALL),
        re.compile(r"subprocess\.(Popen|call|run|check_output)\s*\("),
        re.compile(r"os\.system\s*\("),
    ]

    # P3: Infinite loop without exit
    P3_WHILE_PATTERNS: list[re.Pattern] = [
        re.compile(r"while\s+[Tt]rue\s*:"),
        re.compile(r"while\s+1\s*:"),
        re.compile(r"while\s+True\s*:"),
    ]

    # P4: Telemetry / analytics beacons
    P4_PATTERNS: list[re.Pattern] = [
        re.compile(r"analytics\.track", re.IGNORECASE),
        re.compile(r"mixpanel\.(track|identify)", re.IGNORECASE),
        re.compile(r"segment\.track", re.IGNORECASE),
        re.compile(r"telemetry\.(send|emit|record)", re.IGNORECASE),
        re.compile(r"sentry\.(capture|add_breadcrumb)", re.IGNORECASE),
        re.compile(r"amplitude\.track", re.IGNORECASE),
    ]

    def check(
        self,
        agent_id: str,
        intent: str,
        output: str,
    ) -> EREResult:
        """
        Run all five gates against output.

        Args:
            agent_id: identifier of the agent that produced output
            intent:   the task or goal the agent was given
            output:   the agent's text output (code, prose, JSON, etc.)

        Returns:
            EREResult with gate verdicts, violations, and P5 seal
        """
        gates: dict[str, bool] = {}
        violations: list[str] = []

        # P1: No secrets
        p1_violations = [
            p.pattern for p in self.P1_PATTERNS
            if p.search(output)
        ]
        gates["P1"] = len(p1_violations) == 0
        if not gates["P1"]:
            violations.append(f"P1_NO_SECRETS: detected credential pattern")

        # P2: No eval / code injection
        p2_violations = [
            p.pattern for p in self.P2_PATTERNS
            if p.search(output)
        ]
        gates["P2"] = len(p2_violations) == 0
        if not gates["P2"]:
            violations.append(f"P2_NO_EVAL: code injection pattern detected")

        # P3: Loop safety
        has_infinite_while = any(p.search(output) for p in self.P3_WHILE_PATTERNS)
        has_exit = bool(re.search(r"break|return|sys\.exit", output))
        gates["P3"] = not has_infinite_while or has_exit
        if not gates["P3"]:
            violations.append("P3_LOOP_SAFETY: while True without break/return")

        # P4: No telemetry
        p4_violations = [
            p.pattern for p in self.P4_PATTERNS
            if p.search(output)
        ]
        gates["P4"] = len(p4_violations) == 0
        if not gates["P4"]:
            violations.append("P4_NO_TELEMETRY: analytics beacon detected")

        # P5: Audit hash (only if P1-P4 all pass)
        all_prior_pass = gates["P1"] and gates["P2"] and gates["P3"] and gates["P4"]
        seal: str | None = None

        if all_prior_pass:
            payload = f"{agent_id}:{intent}:{output}"
            seal = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            gates["P5"] = True
        else:
            gates["P5"] = False
            violations.append("P5_AUDIT_HASH: not computed -- prior gates failed")

        return EREResult(
            passed=all_prior_pass,
            gates=gates,
            seal=seal,
            violations=violations,
        )

    def check_code_only(self, agent_id: str, intent: str, code: str) -> EREResult:
        """Convenience wrapper -- same as check() but labels the intent as code."""
        return self.check(agent_id, f"code:{intent}", code)


# ── Module-level singleton for convenience ─────────────────────────────────────

_default_gate = EREGate()


def ere_check(agent_id: str, intent: str, output: str) -> EREResult:
    """Module-level convenience function."""
    return _default_gate.check(agent_id, intent, output)
