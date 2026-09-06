import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';

import type {
  DesktopCommandChunk,
  DesktopCommandRequest,
  DesktopCommandResult,
} from '../shared.js';
import { SovereignDesktopAudit } from './audit.js';

export interface CommandPolicyDecision {
  readonly allowed: boolean;
  readonly reason: string;
  readonly executable?: string;
  readonly args?: ReadonlyArray<string>;
}

const GIT_COMMANDS = new Set([
  'status -sb',
  'status --short',
  'diff --stat',
  'diff --check',
]);

export class DesktopCommandBroker {
  constructor(
    private readonly repoRoot: string,
    private readonly audit = new SovereignDesktopAudit(),
  ) {}

  async run(
    request: DesktopCommandRequest,
    onChunk: (chunk: DesktopCommandChunk) => void,
  ): Promise<DesktopCommandResult> {
    const runId = randomUUID();
    const command = request.command.trim();
    const decision = classifyCommand(command);
    const auditResult = this.audit.seal(
      'desktop.sandbox.terminal',
      {
        command,
        policy: decision.reason,
      },
      decision.allowed,
      decision.reason,
    );
    const trace = auditResult.trace;

    if (!decision.allowed || auditResult.verdict.kind !== 'ALLOW') {
      const reason = auditResult.verdict.reason;
      onChunk({ runId, stream: 'system', text: `DENIED: ${reason}\n` });
      return {
        runId,
        command,
        allowed: false,
        exitCode: null,
        signal: null,
        stdout: '',
        stderr: '',
        reason,
        seal: auditResult.lastSeal,
        trace,
      };
    }

    onChunk({ runId, stream: 'system', text: `ALLOW: ${decision.reason}\n$ ${command}\n` });
    const spawned = await spawnAllowedCommand(
      runId,
      this.repoRoot,
      decision.executable ?? '',
      decision.args ?? [],
      onChunk,
    );

    return {
      ...spawned,
      command,
      allowed: true,
      reason: decision.reason,
      seal: auditResult.lastSeal,
      trace,
    };
  }
}

export function classifyCommand(command: string): CommandPolicyDecision {
  if (!command) return { allowed: false, reason: 'empty command' };
  if (/[|;&<>]/.test(command)) {
    return { allowed: false, reason: 'shell control operators are not allowed in the sandbox' };
  }

  const tokens = parseCommandLine(command);
  if (tokens.length === 0) return { allowed: false, reason: 'empty command' };

  const [program, ...args] = tokens;
  const normalizedProgram = program.toLowerCase();

  if (normalizedProgram === 'python' || normalizedProgram === 'python3' || normalizedProgram === 'py') {
    return classifyPython(normalizedProgram, args);
  }

  if (normalizedProgram === 'git') {
    const key = args.join(' ');
    if (GIT_COMMANDS.has(key)) {
      return {
        allowed: true,
        reason: `approved git inspection: ${key}`,
        executable: executableForPlatform('git'),
        args,
      };
    }
    return { allowed: false, reason: 'only read-only git status/diff commands are allowed' };
  }

  if (normalizedProgram === 'rg') {
    if (args.length > 0 && args.length <= 3 && args.every(arg => !arg.startsWith('-'))) {
      return {
        allowed: true,
        reason: 'approved ripgrep workspace search',
        executable: executableForPlatform('rg'),
        args,
      };
    }
    return { allowed: false, reason: 'rg sandbox accepts a pattern and up to two paths, without flags' };
  }

  return { allowed: false, reason: `command is not in the Sovereign Engine desktop allowlist: ${program}` };
}

export function parseCommandLine(command: string): string[] {
  const tokens: string[] = [];
  let current = '';
  let quote: '"' | "'" | null = null;
  let escaping = false;

  for (const char of command) {
    if (escaping) {
      current += char;
      escaping = false;
      continue;
    }

    if (char === '\\') {
      escaping = true;
      continue;
    }

    if (quote) {
      if (char === quote) quote = null;
      else current += char;
      continue;
    }

    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }

    if (/\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = '';
      }
      continue;
    }

    current += char;
  }

  if (quote) return [];
  if (escaping) current += '\\';
  if (current) tokens.push(current);
  return tokens;
}

function classifyPython(program: string, args: string[]): CommandPolicyDecision {
  if (args.length === 1 && args[0] === '--version') {
    return {
      allowed: true,
      reason: 'approved Python version check',
      executable: executableForPlatform(program),
      args,
    };
  }

  const key = args.join(' ');
  const approved = new Set([
    '-m pytest',
    '-m pytest tests',
    '-m pytest tests/test_routing_trace_endpoints.py',
    '-m pytest tests/stress_test_no_drift.py',
    '-m compileall src tests',
  ]);

  if (approved.has(key)) {
    return {
      allowed: true,
      reason: `approved Sovereign Engine Python gate: ${key}`,
      executable: executableForPlatform(program),
      args,
    };
  }

  return { allowed: false, reason: 'only approved Python test, compile, and version gates are allowed' };
}

function executableForPlatform(program: string): string {
  if (process.platform === 'win32' && program === 'py') return 'py.exe';
  return program;
}

function spawnAllowedCommand(
  runId: string,
  repoRoot: string,
  executable: string,
  args: ReadonlyArray<string>,
  onChunk: (chunk: DesktopCommandChunk) => void,
): Promise<Omit<DesktopCommandResult, 'command' | 'allowed' | 'trace'>> {
  return new Promise(resolve => {
    let stdout = '';
    let stderr = '';
    const child = spawn(executable, [...args], {
      cwd: repoRoot,
      env: { ...process.env, FORCE_COLOR: '0' },
      shell: false,
      windowsHide: true,
    });

    child.stdout?.on('data', chunk => {
      const text = chunk.toString();
      stdout += text;
      onChunk({ runId, stream: 'stdout', text });
    });

    child.stderr?.on('data', chunk => {
      const text = chunk.toString();
      stderr += text;
      onChunk({ runId, stream: 'stderr', text });
    });

    child.on('error', error => {
      const text = `${error.message}\n`;
      stderr += text;
      onChunk({ runId, stream: 'stderr', text });
      resolve({
        runId,
        exitCode: 1,
        signal: null,
        stdout,
        stderr,
        reason: error.message,
      });
    });

    child.on('close', (exitCode, signal) => {
      onChunk({ runId, stream: 'system', text: `process exited with ${exitCode ?? signal}\n` });
      resolve({
        runId,
        exitCode,
        signal,
        stdout,
        stderr,
      });
    });
  });
}
