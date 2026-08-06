# Agent Brief: Sovereign Engine v2

**For the build agents in the C IDE and Python environment.**

Read this before touching any file. This is the complete architectural
picture. Build in order. Do not skip gaps. Do not stub.

---

## The One Sentence

The routing decision must be a proof, not a probability.

---

## What Exists (Do Not Break)

All of these are working in `/c/tmp/sovereign-reverse/engine/src/`:

- `routing/pipeline.py` -- 11-stage pipeline, tested
- `routing/jordan_moe.py` -- Jordan algebra, correct math, pure stdlib
- `routing/parser.py` -- payload blocklist, inverted AST
- `routing/sparse.py` -- SparseActivation, RoutingNode, NANDFilter
- `routing/dispatch.py` -- async expert dispatch
- `routing/symbolic.py` -- SymbolicGraph, JordanTransformer
- `routing/jacobian.py` -- numerical Jacobian
- `routing/constraints.py` -- ConstraintEval
- `core/crypto.py` -- Blake3 + Ed25519
- `core/evidence.py` -- WORM ledger
- `daemon/python_daemon.py` -- TCP daemon, PING/PONG
- `bridge/http_server.py` -- REST bridge for C IDE
- `tools/` -- 50+ tools, registry, approval engine
- `agents/react.py` -- ReAct loop
- `agents/mcts.py` -- MCTS with PUCT
- `continuity/` -- checkpoint + replay
- `retrieval/` -- RAG pipeline

---

## Gap 1: Wire JordanMoEGate into SparseActivation

**File to change:** `routing/sparse.py`

**Current:** `RoutingNode.gate()` uses a sigmoid function.

**Target:** Replace with `JordanMoEGate.gate()` from `routing/jordan_moe.py`.

The Jordan gate:
1. Builds a `SpinFactor` for each expert from its signal affinities
2. Computes all pairwise Jordan products (non-associative cross terms)
3. Runs `FixedPointSolver` per expert to find idempotent attractors
4. Uses idempotent scalar component as routing weight
5. Applies top-k sparsity on the fixed-point weights

The sigmoid gate should become the fallback only if Jordan gate fails.

**How to wire it:**

```python
# In SparseActivation.__init__:
from .jordan_moe import JordanMoEGate
self.jordan_gate = JordanMoEGate(top_k=top_k)

# In SparseActivation.compute():
# Replace the gating_scores loop with:
jordan_result = self.jordan_gate.gate(
    signals=signals,
    expert_names=expert_names,
    affinities={name: self.routing_nodes[name].signal_affinity
                for name in expert_names},
    expert_mask=expert_mask
)
gating_scores = jordan_result.weights
```

---

## Gap 2: Replace MultiProvider keyword routing with QRA tensor

**File to change:** `runtime/providers/multi.py`

**Current:** `classify_task()` does keyword scoring — counts words like
"function", "debug", "write", "analyze" and picks a model.

**Target:** Use the QRA routing tensor to route provider selection.

The QRA tensor Q is 6x6. Map the six glyphs to provider capabilities:
- Pi (0x01) -- code tasks (Nemotron)
- Gamma (0x03) -- reasoning tasks (Nemotron)
- Delta (0x04) -- chat/creative tasks (Mistral)
- Lambda (0xFF) -- identity/passthrough (Ollama local)
- Omega (0x0A) -- terminal/commit state
- Psi (0x0B) -- mixed/uncertain (fallback)

The routing pipeline already produces `active_experts` and `weights`.
Feed that signal into `MultiProvider.invoke_model()` instead of
running `classify_task()` independently.

**Pseudocode:**
```python
# In MultiProvider.invoke_model():
# If routing context is available:
if routing_context and "glyph" in routing_context:
    glyph = routing_context["glyph"]
    provider = self.glyph_to_provider[glyph]
else:
    # fallback to existing classify_task
    task_type = classify_task(messages, system)
    provider = self.task_to_provider[task_type]
```

