/**
 * magma_bindings.ts — TypeScript bindings connecting sovereign-engine-v2
 * to the MAGMA protocol (collectivekitty/lib/magma).
 *
 * Bridges:
 *   1. magma_666.adb CoreState transitions → §MAGMA protocol verbs
 *   2. magma-safety SafetyCertificate      → §ANCHOR:MNEMEX:WORM
 *   3. ERRANT linear-type verification     → §SEAL:CIPHER:SIGN
 *   4. Q-Regex match_bit                   → §FLUX:SENTINEL:PULSE
 *   5. BURT-IMMA entropy output            → §VAULT:CIPHER:STORE
 *
 * MAGMA verb mapping (from schema.ts):
 *   SEAL    — cryptographic seal  → CIPHER  (clearance 5)
 *   ANCHOR  — WORM ledger entry   → MNEMEX  (clearance 5)
 *   FORGE   — build artifact      → FORGE   (clearance 4)
 *   FLUX    — FSM transition      → FLUX    (clearance 3)
 *   VAULT   — encrypted storage   → CIPHER  (clearance 5)
 *   PULSE   — heartbeat/probe     → any     (clearance 1+)
 *   QUERY   — knowledge retrieval → ORACLE  (clearance 4)
 *
 * §INSTRUCTION syntax:
 *   §VERB:AGENT:ACTION{...payload}
 *   ~MODIFIER §VERB:AGENT:ACTION{}
 */

import { createHash } from 'crypto'

// ── MAGMA types (mirrored from schema.ts) ─────────────────────────────────────

export type MagmaVerb =
  | 'SEAL' | 'FLUX' | 'FORGE' | 'ECHO' | 'VAULT'
  | 'QUERY' | 'BIND' | 'PULSE' | 'ANCHOR' | 'SHADOW'
  | 'INVOKE' | 'NULLIFY'

export type MagmaModifier = '~ASYNC' | '~SIGNED' | '~HIDDEN' | '~CHAIN' | '~URGENT'

export type AgentKey =
  | 'CIPHER' | 'ORACLE' | 'SENTINEL' | 'MNEMEX'
  | 'FORGE' | 'NOVA' | 'HERALD' | 'FLUX' | 'NEXUS'

export interface MagmaInstruction {
  verb:      MagmaVerb
  agent:     AgentKey
  action:    string
  payload:   Record<string, unknown>
  modifiers: MagmaModifier[]
  id:        string
  timestamp: number
  hash?:     string
}

// ── Instruction builder ───────────────────────────────────────────────────────

export function buildInstruction(
  verb:      MagmaVerb,
  agent:     AgentKey,
  action:    string,
  payload:   Record<string, unknown> = {},
  modifiers: MagmaModifier[] = [],
): MagmaInstruction {
  const ts   = Date.now()
  const raw  = `${verb}:${agent}:${action}:${JSON.stringify(payload)}:${ts}`
  const hash = createHash('sha256').update(raw).digest('hex')
  return { verb, agent, action, payload, modifiers, id: hash.slice(0, 16), timestamp: ts, hash }
}

export function instruction(raw: string): string {
  return `§${raw}`
}

// ── CoreState transition → MAGMA verb ─────────────────────────────────────────

export type AdaCoreTransition = 'Clear' | 'Pulse' | 'Latch' | 'Persist' | 'Resume'

const CORE_TO_MAGMA: Record<AdaCoreTransition, { verb: MagmaVerb; agent: AgentKey; action: string }> = {
  Clear:   { verb: 'NULLIFY', agent: 'SENTINEL', action: 'RESET_CORE'   },
  Pulse:   { verb: 'FLUX',    agent: 'FLUX',     action: 'PULSE_MATRIX' },
  Latch:   { verb: 'BIND',    agent: 'CIPHER',   action: 'LATCH_STATE'  },
  Persist: { verb: 'ANCHOR',  agent: 'MNEMEX',   action: 'WORM_PERSIST' },
  Resume:  { verb: 'FORGE',   agent: 'FORGE',    action: 'RESUME_CORE'  },
}

/**
 * Convert a magma_666.adb Core_State transition into a MAGMA protocol instruction.
 * Example: coreTransitionToInstruction('Persist', { sequence: 42, valid: true })
 *   → §ANCHOR:MNEMEX:WORM_PERSIST{ sequence: 42, valid: true }
 */
export function coreTransitionToInstruction(
  transition: AdaCoreTransition,
  corePayload: Record<string, unknown> = {},
): MagmaInstruction {
  const { verb, agent, action } = CORE_TO_MAGMA[transition]
  return buildInstruction(verb, agent, action, corePayload)
}

// ── Safety certificate → §ANCHOR ─────────────────────────────────────────────

