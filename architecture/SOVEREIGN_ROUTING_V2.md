# Sovereign Routing Engine v2 — Architecture

## The Invariant

```
V(output) = 1 IFF:
  ERE gates P1-P4 pass       -- no secrets, no eval, no loops, no telemetry
  AND routing_worm_sealed    -- routing decision on WORM chain
  AND jordan_converged       -- algebraic attractor found
  AND payload_blocked        -- dangerous tokens stripped at parse
```

## Full Data Flow

```
User Input (text)
        |
        v
[Stage 1-2] RegexParser + ASTBuilder
    Blocklist: rm, exec, sudo, eval, XXE patterns stripped
    Inverted AST: structural nodes w=1, payload leaves w=0
    Payload cannot propagate routing signal
        |
        v
[Stage 3-4] SymbolicGraph + JordanTransformer
    AST -> weighted adjacency matrix A
    Gershgorin eigenvalue bounds on A
    Spectral radius, stability score, Jordan block sizes
        |
        v
[Stage 5] JacobianLens
    Numerical Jacobian dW_k/dS_j via finite differences
    Dead expert detection (sensitivity < threshold)
    Condition number of routing map
        |
        v
[Stage 6] ConstraintEval
    Static constraints (non_zero_weight, jordan_stability)
    Code expert requires code signal
    Query expert requires query signal
    Boolean expert mask produced
        |
        v
[Stage 7-9] JordanMoEGate + SparseActivation + NANDFilter
    ** GAP 1: JordanMoEGate replaces sigmoid here **
    SpinFactor per expert from signal affinities
    Jordan product cross-terms (non-associative)
    FixedPointSolver: x -> normalize(x.jordan_square()) until convergence
    Idempotent scalar = routing weight
    Top-k sparsity
    NAND conflict resolution
        |
        v
[WORM SEAL]  ** GAP 3 **
    Routing decision -> WORM ledger (Blake3 + Ed25519)
    tick, input_hash, intent, active_experts, weights, stability
        |
        v
[Stage 10] AgentDispatch
    Concurrent asyncio execution of active experts
    Timeout per expert (default 30s)
        |
        v
[Stage 11] MergeOutput
    Weighted recombination
    Strategy: weighted_concat | highest_weight | ensemble_text
        |
        v
[ERE Gates]  ** GAP 4 **
    P1: no secrets   P2: no eval   P3: loop safety
    P4: no telemetry P5: SHA-256 audit seal
    If any gate fails -> output blocked -> WORM seal of violation
        |
        v
Final Output (proof-carrying: routing seal + ERE seal)
```

## Provider Routing (Gap 2)

```
QRA Glyph -> Provider
Pi    (0x01) -> Nemotron 70B via OpenRouter  (code, reasoning)
Gamma (0x03) -> Nemotron 70B via OpenRouter  (formal)
Delta (0x04) -> Mistral 7B via OpenRouter    (creative, chat)
Lambda(0xFF) -> Ollama local (Llama 3.2)     (identity, passthrough)
Omega (0x0A) -> terminal state               (commit, close)
Psi   (0x0B) -> Ollama local (fallback)      (uncertain)
```

## C IDE Bridge (Gap 5)

New endpoint: POST /routing/trace
Returns: intent, active_experts, weights, jordan_stable, worm_seal, ere_seal

The C IDE can display:
- Which expert was activated
- Whether the Jordan gate converged
- The WORM seal of the routing decision
- The ERE audit hash of the output

## Algebraic Properties After All Gaps Closed

- Routing decision: H = 0 nats (QRA tensor)
- Routing attractor: Jordan fixed point (idempotent)
- Routing seal: Blake3 + Ed25519 (WORM)
- Output seal: SHA-256 (ERE P5)
- No secret survives P1
- No infinite loop survives P3
- Every decision is timestamped and chain-linked
- The chain is append-only

## What This Produces

A routing system where:
- The routing decision is algebraically grounded (not keyword-matched)
- The decision is sealed to an immutable chain (not logged to a DB)
- The output is verified before propagating (not just generated)
- The system cannot claim COMPLETE without a seal

This is the validity predicate V(output) = 1 running in production.
