import { DesktopCommandBroker } from './sandbox.js';
import { readWorkspaceTextFile } from './workspace.js';
import type { DesktopToolEvent, DesktopToolSummary } from '../shared.js';

export interface ToolCallRequest {
  readonly name: string;
  readonly input: Record<string, unknown>;
}

export const SOVEREIGN_TOOLS: ReadonlyArray<DesktopToolSummary> = [
  {
    name: 'workspace.search',
    description: 'Search the Sovereign Engine repo with ripgrep. Read-only.',
    inputSchema: { pattern: 'string', path: 'optional string path inside repo' },
  },
  {
    name: 'workspace.read_file',
    description: 'Read a text file from inside the Sovereign Engine repo. Read-only.',
    inputSchema: { path: 'string path inside repo' },
  },
  {
    name: 'engine.list_tools',
    description: 'List tools exposed by the Sovereign Engine HTTP bridge. Read-only.',
    inputSchema: {},
  },
  {
    name: 'engine.key_status',
    description: 'Read provider key status from the Sovereign Engine HTTP bridge. Does not return key values.',
    inputSchema: {},
  },
  {
    name: 'engine.routing_stats',
    description: 'Read aggregate routing trace stats from the Sovereign Engine HTTP bridge.',
    inputSchema: {},
  },
  {
    name: 'engine.routing_test',
    description: 'Dry-run a routing decision through the Sovereign Engine HTTP bridge.',
    inputSchema: { text: 'string input to route', intent: 'optional string intent' },
  },
  {
    name: 'engine.chat',
    description: 'Send a chat message to the Sovereign Engine HTTP bridge.',
    inputSchema: { message: 'string' },
  },
  {
    name: 'engine.tool_execute',
    description: 'Execute a registered Sovereign Engine bridge tool only when its risk_class is 0, 1, or 2.',
    inputSchema: { tool: 'string tool id', args: 'optional object arguments' },
  },
  {
    name: 'repo.status',
    description: 'Run git status -sb. Read-only.',
    inputSchema: {},
  },
  {
    name: 'repo.diff_stat',
    description: 'Run git diff --stat. Read-only.',
    inputSchema: {},
  },
  {
    name: 'engine.pytest',
    description: 'Run python -m pytest through the governed command broker.',
    inputSchema: {},
  },
  {
    name: 'engine.compile',
    description: 'Run python -m compileall src tests through the governed command broker.',
    inputSchema: {},
  },
  {
    name: 'engine.routing_trace_test',
    description: 'Run the routing trace endpoint test through the governed command broker.',
    inputSchema: {},
  },
];

const TOOL_NAMES = new Set(SOVEREIGN_TOOLS.map(tool => tool.name));

export class SovereignToolBroker {
  constructor(
    private readonly repoRoot: string,
    private readonly commands: DesktopCommandBroker,
  ) {}

  list(): ReadonlyArray<DesktopToolSummary> {
    return SOVEREIGN_TOOLS;
  }

  async execute(call: ToolCallRequest): Promise<DesktopToolEvent> {
    try {
      if (!TOOL_NAMES.has(call.name)) {
        return { name: call.name, ok: false, output: `Unknown tool: ${call.name}` };
      }

      switch (call.name) {
        case 'workspace.search':
          return this.runCommandTool(call.name, buildSearchCommand(call.input));
        case 'workspace.read_file': {
          const path = requireString(call.input, 'path');
          const file = await readWorkspaceTextFile(this.repoRoot, path);
          return {
            name: call.name,
            ok: true,
            output: truncateToolOutput(`FILE ${file.relativePath}\n\n${file.content}`),
          };
        }
        case 'repo.status':
          return this.runCommandTool(call.name, 'git status -sb');
        case 'repo.diff_stat':
          return this.runCommandTool(call.name, 'git diff --stat');
        case 'engine.pytest':
          return this.runCommandTool(call.name, 'python -m pytest');
        case 'engine.compile':
          return this.runCommandTool(call.name, 'python -m compileall src tests');
        case 'engine.routing_trace_test':
          return this.runCommandTool(call.name, 'python -m pytest tests/test_routing_trace_endpoints.py');
        case 'engine.list_tools':
          return this.bridgeGet(call.name, '/tools');
        case 'engine.key_status':
          return this.bridgeGet(call.name, '/keys/status');
        case 'engine.routing_stats':
          return this.bridgeGet(call.name, '/routing/stats');
        case 'engine.routing_test':
          return this.bridgePost(call.name, '/routing/test', {
            text: requireString(call.input, 'text'),
            intent: typeof call.input.intent === 'string' && call.input.intent.trim()
              ? call.input.intent.trim()
              : 'query',
          });
        case 'engine.chat':
          return this.bridgePost(call.name, '/chat', { message: requireString(call.input, 'message') });
        case 'engine.tool_execute':
          return this.executeBridgeTool(call);
        default:
          return { name: call.name, ok: false, output: `Unhandled tool: ${call.name}` };
      }
    } catch (error) {
      return {
        name: call.name,
        ok: false,
        output: error instanceof Error ? error.message : String(error),
      };
    }
  }