export interface SafetyCertificateBinding {
  version:  number
  digest:   string   // hex SHA-256
  margins:  number[]
}

/**
 * Bind a magma-safety SafetyCertificate to the WORM ledger via §ANCHOR.
 * Called after Rust check_safety() succeeds.
 *
 * §ANCHOR:MNEMEX:SAFETY_CERT{ version, digest, margins, ts }
 */
export function anchorSafetyCertificate(cert: SafetyCertificateBinding): MagmaInstruction {
  return buildInstruction(
    'ANCHOR', 'MNEMEX', 'SAFETY_CERT',
    { ...cert, ts: Date.now() },
    ['~SIGNED'],
  )
}

// ── Q-Regex match_bit → §FLUX ─────────────────────────────────────────────────

/**
 * Bind a Q-Regex match event to the FLUX verb (FSM transition).
 * match_bit = 1 → §FLUX:SENTINEL:RESONANCE_MATCH{ admissible: true }
 * match_bit = 0 → §FLUX:SENTINEL:RESONANCE_MISMATCH{ admissible: false }
 */
export function fluxQRegexMatch(matchBit: 0 | 1, deltaOmega: number): MagmaInstruction {
  const admissible = matchBit === 1
  return buildInstruction(
    'FLUX', 'SENTINEL',
    admissible ? 'RESONANCE_MATCH' : 'RESONANCE_MISMATCH',
    { admissible, delta_omega: deltaOmega, ts: Date.now() },
    admissible ? ['~CHAIN'] : [],
  )
}

// ── BURT-IMMA entropy → §VAULT ────────────────────────────────────────────────

/**
 * Vault a BURT-IMMA hidden-state entropy sample under CIPHER.
 * §VAULT:CIPHER:ENTROPY_STORE{ h_norm, entropy_bound, ts }
 */
export function vaultBurtImmaEntropy(hNorm: number, entropyBound: number): MagmaInstruction {
  return buildInstruction(
    'VAULT', 'CIPHER', 'ENTROPY_STORE',
    { h_norm: hNorm, entropy_bound: entropyBound, within_bound: hNorm <= entropyBound },
    ['~SIGNED', '~HIDDEN'],
  )
}

// ── Drain pipeline invariants → §SEAL ────────────────────────────────────────

/**
 * Seal a drain pipeline result through CIPHER.
 * §SEAL:CIPHER:DRAIN_PROOF{ tensor_count, complexity, entropy, retained }
 */
export function sealDrainInvariants(params: {
  tensorCount:   number
  totalComplexity: number
  totalEntropy:  number
  originalCount: number
}): MagmaInstruction {
  const retained = params.tensorCount / Math.max(params.originalCount, 1)
  return buildInstruction(
    'SEAL', 'CIPHER', 'DRAIN_PROOF',
    { ...params, retained_fraction: retained },
    ['~SIGNED'],
  )
}

// ── Full pipeline: Core → Protocol → WORM ────────────────────────────────────

/**
 * Execute the full magma_666.adb → MAGMA protocol → WORM pipeline.
 *
 * Sequence:
 *   1. M.Pulse(Core)   → §FLUX:FLUX:PULSE_MATRIX
 *   2. M.Latch(Core)   → §BIND:CIPHER:LATCH_STATE
 *   3. M.Persist(Core) → §ANCHOR:MNEMEX:WORM_PERSIST
 *   4. M.Verify(Core)  → §SEAL:CIPHER:SIGN
 *
 * Returns the ANCHOR instruction (the WORM commitment).
 */
export function executeMagmaPipeline(coreSeq: number, coreValid: boolean): {
  pulse:   MagmaInstruction
  latch:   MagmaInstruction
  persist: MagmaInstruction
  seal:    MagmaInstruction
} {
  const common = { sequence: coreSeq, valid: coreValid, ts: Date.now() }
  return {
    pulse:   coreTransitionToInstruction('Pulse',   common),
    latch:   coreTransitionToInstruction('Latch',   common),
    persist: coreTransitionToInstruction('Persist', common),
    seal:    buildInstruction('SEAL', 'CIPHER', 'CORE_VERIFY', { ...common, verified: coreValid }, ['~SIGNED']),
  }
}

// ── MagmaI algebra ────────────────────────────────────────────────────────────

/** MagmaI.I(X) = NOT X (16-bit) — mirrors Ada imaginary function */
export const imaginary = (x: number) => (~x) & 0xFFFF

/** MagmaI.Fold_I(X,Y) = I(X) XOR I(Y) */
export const foldI = (x: number, y: number) => imaginary(x) ^ imaginary(y)

/** MagmaI.Ectot(X) = Fold_I(X, I(X)) — always 0xFFFF */
export const ectot = (x: number) => foldI(x, imaginary(x))
