/**
 * magma_index.ts — MAGMA bindings entry point
 *
 * Exposes the full binding surface connecting:
 *   sovereign-engine-v2  ←→  MAGMA protocol  ←→  magmad  ←→  Ada core
 */

export * from './magma_bindings'

// Re-export key protocol constants
export const MAGMA_VERBS = ['SEAL','FLUX','FORGE','ECHO','VAULT','QUERY','BIND','PULSE','ANCHOR','SHADOW','INVOKE','NULLIFY'] as const
export const MAGMA_AGENTS = ['CIPHER','ORACLE','SENTINEL','MNEMEX','FORGE','NOVA','HERALD','FLUX','NEXUS'] as const
export const MAGMAD_URL = process.env.MAGMAD_URL ?? 'http://localhost:3000'

/** Check if magmad is reachable */
export async function magmadHealth(): Promise<{ ok: boolean; version?: string }> {
  try {
    const r = await fetch(`${MAGMAD_URL}/api/v1/health`, { signal: AbortSignal.timeout(2000) })
    const j = await r.json() as { ok: boolean; version: string }
    return j
  } catch {
    return { ok: false }
  }
}

/** Send a MAGMA instruction to magmad orchestrator, returns SSE text */
export async function dispatch(instr: import('./magma_bindings').MagmaInstruction): Promise<string> {
  const r = await fetch(`${MAGMAD_URL}/api/v1/orchestrate`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      session_id: instr.id,
      action:     instr.action,
      intent:     `${instr.verb}:${instr.agent}`,
      code:       JSON.stringify(instr.payload),
      trace_ops:  instr.modifiers,
    }),
  })
  return r.text()
}