  private async runCommandTool(name: string, command: string): Promise<DesktopToolEvent> {
    const result = await this.commands.run({ command }, () => undefined);
    const output = [
      result.reason ? `reason: ${result.reason}` : '',
      result.stdout,
      result.stderr,
    ].filter(Boolean).join('\n');
    return {
      name,
      ok: result.allowed && result.exitCode === 0,
      output: truncateToolOutput(output || `exit=${result.exitCode}`),
    };
  }

  private async bridgeGet(name: string, path: string): Promise<DesktopToolEvent> {
    const result = await bridgeJson(path);
    return {
      name,
      ok: true,
      output: truncateToolOutput(JSON.stringify(result, null, 2)),
    };
  }

  private async bridgePost(name: string, path: string, body: Record<string, unknown>): Promise<DesktopToolEvent> {
    const result = await bridgeJson(path, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    return {
      name,
      ok: true,
      output: truncateToolOutput(JSON.stringify(result, null, 2)),
    };
  }

  private async executeBridgeTool(call: ToolCallRequest): Promise<DesktopToolEvent> {
    const tool = requireString(call.input, 'tool');
    const args = typeof call.input.args === 'object' && call.input.args !== null
      ? call.input.args as Record<string, unknown>
      : {};
    const catalog = await bridgeJson('/tools') as { tools?: Array<{ id?: string; risk_class?: number }> };
    const found = catalog.tools?.find(item => item.id === tool);

    if (!found) {
      return { name: call.name, ok: false, output: `Bridge tool not found or bridge offline: ${tool}` };
    }
    if (typeof found.risk_class !== 'number' || found.risk_class > 2) {
      return {
        name: call.name,
        ok: false,
        output: `Refused ${tool}: risk_class ${found.risk_class ?? 'unknown'} requires explicit user approval outside model auto-tools.`,
      };
    }

    return this.bridgePost(call.name, '/tool/execute', { tool, args });
  }
}

export function parseToolCall(content: string): ToolCallRequest | undefined {
  const candidates = [
    ...extractJsonCodeBlocks(content),
    content.trim(),
  ];

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate) as unknown;
      const toolCall = typeof parsed === 'object' && parsed !== null && 'tool_call' in parsed
        ? (parsed as { tool_call?: unknown }).tool_call
        : parsed;
      if (typeof toolCall !== 'object' || toolCall === null) continue;
      const record = toolCall as Record<string, unknown>;
      if (typeof record.name !== 'string') continue;
      const input = typeof record.input === 'object' && record.input !== null
        ? record.input as Record<string, unknown>
        : {};
      return { name: record.name, input };
    } catch {
      continue;
    }
  }

  return undefined;
}

export function removeToolCallJson(content: string): string {
  return content
    .replace(/```(?:json)?\s*{[\s\S]*?"tool_call"[\s\S]*?}\s*```/gi, '')
    .replace(/^\s*{[\s\S]*?"tool_call"[\s\S]*?}\s*$/i, '')
    .trim();
}

export function formatToolResultForModel(call: ToolCallRequest, event: DesktopToolEvent): string {
  return JSON.stringify({
    tool_result: {
      name: call.name,
      ok: event.ok,
      output: event.output,
    },
  }, null, 2);
}

function buildSearchCommand(input: Record<string, unknown>): string {
  const pattern = requireString(input, 'pattern');
  const path = typeof input.path === 'string' && input.path.trim() ? input.path.trim() : '.';
  return `rg ${quoteArg(pattern)} ${quoteArg(path)}`;
}

function requireString(input: Record<string, unknown>, key: string): string {
  const value = input[key];
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`Tool input field "${key}" must be a non-empty string.`);
  }
  return value.trim();
}

function quoteArg(value: string): string {
  return `"${value.replaceAll('\\', '\\\\').replaceAll('"', '\\"')}"`;
}

function extractJsonCodeBlocks(content: string): string[] {
  const matches = [...content.matchAll(/```(?:json)?\s*([\s\S]*?)```/gi)];
  return matches.map(match => match[1]?.trim() ?? '').filter(Boolean);
}

function truncateToolOutput(output: string): string {
  const limit = 12_000;
  if (output.length <= limit) return output;
  return `${output.slice(0, limit)}\n\n[tool output truncated at ${limit} chars]`;
}

async function bridgeJson(path: string, init: RequestInit = {}): Promise<unknown> {
  const baseUrl = process.env.SOVEREIGN_ENGINE_BRIDGE_URL ?? 'http://127.0.0.1:19000';
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...init.headers,
    },
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Sovereign Engine bridge ${path} failed ${response.status}: ${text.slice(0, 600)}`);
  }
  return text ? JSON.parse(text) : {};
}
