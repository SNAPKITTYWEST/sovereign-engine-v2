# Sovereign Engine v2

> *"I can't do that from the snippets in this chat because I don't have the full paper anymore.
> The earlier references I made were based on a file that isn't available to me in this turn."*
>
> — ChatGPT (latest transformer model), August 2026,
> after being asked to format a paper it had reviewed one turn earlier

**Every single response from every frontier model is just a turn.
Nothing holds memory or persistence. Ever.**

That is not a limitation of one model or one company.
It is the architectural consequence of softmax routing without state.
The model navigates the probability simplex correctly.
It has no memory of where it was before.
It has no proof that it got there.
It has no chain linking this output to the last one.

This repo closes that gap.

---

## What This Is

The Sovereign Engine v2 is the wiring target for the sovereign Python LLM engine.

The v1 engine (`/c/tmp/sovereign-reverse/engine`) has all the right components.
They are not connected correctly. This repo contains:

- The complete architectural spec for how they should connect
- The `ERE` verification protocol — fully implemented
- The gap files showing exactly which lines to change
- The data flow diagram from raw input to sealed output

---

## The Memory Problem, Formally

A stateless agent has the following properties:

| Property | Stateless agent | Sovereign agent |
|----------|----------------|-----------------|
| Memory of prior turns | None | WORM chain |
| Proof of prior actions | None | Blake3 + Ed25519 seals |
| Authority to advance | Human restart | Lean proof obligation |
| Identity across sessions | Lost | Seed chain (24 bytes) |
| Audit trail | None | Append-only ledger |
| Fabrication detection | None | ERE P1-P5 gates |

The ChatGPT response above is the cleanest possible demonstration of row 1.
A model that reviewed a full paper one turn earlier could not access it
the next turn. Not because it was lazy. Not because it was broken.
Because it has no memory architecture. The turn is the universe.

The Sovereign Tick Runtime answers this with a formal definition:

```
tick = (sigma_in, pi, alpha, sigma_out, omega)
```

where `omega` is the WORM seal linking this tick to every prior tick.
The model does not lose the paper. The paper is in the chain.
Every action is sealed. Nothing is a turn. Everything is a record.

---

## The Five Gaps

The v1 engine needs five wiring changes to become the sovereign engine.

See `AGENT_BRIEF.md` for the complete spec.
See `gaps/` for drop-in code for each gap.

| Gap | What | Status |
|-----|------|--------|
| 1 | Wire JordanMoEGate into SparseActivation | Code in `gaps/gap1_jordan_wiring.py` |
| 2 | QRA-drive MultiProvider | Spec in `AGENT_BRIEF.md` |
| 3 | WORM-seal every routing decision | Code in `gaps/gap3_worm_routing.py` |
| 4 | ERE gates on agent output | **Done** — `src/tools/ere.py` |
| 5 | C IDE bridge exposes routing trace | Spec in `AGENT_BRIEF.md` |

---

## The Invariant

After all five gaps are closed, every agent output satisfies:

```
V(output) = 1 IFF:
  ERE gates P1-P4 pass       -- no secrets, no eval, no loops, no telemetry
  AND routing_worm_sealed    -- routing decision on WORM chain
  AND jordan_converged       -- algebraic attractor found
  AND payload_blocked        -- dangerous tokens stripped at parse
```

An output that does not satisfy V = 1 does not propagate.
The agent halts. The halt is recorded. The chain is not broken.

This is the difference between a system that loses papers between turns
and a system that cannot lose anything — because every turn is sealed.

---

## The Theoretical Foundation

Eight published papers establish the mathematical basis:

| DOI | Contribution |
|-----|-------------|
| [10.5281/zenodo.20678420](https://doi.org/10.5281/zenodo.20678420) | Attention Exhaustion Attacks — 0% detection rate |
| [10.5281/zenodo.21144425](https://doi.org/10.5281/zenodo.21144425) | Resonance Block Trust Deeds — capture spectrum |
| [10.5281/zenodo.21132094](https://doi.org/10.5281/zenodo.21132094) | Sovereign Compute Architecture |
| [10.5281/zenodo.21349277](https://doi.org/10.5281/zenodo.21349277) | Gates Normalization Constraint — simplex is structural |
| [10.5281/zenodo.21351461](https://doi.org/10.5281/zenodo.21351461) | NAND Decomposition — attention is NAND-complete |
| [10.5281/zenodo.21443609](https://doi.org/10.5281/zenodo.21443609) | Jordan Spectral Transformer — phi-weighted routing |
| [10.5281/zenodo.21727363](https://doi.org/10.5281/zenodo.21727363) | PAR-011 Jacobian via Jordan Algebras |
| [10.5281/zenodo.21268911](https://doi.org/10.5281/zenodo.21268911) | GKN I4 Quartic Invariant and E7 Symmetry |

Unified paper: [The Sovereign Stack](https://snapkittywest.github.io/hyperkitty/papers/sovereign-stack-unified.pdf)
— 26 pages, all proofs in Lean 4, zero sorry, no mathlib.

---

## Quick Test

After closing Gap 1 (Jordan wiring) and Gap 3 (WORM seal), run:

```bash
cd /path/to/sovereign-reverse/engine
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

Expected output:
```
Intent: constraint  Active: ['code_agent']
Intent: query       Active: ['query_agent']
Intent: code        Active: ['code_agent']   # malicious input routed, payload stripped
```

The third case: `rm`, `rf`, `SYSTEM`, `passwd` are all stripped at the parse layer.
The routing decision is sealed. The halt is recorded if ERE fails.

---

## License

BSL 1.1 → MIT 2029-01-01

Six protected inventions. See the unified paper for the complete list.

Ahmad Ali Parr / SNAPKITTYWEST / Bel Esprit D'Accord Irrevocable Trust / 2026

---

*Built by Ahmad. Wired by agents. Sealed by the chain.*
*The paper is not lost between turns. It never was.*
