# Sovereign Engine v2

**QRA-routed. Jordan-gated. WORM-sealed.**

This is the architectural target for the sovereign Python LLM engine.
The v1 engine at `/c/tmp/sovereign-reverse/engine` is the working base.
This repo contains the wiring plan, the missing bridges, and the
architectural spec the build agents should implement.

## The Gap

v1 has all the right components but they are not connected to each other
correctly. The Jordan algebra sits unused. The QRA tensor is not driving
routing. WORM is not sealing routing decisions. The C IDE bridge does not
reach the algebraic routing layer.

## The Target Architecture

```
User Input
    |
    v
RegexParser + ASTBuilder       -- payload-weight inversion (working)
    |
    v
SymbolicGraph + JordanTransformer  -- eigendecompose (working)
    |
    v
JordanMoEGate                  -- REPLACE sigmoid with Jordan algebra (GAP)
    |
    v
QRA Tensor routing             -- H=0 nats deterministic (GAP: not wired)
    |
    v
WORM seal routing decision     -- every routing choice sealed (GAP)
    |
    v
AgentDispatch + MergeOutput    -- working
    |
    v
ERE gates on output            -- P1-P5 verification (GAP: not wired)
    |
    v
WORM seal final output         -- working (in ledger, not in routing path)
```

## What the Agents Need to Build

See `AGENT_BRIEF.md` for the full spec.
See `architecture/` for diagrams and pseudocode.
See `gaps/` for the exact files that need changing.

## License

BSL 1.1 -> MIT 2029-01-01
Ahmad Ali Parr / SNAPKITTYWEST / Bel Esprit D'Accord Irrevocable Trust