---

## Gap 3: WORM-seal every routing decision

**File to change:** `routing/pipeline.py`

**Current:** Routing pipeline runs 11 stages, returns `PipelineTrace`.
Nothing is sealed to the ledger.

**Target:** Every `route_with_trace()` call should append a sealed
event to the WORM ledger.

The event should contain:
- `input_hash`: Blake3 of the input text
- `intent`: the parsed intent
- `active_experts`: which experts were activated
- `weights`: the routing weights
- `jordan_converged`: whether Jordan fixed-point converged
- `nand_suppressed`: which experts were NAND-filtered
- `timestamp`: Unix nanoseconds

**How to wire it:**

```python
# In RoutingPipeline.__init__:
from ..core.evidence import WORMLedger
from ..core.crypto import generate_signing_key
import os
from pathlib import Path

signing_key = generate_signing_key()
self._ledger = WORMLedger(
    Path(os.environ.get("WORM_LEDGER_PATH", "routing_worm.jsonl")),
    signing_key
)

# At end of route_with_trace():
routing_event = {
    "input_hash": hash_content(input_text.encode()).hex(),
    "intent": trace.parse.intent,
    "confidence": trace.parse.confidence,
    "active_experts": trace.routing.active_experts,
    "weights": {k: round(v, 6) for k, v in trace.routing.weights.items()},
    "jordan_converged": trace.jordan.routing_features.get("stability_score", 0) > 0.5,
    "nand_suppressed": trace.routing.nand_suppressed,
    "payload_blocked": trace.parse.payload_blocked,
}
self._ledger.append(
    "routing_decision",
    json.dumps(routing_event).encode(),
    {"tick": getattr(self, "_tick_counter", 0)}
)
self._tick_counter = getattr(self, "_tick_counter", 0) + 1
```

---

## Gap 4: Wire ERE gates on agent output

**File to create:** `tools/ere.py`

ERE = Expected Reasoning Error. Five gates every agent output must pass.

```python
import hashlib
import re
from dataclasses import dataclass

@dataclass
class EREResult:
    passed: bool
    gates: dict[str, bool]  # P1-P5
    seal: str | None        # SHA-256 if all pass, None otherwise
    violations: list[str]

class EREGate:
    P1_PATTERNS = [r"sk-[a-zA-Z0-9]+", r"api_key\s*=\s*['"][^'"]+",
                   r"password\s*=\s*['"][^'"]+"]
    P2_PATTERNS = [r"eval\s*\(", r"exec\s*\(", r"__import__\s*\("]
    P3_PATTERNS = [r"while\s+[Tt]rue\s*:", r"while\s+1\s*:"]
    P4_PATTERNS = [r"telemetry", r"analytics\.track", r"mixpanel", r"segment\.track"]

    def check(self, agent_id: str, intent: str, output: str) -> EREResult:
        gates = {}
        violations = []

        # P1: No secrets
        gates["P1"] = not any(re.search(p, output, re.IGNORECASE)
                               for p in self.P1_PATTERNS)
        if not gates["P1"]:
            violations.append("P1: hardcoded secret detected")

        # P2: No eval
        gates["P2"] = not any(re.search(p, output) for p in self.P2_PATTERNS)
        if not gates["P2"]:
            violations.append("P2: code injection pattern detected")

        # P3: Loop safety
        has_while = any(re.search(p, output) for p in self.P3_PATTERNS)
        has_break = "break" in output or "return" in output
        gates["P3"] = not has_while or has_break
        if not gates["P3"]:
            violations.append("P3: infinite loop without break")

        # P4: No telemetry
        gates["P4"] = not any(re.search(p, output, re.IGNORECASE)
                               for p in self.P4_PATTERNS)
        if not gates["P4"]:
            violations.append("P4: telemetry beacon detected")

        # P5: Audit hash (only if P1-P4 pass)
        all_pass = all(gates.values())
        seal = None
        if all_pass:
            payload = f"{agent_id}:{intent}:{output}"
            seal = hashlib.sha256(payload.encode()).hexdigest()
            gates["P5"] = True
        else:
            gates["P5"] = False

        return EREResult(
            passed=all_pass,
            gates=gates,
            seal=seal,
            violations=violations
        )
```

