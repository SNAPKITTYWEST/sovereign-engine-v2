import { createHash } from 'node:crypto';

export interface DesktopTraceEvent {
  readonly phase: string;
  readonly summary: string;
}

export interface DesktopAuditResult {
  readonly lastSeal: string;
  readonly verdict: {
    readonly kind: 'ALLOW' | 'DENY';
    readonly reason: string;
  };
  readonly trace: ReadonlyArray<DesktopTraceEvent>;
}

export class SovereignDesktopAudit {
  private tick = 0;
  private previousSeal = 'sovereign-engine-desktop-genesis';

  seal(
    action: string,
    payload: Record<string, unknown>,
    allowed: boolean,
    reason: string,
  ): DesktopAuditResult {
    const tick = ++this.tick;
    const timestamp = new Date().toISOString();
    const material = JSON.stringify({
      tick,
      timestamp,
      previousSeal: this.previousSeal,
      action,
      payload,
      allowed,
      reason,
    });
    const lastSeal = createHash('sha256').update(material).digest('hex');
    this.previousSeal = lastSeal;

    return {
      lastSeal,
      verdict: {
        kind: allowed ? 'ALLOW' : 'DENY',
        reason,
      },
      trace: [
        { phase: 'RECEIVED', summary: `Desktop action ${action} accepted for local inspection.` },
        { phase: 'POLICY_CHECK', summary: `Policy returned ${allowed ? 'ALLOW' : 'DENY'}: ${reason}.` },
        {
          phase: 'ENGINE_CONTEXT',
          summary: 'Workspace is Sovereign Engine v2; renderer remains sandboxed behind Electron preload.',
        },
        { phase: 'SEAL', summary: `SHA-256 desktop seal ${lastSeal.slice(0, 16)}...` },
        { phase: 'COMPLETE', summary: allowed ? 'Action completed inside local boundary.' : 'Action blocked locally.' },
      ],
    };
  }
}
