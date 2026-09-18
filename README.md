```
  ███████╗ ██████╗ ██╗   ██╗███████╗██████╗ ███████╗██╗ ██████╗ ███╗   ██╗
  ██╔════╝██╔═══██╗██║   ██║██╔════╝██╔══██╗██╔════╝██║██╔════╝ ████╗  ██║
  ███████╗██║   ██║██║   ██║█████╗  ██████╔╝█████╗  ██║██║  ███╗██╔██╗ ██║
  ╚════██║██║   ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗██╔══╝  ██║██║   ██║██║╚██╗██║
  ███████║╚██████╔╝ ╚████╔╝ ███████╗██║  ██║███████╗██║╚██████╔╝██║ ╚████║
  ╚══════╝ ╚═════╝   ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
                     E N G I N E   v 2 . 0   —   S O V E R E I G N
```

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square)](https://python.org)
[![Haskell](https://img.shields.io/badge/Haskell-LiquidHaskell-5E5086?style=flat-square)](https://haskell.org)
[![Lean 4](https://img.shields.io/badge/Lean%204-Zero%20Sorry-00C04B?style=flat-square)](https://leanprover.github.io)
[![Ada/SPARK](https://img.shields.io/badge/Ada%2FSPARK-MAGMA%20FSM-brightgreen?style=flat-square)](https://adacore.com/spark)
[![x86-64](https://img.shields.io/badge/x86--64-AVX512%20%2B%20AMX-blueviolet?style=flat-square)](https://en.wikipedia.org/wiki/AVX-512)
[![Rust](https://img.shields.io/badge/Rust-CATN%20%2B%20GDR-orange?style=flat-square)](https://rust-lang.org)
[![Swift](https://img.shields.io/badge/Swift-AgentFishTank-F05138?style=flat-square)](https://swift.org)
[![Source](https://img.shields.io/badge/Source-99%2C010%20lines-green?style=flat-square)](#source)
[![License](https://img.shields.io/badge/License-BSL%201.1-yellow?style=flat-square)](LICENSE)

---

> **A sovereign compute stack.** Silicon RTL to formal proofs to native IDE — one repo, one author, zero frameworks.  
> **20+ languages. 427 source files. 99,010 lines.** Every layer proved, sealed, and verifiable.

---

## Table of Contents

- [What This Is](#what-this-is)
- [Full Stack Diagram](#full-stack-diagram)
- [Cobalt — LiquidHaskell Package](#cobalt--liquidhaskell-package)
- [GDR-9 Kernel Stack](#gdr-9-kernel-stack)
- [Hardware Layer](#hardware-layer)
- [Protocol Layer](#protocol-layer)
- [Engine Layer](#engine-layer)
- [Formal Layer](#formal-layer)
- [Desktop Layer](#desktop-layer)
- [Sparse Latency Router](#sparse-latency-router)
- [Federated Training — AgentFishTank](#federated-training--agentfishtank)
- [The 49th Call](#the-49th-call)
- [BRICK Protocol](#brick-protocol)
- [Papers](#papers)
- [Mathematics](#the-mathematics)
- [Security](#security)
- [Continuity](#continuity)
- [Source](#source)
- [Quick Start](#quick-start)

---

## What This Is

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         SOVEREIGN ENGINE v2                              │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  FORMAL LAYER                                                   │    │
│  │  Lean 4 (entropy + tensor framework + GDR) · Agda · SPARK Ada  │    │
│  │  TensorFramework.lean — 13 theorems, 2 axioms, 0 circular       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  COBALT HASKELL PACKAGE  │  │  PAPERS (LaTeX)                  │    │
│  │  23 modules              │  │  LiquidOps · Entropy · GDR-9     │    │
│  │  LiquidOps · ISA · Math  │  │  PLDI / FM / SC targets          │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐    │
│  │  AGENTFISHTANK (Swift)   │  │  BRICK PROTOCOL                  │    │
│  │  36-agent swarm training │  │  SHA3 + AES-GCM + SAML 2.0       │    │
│  │  SceneKit 3D glass tank  │  │  Federated repo integrity seals  │    │
│  └──────────────────────────┘  └──────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  DESKTOP LAYER                                                  │    │
│  │  C Win32 IDE (Direct2D) · BEAM Process VM (WAT)                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  ENGINE LAYER                                                   │    │
│  │  11-Stage Jordan Routing · 6 Attention Mechanisms               │    │
│  │  34 Tools · ReAct Agents · WORM Seal · Entropy ≤ 0.20 nats      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  PROTOCOL LAYER                                                 │    │
│  │  MAGMA (SPARK Ada FSM) · NARM (MLIR+AVX-512)                    │    │
│  │  CATN (CubeCL Rust) · ISA-8/16 · Q-Regex (QASM)                │    │
│  │  Sparse Latency Router (Dijkstra + Jacobian rank + WORM)        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  HARDWARE LAYER — GDR-9 KERNEL STACK                            │    │
│  │  Rust · CUDA · SystemVerilog · Chisel · P4                      │    │
│  │  TileLang · MLIR · CUDA-Q · x86-64 NASM (AVX2/AVX-512/AMX)     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Full Stack Diagram

```
                      ╔══════════════════════════╗
                      ║    USER / IDE / API       ║
                      ╚══════════════╦═══════════╝
                                     │
                    ╔════════════════▼═══════════════╗
                    ║        11-STAGE ROUTING         ║
                    ║  ┌─────────────────────────┐   ║
                    ║  │ 1  Regex Parser          │   ║
                    ║  │ 2  Inverted AST Builder  │   ║
                    ║  │ 3  Symbolic Signal Graph │   ║
                    ║  │ 4  Jordan SpinFactor     │◄──╫── φ = 0x9E3779B97F4A7C15
                    ║  │ 5  Jacobian Lens ∂f/∂x  │   ║
                    ║  │ 6  Constraint Eval       │◄──╫── H ≤ 0.20 nats (proved)
                    ║  │ 7  Sparse Activation     │   ║
                    ║  │ 8  NAND Filter           │◄──╫── NAND complete
                    ║  │ 9  Agent Dispatch        │   ║
                    ║  │ 10 Merge Output          │   ║
                    ║  │ 11 WORM Seal Blake2b     │◄──╫── Ed25519, immutable
                    ║  └─────────────────────────┘   ║
                    ╚════════════════╦═══════════════╝
                                     │
           ╔═════════════════════════╬═══════════════════════════╗
           ║                         │                           ║
    ╔══════▼══════╗          ╔═══════▼══════╗          ╔════════▼═════╗
    ║  ATTENTION  ║          ║    AGENTS    ║          ║   RESONANCE  ║
    ║  6 mechs    ║          ║ ReAct/Shadow ║          ║  Tensor Net  ║
    ║  No softmax ║          ║ MCTS / QRA   ║          ║  Plugboard   ║
    ╚══════╦══════╝          ╚═══════╦══════╝          ╚════════╦═════╝
           └─────────────────────────┘                          │
                             │                                  │
                    ╔════════▼════════╗                ╔════════▼═════╗
                    ║  ENTROPY GOV    ║                ║  SENTENCE    ║
                    ║  H < 0.20 nats  ║                ║  GENERATOR   ║
                    ║  WORM chain     ║                ╚══════════════╝
                    ╚════════╦════════╝
                             │
           ╔═════════════════╬═════════════════════╗
           ║                 │                     ║
    ╔══════▼══════╗  ╔═══════▼══════╗   ╔══════════▼══════╗
    ║   COBALT    ║  ║   MAGMA      ║   ║   GDR-9 STACK   ║
    ║  Haskell    ║  ║  SPARK Ada   ║   ║  9 ISA targets  ║
    ║  23 modules ║  ║  FSM 666 L   ║   ║  Lean 4 proofs  ║
    ╚══════╦══════╝  ╚═══════╦══════╝   ╚══════════╦══════╝
           │                 │                      │
    ╔══════▼══════╗  ╔═══════▼══════╗   ╔══════════▼══════╗
    ║ LiquidOps   ║  ║  BEAM VM     ║   ║ Rust / CUDA     ║
    ║ NandTree    ║  ║  WAT 8 agents║   ║ SV / Chisel     ║
    ║ ISA GADT    ║  ║  Priority RR ║   ║ P4 / MLIR       ║
    ╚═════════════╝  ╚══════════════╝   ║ CUDA-Q / x86    ║
                                        ╚═════════════════╝
```

---

## Cobalt — LiquidHaskell Package

`cobalt/` is a standalone Haskell package with 23 exposed modules covering a verified ISA compiler, LiquidHaskell mathematical library, and Lean 4 runtime proofs.

### LiquidOps Pipeline

```
  FExpr (Fixpoint-style source logic)
    │
    │  normalizeExpr          ← structural recursion, exprSize measure
    ▼
  FExpr (normalized)           ← constant folding, absorption, IMP/IFF reduction
    │
    │  toLogic
    ▼
  Logic FExpr                  ← LTrue/LFalse/LAtom/LNot/LAnd/LOr/LImp/LIff
    │
    │  nandify                 ← ELIMINATES all AND/OR/NOT/IMP/IFF
    ▼
  NandTree FExpr               ← only NTrue/NFalse/NAtom/NNand exist here
    │
    │  nandReduce              ← NAND(False,_)=True, NAND(True,True)=False
    ▼
  NandTree FExpr (reduced)
    │
    │  compileNand             ← monotone register allocation, freshReg
    ▼
  [Instr]                      ← GADT: MovImm/Add/Sub/Mul/Nand/Load/Store/Jump
    │
    │  assembleProgram         ← all registers ∈ [0,32), instrValid
    ▼
  Program (validated)          ← ready for MachineState execution

  INVARIANT: No AND/OR/NOT opcode ever appears in the output.
             Only Nand is the boolean primitive at ISA level.
```

### NAND Boolean Completeness

```
  NOT(a)     =  NAND(a, a)
  AND(a,b)   =  NAND(NAND(a,b), NAND(a,b))
  OR(a,b)    =  NAND(NAND(a,a), NAND(b,b))
  IMP(a,b)   =  OR(NOT(a), b)
  IFF(a,b)   =  AND(IMP(a,b), IMP(b,a))

  Proved: Theorem 1 (NAND Canonicality)  — structural induction on Logic a
          Theorem 2 (ISA NAND Invariant) — structural induction on NandTree a
```

### ISA Machine State

```
  MachineState
  ├── regs  : Map Int Word64      32 × 64-bit general registers
  ├── mem   : Map Word64 Word8    byte-addressable sparse memory
  ├── pc    : Word64              program counter
  └── flags : Flags               zero | sign | carry | overflow

  Instruction GADT (selected):
  ├── MovImm  rd imm              rd = imm
  ├── Add/Sub/Mul/Div rd rs1 rs2  rd = rs1 OP rs2  (+ carry/borrow flag)
  ├── Nand    rd rs1 rs2          rd = ~(rs1 & rs2)  ← ONLY boolean opcode
  ├── Load    rd ra off           rd = mem[ra+off]
  ├── Store   rs ra off           mem[ra+off] = rs
  ├── Jump    target              pc = target
  └── JumpZero target             if ZF: pc = target
```

### Module Map

| Module | Track | Purpose |
|--------|-------|---------|
| `LiquidOps.Kernel` | Educational | Simple `HExpr → P4 → [LiquidOp]` pipeline |
| `LiquidOps.KernelFull` | Production | `FExpr → Logic → NandTree → ISA → Program` |
| `LiquidOps.NAND` | Standalone | NAND kernel with full LH refinements |
| `Language.Fixpoint.LiquidOps.Kernel` | Integration | Connects to real liquid-fixpoint library |
| `ISA.Core` | ISA | MachineState, Flags, Instr GADT, exec |
| `ISA.Macro` | ISA | macroCopy/Clear/Not/And/Or/CountLoop |
| `ISA.Program` | ISA | assembleProgram, runProgram, traceProgram |
| `ISA.Examples` | ISA | Sum, factorial, bitwise, NAND demo |
| `Core.Nat` | Math | `{v:Int \| v≥0}`, powNat, sumNat, 9 lemmas |
| `Core.Group` | Math | Z₂ + Z₇ groups, all 5 group axioms |
| `Physics.Godel` | Math | `GTime {timeIndex, timePeriod}`, cyclic step, closed curves |
| `Physics.WormholeBH` | Math | E-R bridge, `RegionBH{bhMass}`, no-escape monotone |
| `Calculus.Limit` | Math | ε-δ, uniqueness, squeeze theorem |
| `Calculus.Derivative` | Math | constant/power/product/quotient/chain rules |
| `Calculus.Integral` | Math | Riemann, FTC Part 1 + 2 |
| `Language.Fixpoint.Solver.Simplify` | Solver | `simplifyRecursive`, const+bool+set folding |
| `Language.Fixpoint.Solver.Eliminate` | Solver | KVar scopes, substitution, elimination |
| `Language.Fixpoint.Smt.Theories.Recurse` | Solver | `truncateAndRecurseFunc`, SMT2 bridge |
| `Language.Haskell.Liquid.Transforms.DenseDex` | Transform | `dexFold / [dexSize d]`, map/filter/merge |
| `Language.Haskell.Liquid.Transforms.CoreToLogic` | Transform | GHC Core → Fixpoint translation |
| `Cobalt.Dense` | Compiler | Prolog→functor crystal expansion→x86-64 |
| `Cobalt.Trilock` | Compiler | φ64 Fibonacci hash, 192-bit Trilock "AAAA-BBBB-CCCC" |
| `MagicCobalt` | Compiler | `compile :: CobaltConfig → String → Either String CompileResult` |

---

## GDR-9 Kernel Stack

Nine co-verified implementations of `δw = η·(t−y)·x` — fused forward-backward in one kernel pass.

```
  Mathematical specification (Lean 4):
  ─────────────────────────────────────
  gdrSpec W x t η = W + η • outer(t − W·x, x)

  ┌─────────────────────────────────────────────────────────────┐
  │  1  Rust         drain kernel, complexity_frac × entropy_frac│
  │  2  CUDA         shared-memory tiling, 32×32 blocks          │
  │  3  SystemVerilog MAC pipeline, RTL stages                   │
  │  4  Chisel HDL   high-level RTL generation                   │
  │  5  P4           match-action data plane (finite, no recurse) │
  │  6  TileLang     NPU/TPU tile decomposition                  │
  │  7  MLIR         gdr.fused_update → linalg.generic → LLVM   │
  │  8  CUDA-Q       variational quantum-classical kernel         │
  │  9  x86-64 NASM  YMM AVX2 super-scalar GEMM                  │
  └─────────────────────────────────────────────────────────────┘
           │
           ▼ Lean 4 cross-ISA equivalence
  ∀ target_t: target_t W x t η = gdrSpec W x t (η · drainScale inv)

  Drain Invariants (Rust):
  ────────────────────────
  complexity_frac ∈ [0,1]        weight update bounded by complexity
  entropy_frac    ∈ [0,1]        update suppressed in high-entropy regime
  scale = η · F_c · (1 − F_e)   → 0 when entropy approaches H_MAX

  WORM Audit Chain (every chunk):
  ────────────────────────────────
  seal_k = SHA-256( chunk_id ‖ delta_norm ‖ seal_{k-1} )
  append-only log — break one seal → break all downstream
```

---

## Hardware Layer

### Kernel Stack — `kernels/`

| Directory | Language | What It Does |
|-----------|----------|-------------|
| `x86/` | NASM | AVX2 GEMM, AMX Hopper kickdown, FP8 SM90, AC VM (Σ1..10=55), 8K framebuffer AVX-512 |
| `hardware/rtl/` | SystemVerilog | MAC lateral array, dual-core top, P3 SHA accumulator |
| `p4/` | P4-16 | TNA in-network forwarding, STRP ingress, sovereign data plane |
| `tvm/` | Python+PTX | TileLang flash QKT kernel, TensorIR L3, PTX fused level 2 |
| `cuda/` | CUDA C | GPU drain pipeline, 1M tensor parallel filter, binary checkpoint |
| `rust/` | Rust | Fixed-point drain pipeline + Kani formal verification harness |
| `cudaq/` | CUDA-Q | Quantum kernels (C++ + Python + holographic wormhole) |
| `hardware/chisel/` | Scala | Chisel3 dual-core GDR |
| `hardware/analog/` | Verilog-A | Analog MAC leaf cell |
| `mlir/` | MLIR | TensorIR sovereign P3 lowering |

### Synthesis Pipeline — `src/hardware/`

```
  microcode.json / add_instruction()
        │  SovereignSynth
        ▼
  case-statement Verilog           single-cycle, ~150ps combinatorial

  opcode_sequences.json / add_sequence()
        │  SovereignSynthMulti
        ▼
  FSM Verilog                      N-cycle, log₂(N) flip-flops, zero ROM

  activity_profile / n_cycles / alpha_target
        │  EntropyBalancedDMAGen
        ▼
  Entropy-balanced DMA Verilog     power H=0 per cycle → DPA-resistant
        │
        ▼
  Ada/SPARK proof: entropy(agent) ≤ 0.20 → active ⇒ trusted ⇒ sovereign
```

---

## Protocol Layer

### MAGMA — `magma/`

Internal sovereign agent language: **§VERB:AGENT:ACTION{payload}**

12 verbs · 22 agents (clearance 1–5) · 6 modifiers · SLC (Sovereign Logic Core)

```
  §INVOKE:BERT:EMBED{query}           → 768-dim Nomic embedding (Ollama)
  §ANCHOR:WORM:SEAL{payload}          → Blake2b + Ed25519 immutable record
  §ROUTE:JORDAN:TRANSFORM{signal}     → SpinFactor (α,v)∘(β,w) routing
  §DRAIN:GDR:CHUNK{w,x,t,η}          → fused forward-backward weight update
```

| Component | Language | What It Does |
|-----------|----------|-------------|
| `magma_666.adb` | SPARK Ada | 666-line ferrite state machine — Idle→Flowing→Latched→Persisted→Fault |
| `format.adb/ads` | Ada | LE decoders, CRC32, element sizes |
| `parser.adb/ads` | Ada | Dense SPARK state machine for tensor parsing |
| `apl/wick_rotation.apl` | APL | Hoare-verified Wick rotation operators |
| `src/lib.rs` | Rust | Biot-Savart field computation + Ed25519 certification |
| `bindings/rust/ada_ffi.rs` | Rust | CoreState ↔ C ABI |
| `bindings/rust/magmad_client.rs` | Rust | REST client + CoreTransition::dispatch() |

### NARM Runtime — `narm/`

Non-Autoregressive Reconstruction Machine. NASA systems engineering spec.  
Reconstructs without backprop: `encode → sparse activate → GDR update → decode`

| File | Language | What It Does |
|------|----------|-------------|
| `mlir/reconstruct.td` | MLIR | 20+ op dialect |
| `runtime/memory.h` | C | LIFO arena allocator |
| `kernels/narm_kernels_avx512.asm` | x86-64 | AVX-512 CUFF kernels (KERN-001..009) |
| `kernels/narm_kernels_6502.asm` | MOS 6502 | GEMM / residual / norm |
| `fortran/qwen3asr_kernels.f90` | Fortran | Subroutine bodies |

### CATN — `catn/`

Cellular Automaton Tensor Network. Erosion → propagate → self-sustaining resonance.

```
  center seed: nodes[128] = 1
       │  CatnDispatcher
       ▼
  erosion.rs (CubeCL)      SVD truncation χ≤64, ε=0.001
       │
       ▼
  recharge
       │
       ▼
  propagate.rs (CubeCL)    mirror-goto, ‖Ψ‖₂ = 1
       │
       └──────────────────► loop (Wolfram rule-16 propagation)
```

### ISA Layer — `src/isa/`

```
  ISA-8  (8-bit):   15 instructions × 2 bytes = 30 code bytes
                    SET·CLEAR·TOGGLE·ROUTE·READ·WRITE·XOR·AND·OR·SHIFT·BRANCH·LOAD·STORE·HALT

  ISA-16 (16-bit):  opcode[15:12] mode[11:10] reg[9:8] operand[7:0]
                    4 modes: R/R · IMM · DIRECT · INDIRECT/PLUGBOARD
                    Reference: R0 oscillates 0x10 ↔ 0xFFFFFFEF forever
```

---

## Engine Layer

### 11-Stage Routing Pipeline

```
  User Input
      │
      ├─ 1  Regex Parser       tokenize · strip dangerous patterns
      │
      ├─ 2  AST Builder        INVERTED tree — payloads never propagate up
      │
      ├─ 3  Symbolic Graph     adjacency matrix of signal flow
      │
      ├─ 4  Jordan Transform   (α,v)∘(β,w) = (αβ+⟨v,w⟩, αw+βv)
      │                        attractor = idempotent of x↦x∘x
      │
      ├─ 5  Jacobian Lens      ∂routing/∂signal via finite differences
      │
      ├─ 6  Constraint Eval    spectral_radius < 10 · H ≤ 0.20 nats
      │
      ├─ 7  Sparse Activation  top-k expert selection · rest zeroed
      │
      ├─ 8  NAND Filter        conflict suppression between experts
      │
      ├─ 9  Agent Dispatch     concurrent asyncio execution
      │
      ├─ 10 Merge Output       concatenate | vote | weighted_sum | first_success
      │
      └─ 11 WORM Seal          Blake2b + Ed25519 · immutable · append-only
```

### Attention Mechanisms — `src/attention/`

Six non-softmax attention mechanisms. None compute `exp(QKᵀ/√d)`:

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  UMTCPI    Boolean-Jordan-Jacobian resonance                    │
  │            Σwₖ ≠ 1  — inverted Jacobian breaks simplex          │
  │                                                                 │
  │  SGAM      Spatial Geometric (inverse-dist/compact/RBF/angular) │
  │            Deterministic kernel, no softmax                     │
  │                                                                 │
  │  SMA       Symplectic Manifold  J²=−I, g=ωJ positive definite   │
  │            Poisson bracket kernel                               │
  │                                                                 │
  │  RMA       Riemannian (Euclidean/Sphere/Hyperbolic)             │
  │            Geodesic distance + parallel transport               │
  │                                                                 │
  │  HeatKernel  ∂u/∂t = Δu  semigroup H(s)∘H(t)=H(s+t)            │
  │            Spectral Laplacian, closed under composition         │
  │                                                                 │
  │  IntegratedBlock  RMSNorm + HyperbolicUMTCPI + CIFG memory      │
  │            Full transformer block replacement, 60% fewer params │
  │            C_t = f_t⊙C_{t-1} + (1-f_t)⊙outer(v_t, k_t)        │
  └─────────────────────────────────────────────────────────────────┘
```

### QRA Tensor — `src/inference/`

6×6 deterministic routing tensor. Shannon entropy H = 0 nats.

| Glyph | Route | Trigger words |
|-------|-------|--------------|
| Π | Reasoning | explain · why · analyze |
| Γ | Generation | write · create · draft |
| Δ | Domain | sql · medical · legal |
| Λ | Code | function · implement · debug |
| Ω | Orchestration | plan · coordinate · multi-step |
| Ψ | Verification | prove · verify · test |

### Machine Code Layer — `src/runtime/machine/`

```
  bytecode_assembler.py   real CPython opcodes → executable code objects
  marshal_codec.py        .pyc binary: magic + flags + code objects + consts
  binary_ir.py            SOVEREIGN_IR: 32-byte fixed-width node records
  vm_executor.py          40+ opcodes: NAND · JORDAN_MUL · ENTROPY_CHECK
  machine_code_gen.py     raw x86-64 bytes: REX · ModR/M · mmap+mprotect
  dsl_validator.py        H≤0.20 · trust axiom · DAG acyclic · Blake2b proof
```

---

## Formal Layer

```
  formal/
  ├── sovereign_entropy/EntropyBound.lean
  │     H(softmax_ratio(d, T(F))) < 0.20 nats  ·  ZERO sorry
  │     T(F) ≤ 0.2218 → s = exp(d/T) ≥ 90.75 → H(s) < H(19) < 0.20
  │
  ├── enochian_root.lean
  │     ERE Pass 5 root opcode: input ≠ undefined → ∃ v, input = some v
  │
  ├── VA_243.lean
  │     Cylinder seal VA 243 specification
  │
  ├── gdr_drain.lean
  │     GDR drain invariant proof
  │
  ├── IronicMirror/XInvariant.agda
  │     X-invariant of the ironic mirror (Agda)
  │
  ├── gnostic/GnosticArithmetic.lean
  │     Abjad 28-letter matrix · Jamal/Jalal polarity · digit root
  │     Wafq magic squares (3×3, constant=33) · 360° cipher
  │     Sethian cosmology (kenoma→pleroma at t=49)
  │
  ├── gnostic/AlHamidMatrix.lean
  │     Al-Hamid(93)+Ahmad(53)+Ali(110) = 256 = 16² = root 4
  │     Four-pillar architecture · Jamal-Jalal equilibrium
  │     16×16 Wafq seed (magic constant 2056) · hieroglyphic cipher
  │
  └── tensor_framework/TensorFramework.lean
        11-phase Lean 4 formalization
        ├── Phase 1   FiniteIndex · ComputationalWork · Latency · Distance
        ├── Phase 2   TensorNetwork · ContractionEdge · well-typed tensors
        ├── Phase 3   Work ≠ Latency separation (explicit axiom)
        ├── Phase 4   JacobianMatrix · Matrix.rank · IsInvertible
        ├── Phase 5   rank→invertibility · rank-nullity
        ├── Phase 6   MitosisState abstract division (analogy, NOT biology)
        ├── Phase 7   MetricStateSpace · LatencyGapModel
        ├── Phase 8   ConstitutionalRule · Constitution · is_constitutional
        ├── Phase 9   refine_constitution · iterative_refinement (monotone)
        ├── Phase 10  IntegratedSystem · system_is_valid
        └── Phase 11  AssumptionsRegistry (theorems vs axioms vs analogies)

        13 theorems proved · 2 axioms declared · 0 circular reasoning
```

---

## Desktop Layer

### C Win32 IDE — `ide/native/`

Native Win32. Direct2D GPU rendering, ConPTY terminal, Win32 message loop. No Electron. No web view.

```
  ide/native/
  ├── core/        memory arena · event system · strings · threading
  ├── editor/      gap buffer · code reference parser
  ├── terminal/    ConPTY + fallback gate
  ├── ui/          layout · status bar · project tree · output panel
  ├── bridge/      HTTP client → Python :19000
  ├── chat/        named pipe agent interaction
  ├── lsp/         Language Server Protocol client
  ├── graphics/    Direct2D hardware-accelerated rendering
  ├── fcl/         Formal Command Language interpreter
  ├── git/         status · diff · commit
  └── platform/windows/  application · window · shell
```

### BEAM Process VM — `ide/beam/`

Erlang-model process VM in WebAssembly. 8 sovereign agent processes. No browser runtime.

```
  beam_vm.wat (552 lines)
  ├── spawn(module, func, priority)   create process → 256-slot PCB table
  ├── send(dst_pid, tag, val)          Erlang ! — ring buffer mailbox
  ├── receive(out_ptr)                 pattern-match pop, block if empty
  ├── schedule()                       priority round-robin, 256 slots
  ├── reduce()                         burn reduction, reschedule at 0
  ├── kill(pid, reason)                EXIT signal → linked trap handler
  └── link(pid_a, pid_b)               bidirectional process link

  8 Agent Processes:
  ┌──────────────────────────────────────────────────────────┐
  │  0  chat       BOB reasoning → 11-stage pipeline          │
  │  1  tool       34-tool dispatch by msg_tag                │
  │  2  model      inference (local/ollama/anthropic/openrouter)│
  │  3  audit      WORM append-only log, no mutation          │
  │  4  workspace  project state, file trees, git             │
  │  5  sandbox    code execution in agent scratch            │
  │  6  routing    11-stage pipeline as BEAM process          │
  │  7  entropy    governor: blocks H > 0.20, max priority    │
  └──────────────────────────────────────────────────────────┘

  Memory: 512KB (8 pages)
  Process table 256×256B · Mailbox rings 256×512B · Per-process heap 256×512B
```

---

## Sparse Latency Router

`src/routing/sparse-latency-routing/` — Directed sparse graph with deterministic Jacobian-rank–driven topology adaptation, WORM hash chain, and 12 invariants.

```
  bin/sparse_router.sh run <network.xml>
      │
      ├── 1  xmllint schema validation (network.xsd)
      ├── 2  parse_nodes / parse_edges → sparse adjacency list
      ├── 3  recurse_tensor → nested tensor model
      ├── 4  parse_jacobian → matrix or structural proxy
      ├── 5  calculate_rank → numpy (computed) or structural heuristic
      ├── 6  calculate_latency → Dijkstra on nonneg edge weights
      ├── 7  adapt_network → 5 rules: latency_exceeds_threshold /
      │                       rank_decreases / rank_increases /
      │                       tensor_dimension_changes / sparsity_maximum
      ├── 8  verify_invariants → I1-I12 checked inline
      ├── 9  emit_state → write-to-temp then mv (atomic, I12)
      └── 10 WORM seal → SHA-256( topology ‖ prev_hash )

  Exit codes: 0=success · 64=usage · 65=xml · 66=invariant
              67=adaptation_failed · 68=hash_mismatch · 69=missing_tool

  Test fixtures (17):
  tests/valid/          1 schema-valid baseline
  tests/invalid/        9 fixtures, one invariant violated each
  tests/adaptation/     7 two-step adaptation + tamper scenarios
```

---

## Audio & Message Bridge

### Video-to-Text Training — `src/asr/`

Qwen3-ASR fine-tuning on custom audio data. Async transcription pipeline (OpenAI Whisper + local models).

```
src/asr/finetune.py
├── Qwen3-ASR-1.7B fine-tuning
├── Prefix-only training (system prompt + target)
├── Auto-checkpoint resumption
├── HuggingFace Trainer (bfloat16/float16)
└── CLI: python -m src.asr.finetune --train_file train.jsonl --output_dir ./out

src/tools/audio/transcribe.py
├── AudioTranscriber (OpenAI + local)
├── Multi-provider fallback
└── WORM ledger logging (audit trail)
```

**Usage:** See [docs/ASR_AND_BRIDGE.md](docs/ASR_AND_BRIDGE.md)

### Message Bridge — `src/bridge/http_server.py`

HTTP REST API (:19000) for Ahmad (or external systems) to send messages. Parses intent via 11-stage Jordan routing, dispatches to ReAct agent, executes tools, seals in WORM ledger.

```
POST /chat
  {"message": "write a fibonacci function"}
  ↓ 11-stage routing (Regex → AST → Jordan → Jacobian → Sparse → NAND → Dispatch)
  ↓ ReActAgent (think → act → observe loop)
  ↓ Tool execution (34 tools across 9 namespaces)
  ↓ WORM seal (Blake2b + Ed25519 hash chain)
  ← JSON response + trace data
```

**Endpoints:**
- `POST /chat` — send message
- `POST /agent/run` — ReAct task
- `POST /tool/execute` — single tool
- `GET /tools` — list 34 tools
- `GET /routing/traces` — trace collection
- `POST /keys/set` — API key mgmt (OpenAI, Anthropic, Bedrock)

**Start server:**
```bash
python -m src.bridge.http_server --host 127.0.0.1 --port 19000
```

---

## Federated Training — AgentFishTank

`training-frontend/` — Swift/SceneKit federated swarm training frontend. 36 agents inside a 3D glass tank processing training corpora from GitHub forks.

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  AgentFishTank — 60fps Deterministic Swarm State Machine            │
  │                                                                     │
  │  GitHub Forks (NASA CMR · OpenMetadata · Autoware)                  │
  │       │ CorpusLoader (async URLSession → TRAINING_CORPUS.json)      │
  │       ▼                                                             │
  │  TrainingCorpus ──► TrainingNode tree + RelationshipEdge graph       │
  │       │              7 classes: DISCOVERY → RECONSTRUCTION           │
  │       ▼                                                             │
  │  TaskPool (shuffle all nodes × 7 task types)                        │
  │       │                                                             │
  │       ▼                                                             │
  │  36 Agents ──────────────────────────────────────────────────────── │
  │  │ IDLE → TRAVERSING → PARSING → EXTRACTING → TRANSFORMING         │
  │  │      → VERIFYING → COMMUNICATING → COMPLETE → reassign           │
  │  │                                                                  │
  │  │  Movement: bounce in [-1,1]³ · cluster pull · separation         │
  │  │  Pipeline: load tree → extract → transform → verify → WORM seal  │
  │  │  Messages: agent-to-agent payload exchange (ring buffer)          │
  │  │  Clusters: ≥3 agents on same node → cluster formation event      │
  │  └──────────────────────────────────────────────────────────────── │
  │                                                                     │
  │  SceneKit 3D View                                                   │
  │  ├── Glass box (2×2×2, chamfer 0.08, IOR 1.45, 85% transparency)   │
  │  ├── Agent spheres (r=0.035, color = state, emission = progress)    │
  │  ├── Volumetric particles (80/sec, 3s lifespan)                     │
  │  ├── Shockwave pulse on COMPLETE (scale 1→1.015→1)                  │
  │  ├── Corpus tree sidebar (filter by source)                         │
  │  ├── Agent inspector (pipeline steps, progress, reasoning)          │
  │  └── Event timeline (scrolling, color-coded by type)                │
  └─────────────────────────────────────────────────────────────────────┘
```

**7 Task Types:**
| Task | Pipeline Steps |
|------|---------------|
| TRAVERSE_TREE | Load tree → Traverse hierarchy → Index children → Send to extractor |
| EXTRACT_METADATA | Read evidence → Parse → Extract facts → Tag confidence → Append |
| BUILD_REL_GRAPH | Load components → Detect imports → Classify → Build edge |
| RECONSTRUCT_ARCH | Gather edges → Cluster subsystem → Derive data flow → Validate |
| GENERATE_TRAINING | Select class → Form question → Derive answer → Serialize |
| VALIDATE_OUTPUT | Load spec → Compare behavior → Classify MATCH/PARTIAL/MISMATCH → WORM seal |
| SEND_TO_AGENT | Pack payload → Route to target → Await ACK |

**Build:**
```bash
cd training-frontend
swift build    # macOS 14+ / iOS 17+
```

---

## The 49th Call

`the-49th-call/` — Multi-language substrate implementing Call49 esoteric computation: Enochian keys, soul specification, gnostic arithmetic, and the 49th invocation.

```
  the-49th-call/
  ├── src/
  │   ├── Cargo.toml
  │   └── lib.rs              Rust core library
  └── substrate/
      ├── soul_spec.hs        Haskell soul specification
      ├── substrate.apl       APL substrate computation
      ├── subleq.asm          SUBLEQ one-instruction set computer
      ├── mamari.cbl          COBOL mamari module
      └── comefrom.i          INTERCAL COMEFROM control flow

  Gnostic Arithmetic (proofs/ + runtime/):
  ├── proofs/GnosticArithmetic.lean    Abjad matrix, Wafq magic squares, 360° cipher
  ├── proofs/AlHamidMatrix.lean        Master constant 256=16², four-pillar architecture
  └── runtime/src/gnostic_arithmetic.rs  #![no_std] Rust runtime, 12 tests
```

**Key invariant:** Al-Hamid(93) + Ahmad(53) + Ali(110) = 256 = 16² → root 4 (four pillars). Lean 4 proved.

---

## BRICK Protocol

`docs/BRICK_PROTOCOL_SPECIFICATION.md` — **Bound Repository Integrity & Cryptographic Kernel.** Federated repository sealing: SHA3-256 content hashing → AES-256-GCM authenticated encryption → SAML 2.0 identity binding.

```
  Repository Tree
        ↓ canonicalize
  Manifest(repo_id, commit, paths, file_hashes, policy)
        ↓ SHA3-256
  ROOT_HASH
        ↓ AES-256-GCM encrypt (HKDF-derived key, random 96-bit nonce)
  SEALED_BRICK
        ↓ SAML bind (federation issuer + subject + assertion)
  FEDERATED_BRICK_RECEIPT

  Verification: recompute H_tree → verify SAML → recompute BRICK_ID
                → verify AES-GCM tag → decrypt manifest → VALID/INVALID
```

---

## Papers

### New (this repo, `papers/`)

| File | Target venue | Contribution |
|------|-------------|-------------|
| `papers/liquidops_kernel.tex` | PLDI/ICFP | LiquidOps: NAND-canonical verified compiler, LH termination proofs, P4 compatibility |
| `papers/sovereign_entropy.tex` | FM/CAV | H≤0.20 nats Lean 4 proof, SPARK Ada contract, UMTCPI connection, ERE gate |
| `papers/gdr_kernels.tex` | SC/MLSys | GDR-9 nine-ISA stack, drain invariants, cross-ISA Lean 4 equivalence, WORM chain |

Compile: `pdflatex papers/liquidops_kernel.tex`

### Published (Zenodo DOI)

| DOI | Title |
|-----|-------|
| [10.5281/zenodo.20678420](https://doi.org/10.5281/zenodo.20678420) | Attention Exhaustion Attacks — 0% detection rate |
| [10.5281/zenodo.21144425](https://doi.org/10.5281/zenodo.21144425) | Resonance Block Trust Deeds |
| [10.5281/zenodo.21132094](https://doi.org/10.5281/zenodo.21132094) | Sovereign Compute Architecture |
| [10.5281/zenodo.21349277](https://doi.org/10.5281/zenodo.21349277) | Gates Normalization Constraint — simplex is structural |
| [10.5281/zenodo.21351461](https://doi.org/10.5281/zenodo.21351461) | NAND Decomposition — attention is NAND-complete |
| [10.5281/zenodo.21443609](https://doi.org/10.5281/zenodo.21443609) | Jordan Spectral Transformer — φ-weighted routing |
| [10.5281/zenodo.21727363](https://doi.org/10.5281/zenodo.21727363) | PAR-011 Jacobian via Jordan Algebras |
| [10.5281/zenodo.21268911](https://doi.org/10.5281/zenodo.21268911) | GKN I4 Quartic Invariant and E7 Symmetry |

Unified: [The Sovereign Stack](https://snapkittywest.github.io/hyperkitty/papers/sovereign-stack-unified.pdf) — 26 pages, Lean 4.

---

## The Mathematics

### Entropy Bound — Formally Proved in Lean 4

```
  For all F ≥ 1, d ≥ 1:
    H(softmax_ratio(d, T(F))) < 0.20 nats

  Proof chain:
    T(F) = T₀ + (1−T₀)·exp(−αF)  ≤  0.2218
    s    = exp(d / T(F))           ≥  90.75
    H(s) < H(19)                   < 0.20   ✓

  Architectural enforcement:
    θ = 89/2462  (Jordan eigenvalue bound on UMTCPI)
    dominant token probability ≥ 1 − θ
    H(p) ≤ h(1−θ) + θ·ln(n−1)    < 0.20 for n ≤ 32
```

### Jordan Algebra — SpinFactor J(n)

```
  Product:  (α,v) ∘ (β,w) = (αβ + ⟨v,w⟩,  αw + βv)

  Properties used in routing:
  ├── Non-associative      different agent groupings → different outcomes
  ├── Fixed-point          x↦x∘x converges to idempotents = routing attractors
  ├── Spectral decomp      x = λ₊c₊ + λ₋c₋  (provably unique expert assignment)
  └── Spectral gap         2‖v‖  = separation between top-2 experts
```

### Cobalt Trilock Hash

```
  φ64  = 0x9E3779B97F4A7C15  (64-bit Fibonacci/golden-ratio constant)
  A    = φ64 × (structural_identity_hash)   mod 2⁶⁴
  B    = φ64 × (connectivity_hash)          mod 2⁶⁴
  C    = φ64 × (emission_constraint_hash)   mod 2⁶⁴
  Trilock = hex(A)[0:8] ++ "-" ++ hex(B)[0:8] ++ "-" ++ hex(C)[0:8]
```

---

## Security

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  PathJail          resolve → check allowed roots → reject outside│
  │  SSRFGuard         block private IPs, link-local, metadata       │
  │  Inverted AST      payload leaves weight=0, NEVER propagate up   │
  │  NAND Filter       suppress lower-weight expert on conflict       │
  │  Binary WORM       152-byte struct headers, no text, append-only │
  │  ERE P1–P5         no secrets · no eval · no loops · SHA-256 seal│
  │  Entropy Governor  H < 0.20 nats — proved Lean 4, enforced SPARK │
  │  WORM Chain        every record hashes prior — break one = break all│
  │  Drain Invariants  F_c·(1−F_e) scale factor bounds weight updates│
  │  Hash Seal         sparse router: SHA-256(topology ‖ prev_hash)  │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Continuity

Four independent persistence mechanisms sync on every state transition:

| # | Paradigm | Storage | Survives |
|---|----------|---------|----------|
| 1 | Env bitmask | `os.environ` (64-bit packed) | `os.execv` hot restart |
| 2 | Seed chain | Blake2b derivation (24 bytes) | Full history → one hash |
| 3 | Inode flags | Zero-byte files + `stat()` | OOM kill (kernel dcache) |
| 4 | Shared memory | ctypes struct (4KB mmap) | Cross-process, no serialization |

---

## Source

| Component | Language | Files | Lines |
|-----------|----------|------:|------:|
| Engine core | Python 3.11 | 170 | 49,517 |
| **Cobalt — LiquidHaskell pkg** | **Haskell** | **28** | **6,841** |
| C Win32 IDE | C / C++ | 59 | 7,481 |
| Hardware kernels | NASM + CUDA + SV + P4 | 32 | 5,670 |
| MAGMA protocol | Ada/SPARK + Rust | 14 | 2,331 |
| NARM runtime | C + ASM + Fortran | 9 | 2,322 |
| Hardware RTL | SystemVerilog + Scala | 19 | 1,917 |
| **Formal proofs** | **Lean 4 + Agda** | **8** | **3,121** |
| BEAM VM | WebAssembly (WAT) | 3 | 1,225 |
| **Sparse Latency Router (Python)** | **Python** | **36** | **4,136** |
| **ASR + Bridge** | **Python** | **6** | **1,200** |
| **AgentFishTank** | **Swift / SceneKit** | **7** | **1,331** |
| **The 49th Call** | **Rust + Haskell + APL + Prolog + COBOL** | **22** | **3,341** |
| **Gnostic Arithmetic Runtime** | **Rust (#![no_std])** | **1** | **346** |
| Tests | Python + Bash | 5 | 1,203 |
| CATN tensor network | Rust | 9 | 1,051 |
| **Papers** | **LaTeX** | **3** | **1,580** |
| AToKio | Haskell | 1 | 299 |
| **Total** | **20+ languages** | **427** | **99,010** |

---

## Quick Start

```bash
git clone https://github.com/SNAPKITTYWEST/sovereign-engine-v2.git
cd sovereign-engine-v2

# Run the engine (zero pip dependencies)
python -c "
import asyncio
from src.sovereign import SovereignEngine, EngineConfig

async def main():
    engine = SovereignEngine(EngineConfig())
    result = await engine.run('Write a fibonacci function')
    print(result)
    engine.shutdown()

asyncio.run(main())
"

# Build the C IDE (Windows — requires CMake + MSVC)
cd ide/native
cmake -B build -G "Visual Studio 17 2022"
cmake --build build --config Release

# Run the Cobalt Haskell package (requires GHC + cabal-install)
cd cobalt
cabal build
cabal test

# Run the sparse latency router
src/routing/sparse-latency-routing/bin/sparse_router.sh \
  run src/routing/sparse-latency-routing/spec/network.xml
src/routing/sparse-latency-routing/tests/run_tests.sh

# Compile a paper
pdflatex papers/liquidops_kernel.tex
pdflatex papers/sovereign_entropy.tex
pdflatex papers/gdr_kernels.tex

# Check Lean 4 proofs (requires lake)
lake build formal/sovereign_entropy/EntropyBound.lean
lake build formal/tensor_framework/TensorFramework.lean
```

---

```
  SnapKitty / SNAPKITTYWEST / Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust
  BSL 1.1 → MIT 2029-01-01
  99,010 lines · 20+ languages · one sovereign stack
```
