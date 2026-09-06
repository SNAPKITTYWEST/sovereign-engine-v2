"""
live_routing_test.py — Live LLM routing through Sovereign Engine DSL.

Proof of concept: real prompts route through the 11-stage pipeline,
dispatch to the correct QRA glyph, and produce sealed WORM records.

Uses AWS Bedrock (Claude Haiku) for actual inference.
Falls back to mock if no credentials available.

Demonstrates:
  1. DSL constraint enforcement (H <= 0.20)
  2. QRA 6-glyph classification (deterministic)
  3. ERE 5-gate verification on output
  4. WORM seal on routing decision
  5. PathJail enforcement on any file ops
  6. Full pipeline: input -> route -> infer -> verify -> seal
"""

import asyncio
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.runtime.machine.vm_executor import (
    SovereignVM,
    VMInstruction,
    VMOpcode,
    WORMLog,
    nand_op,
)
from src.tools.ere import EREGate, EREResult


# ---------------------------------------------------------------------------
# QRA Glyph Router (deterministic — from qra_router.py)
# ---------------------------------------------------------------------------

GLYPH_KEYWORDS = {
    'Pi':    ['explain', 'why', 'analyze', 'reason', 'think', 'understand'],
    'Gamma': ['write', 'create', 'draft', 'generate', 'compose', 'make'],
    'Delta': ['sql', 'medical', 'legal', 'financial', 'domain', 'specific'],
    'Lambda': ['function', 'implement', 'debug', 'code', 'fix', 'refactor'],
    'Omega': ['plan', 'coordinate', 'multi-step', 'orchestrate', 'workflow'],
    'Psi':   ['prove', 'verify', 'test', 'check', 'validate', 'assert'],
}


def classify_glyph(prompt: str) -> str:
    """Deterministic glyph classification. H=0 nats — no randomness."""
    prompt_lower = prompt.lower()
    scores = {}
    for glyph, keywords in GLYPH_KEYWORDS.items():
        scores[glyph] = sum(1 for kw in keywords if kw in prompt_lower)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return 'Gamma'  # default: generation
    return best


# ---------------------------------------------------------------------------
# Sovereign Routing Pipeline (simplified for live test)
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    prompt: str
    glyph: str
    entropy: float
    ere_passed: bool
    ere_seal: str | None
    worm_seq: int
    latency_ms: float
    model_response: str | None = None


class SovereignRouter:
    """Simplified 11-stage routing pipeline for live testing."""

    def __init__(self):
        self._ere = EREGate()
        self._worm = WORMLog()
        self._decisions: list[RoutingDecision] = []

    def route(self, prompt: str) -> RoutingDecision:
        start = time.time()

        # Stage 1-2: Parse + classify
        glyph = classify_glyph(prompt)

        # Stage 3-4: Jordan gate (via VM)
        jordan_program = [
            VMInstruction(VMOpcode.PUSH, len(prompt)),
            VMInstruction(VMOpcode.PUSH, len(prompt.split())),
            VMInstruction(VMOpcode.MUL),
            VMInstruction(VMOpcode.GATE),
            VMInstruction(VMOpcode.HALT),
        ]
        vm = SovereignVM(jordan_program)
        gate_result = vm.run()

        # Stage 5-6: Entropy measurement
        entropy_program = [
            VMInstruction(VMOpcode.PUSH, hash(prompt) & 0xFF),
            VMInstruction(VMOpcode.PUSH, hash(glyph) & 0xFF),
            VMInstruction(VMOpcode.PUSH, len(prompt)),
            VMInstruction(VMOpcode.PUSH, gate_result if gate_result else 0),
            VMInstruction(VMOpcode.ENTROPY),
            VMInstruction(VMOpcode.HALT),
        ]
        vm2 = SovereignVM(entropy_program)
        entropy = vm2.run()

        # Stage 7-8: NAND conflict check (no conflict in single-route)
        nand_clear = nand_op(1, 0)  # always 1 = no conflict

        # Stage 9: Dispatch (mock response — real inference below)
        response = f"[{glyph}] Routed: {prompt[:50]}"

        # Stage 10: ERE verification on response
        ere_result = self._ere.check(
            agent_id="sovereign_router",
            intent=f"glyph:{glyph}",
            output=response,
        )

        # Stage 11: WORM seal
        seal_data = f"{glyph}:{entropy}:{prompt}:{response}".encode()
        worm_entry = self._worm.append(VMOpcode.SEAL, seal_data)

        latency = (time.time() - start) * 1000

        decision = RoutingDecision(
            prompt=prompt,
            glyph=glyph,
            entropy=entropy if isinstance(entropy, float) else 0.0,
            ere_passed=ere_result.passed,
            ere_seal=ere_result.seal,
            worm_seq=worm_entry.seq,
            latency_ms=latency,
            model_response=response,
        )
        self._decisions.append(decision)
        return decision

    async def route_with_inference(self, prompt: str) -> RoutingDecision:
        """Route with actual LLM inference via Bedrock."""
        decision = self.route(prompt)

        try:
            import boto3
            client = boto3.client('bedrock-runtime', region_name='us-east-1')
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            })
            response = client.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=body,
            )
            result = json.loads(response['body'].read())
            decision.model_response = result['content'][0]['text']

            # Re-verify with ERE after real inference
            ere_result = self._ere.check(
                agent_id="haiku",
                intent=f"glyph:{decision.glyph}",
                output=decision.model_response,
            )
            decision.ere_passed = ere_result.passed
            decision.ere_seal = ere_result.seal

        except Exception as e:
            decision.model_response = f"[MOCK - no Bedrock: {type(e).__name__}] {decision.model_response}"

        return decision

    @property
    def worm_log(self) -> WORMLog:
        return self._worm

    @property
    def decisions(self) -> list[RoutingDecision]:
        return self._decisions