Wire this into `AgentDispatch._run_expert()`:
After the expert returns output, run `EREGate().check()`.
If it fails, log the violation to WORM and return a failure result
instead of propagating the invalid output.

---

## Gap 5: C IDE bridge reaches Jordan routing

**File to change:** `bridge/http_server.py`

Add endpoint: `POST /routing/trace`

This exposes the full pipeline trace to the C IDE so it can show:
- Which experts were activated
- Whether Jordan fixed-point converged
- The WORM seal of the routing decision
- The ERE gate results

```python
async def _handle_routing_trace(self, request):
    from aiohttp import web
    data = await request.json()
    input_text = data.get("input", "")
    if not input_text:
        return web.json_response({"error": "input required"}, status=400)

    # Use the sovereign engine's routing pipeline
    # (needs SovereignEngine wired into bridge)
    trace = await self.routing_pipeline.route_with_trace(input_text, {})
    summary = trace.summary()
    return web.json_response({
        "intent": summary["intent"],
        "active_experts": summary["active_experts"],
        "weights": summary["weights"],
        "jordan_stable": summary["stability_score"] > 0.5,
        "nand_suppressed": summary["nand_suppressed"],
        "payload_blocked": summary["blocked_experts"],
        "worm_sealed": True  # after Gap 3 is done
    })
```

---

## Build Order

1. **Gap 4 first** -- `tools/ere.py` is self-contained, no dependencies
2. **Gap 1** -- wire Jordan into SparseActivation
3. **Gap 3** -- WORM-seal routing decisions
4. **Gap 2** -- QRA-drive MultiProvider
5. **Gap 5** -- expose routing trace to C IDE

Run the existing test after each gap:
```bash
cd /c/tmp/sovereign-reverse/engine
python -u -c "
import sys, asyncio
sys.path.insert(0, '.')
async def test():
    from src.routing.pipeline import RoutingPipeline
    async def code_fn(text, ctx): return {'text': 'code: ' + text[:40]}
    async def query_fn(text, ctx): return {'text': 'query: ' + text[:40]}
    pipeline = RoutingPipeline(
        experts={'code_agent': code_fn, 'query_agent': query_fn},
        top_k=1
    )
    for text in [
        'write a python fibonacci function',
        'what is the jacobian of a neural network',
        'execute shell rm rf SYSTEM file etc passwd',
    ]:
        trace = await pipeline.route_with_trace(text)
        s = trace.summary()
        print('Intent:', s['intent'], 'Active:', s['active_experts'])
asyncio.run(test())
"
```

Expected: code/query routing correct, malicious input blocked.

---

## The Invariant

Every agent output must satisfy:

```
V(output) = 1 IFF:
  ERE_P1(output) = true      -- no secrets
  AND ERE_P2(output) = true  -- no eval
  AND ERE_P3(output) = true  -- no infinite loop
  AND ERE_P4(output) = true  -- no telemetry
  AND routing_sealed = true  -- WORM seal exists
  AND jordan_converged = true -- routing attractor found
```

If V = 0, the output does not propagate. The agent halts.
The WORM chain records the halt. The chain is append-only.

---

## What Not to Touch

- Do not rewrite the routing pipeline from scratch
- Do not replace the WORM ledger format
- Do not change the Jordan product formula
- Do not add new frameworks (no LangChain, no CrewAI)
- Do not add numpy to the routing layer (it is pure stdlib by design)
- Do not add external embedding services to routing (routing is local)

The routing layer must remain:
- Pure Python stdlib
- Zero network calls
- Deterministic given same input
- H = 0 nats after Jordan gate

---

Ahmad Ali Parr / SNAPKITTYWEST / August 2026