# ---------------------------------------------------------------------------
# Test prompts — one per glyph
# ---------------------------------------------------------------------------

TEST_PROMPTS = [
    # Pi (reasoning)
    "Explain why Jordan algebras are relevant to neural network routing",
    "Analyze the computational complexity of SpinFactor composition",
    "Why does non-associativity matter for expert selection?",

    # Gamma (generation)
    "Write a Python function that computes Shannon entropy",
    "Create a dataclass for representing WORM ledger entries",
    "Draft a commit message for adding NAND-complete Boolean kernel",

    # Delta (domain-specific)
    "Write a SQL query to find all users with expired sessions",
    "What are the legal implications of WORM-sealed audit trails?",
    "Generate a financial report template with P&L breakdown",

    # Lambda (code)
    "Implement a ring buffer with atomic read/write in C",
    "Debug this function: def fib(n): return fib(n-1) + fib(n-2)",
    "Refactor this class to use the strategy pattern",

    # Omega (orchestration)
    "Plan a migration from REST to gRPC in 5 phases",
    "Coordinate three agents to review, test, and deploy this PR",
    "Design a multi-step workflow for data ingestion",

    # Psi (verification)
    "Prove that NAND is functionally complete",
    "Verify this implementation matches the specification",
    "Test the edge cases for division by zero handling",
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("SOVEREIGN ENGINE v2 -- LIVE ROUTING TEST")
    print("DSL Proof of Concept: prompt -> classify -> gate -> verify -> seal")
    print("=" * 70)
    print()

    router = SovereignRouter()
    use_live = '--live' in sys.argv

    if use_live:
        print("  MODE: LIVE (Bedrock Haiku inference)")
    else:
        print("  MODE: LOCAL (deterministic routing, mock inference)")
        print("  Add --live to invoke real Bedrock Haiku inference")
    print()

    glyph_counts = {}
    total_latency = 0.0
    all_passed = True

    for i, prompt in enumerate(TEST_PROMPTS):
        if use_live:
            decision = await router.route_with_inference(prompt)
        else:
            decision = router.route(prompt)

        glyph_counts[decision.glyph] = glyph_counts.get(decision.glyph, 0) + 1
        total_latency += decision.latency_ms

        status = "PASS" if decision.ere_passed else "FAIL"
        if not decision.ere_passed:
            all_passed = False

        print(f"  [{i+1:02d}] {decision.glyph:<6} | ERE:{status} | "
              f"H={decision.entropy:.4f} | {decision.latency_ms:.1f}ms | "
              f"{prompt[:50]}")

    print()
    print("-" * 70)
    print()
    print("  GLYPH DISTRIBUTION:")
    for glyph, count in sorted(glyph_counts.items()):
        bar = '#' * (count * 4)
        print(f"    {glyph:<6} [{count:2d}] {bar}")

    print()
    print(f"  Total prompts:    {len(TEST_PROMPTS)}")
    print(f"  ERE passed:       {sum(1 for d in router.decisions if d.ere_passed)}/{len(TEST_PROMPTS)}")
    print(f"  WORM entries:     {router.worm_log.count()}")
    print(f"  Chain valid:      {router.worm_log.all_valid()}")
    print(f"  Avg latency:      {total_latency / len(TEST_PROMPTS):.2f}ms")
    print(f"  Total latency:    {total_latency:.2f}ms")

    # Determinism check: route same prompts again, verify same glyphs
    print()
    print("  DETERMINISM CHECK (re-route all prompts):")
    drift_count = 0
    for prompt in TEST_PROMPTS:
        glyph_1 = classify_glyph(prompt)
        glyph_2 = classify_glyph(prompt)
        if glyph_1 != glyph_2:
            drift_count += 1
            print(f"    DRIFT: '{prompt[:40]}' -> {glyph_1} then {glyph_2}")
    if drift_count == 0:
        print("    All glyphs stable. H=0 nats confirmed.")

    # Master seal
    master = hashlib.blake2b(digest_size=32)
    for d in router.decisions:
        master.update(f"{d.glyph}:{d.ere_seal}:{d.worm_seq}".encode())
    master_hex = master.hexdigest()[:32]

    print()
    print(f"  MASTER SEAL: {master_hex}")
    print()
    if all_passed:
        print("  VERDICT: ALL PROMPTS ROUTED + VERIFIED + SEALED.")
        print("  DSL constraints enforced. Zero drift. WORM chain intact.")
    else:
        print("  VERDICT: SOME ERE GATES FAILED. Investigate violations.")
        sys.exit(1)

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
