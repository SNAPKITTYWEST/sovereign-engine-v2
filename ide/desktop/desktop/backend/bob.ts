import type { BobChatMessage, BobChatRequest, BobChatResponse, DesktopToolEvent } from '../shared.js';
import { SovereignDesktopAudit } from './audit.js';
import { callConfiguredModel } from './model-client.js';
import type { ModelProviderStore } from './providers.js';
import {
  formatToolResultForModel,
  parseToolCall,
  removeToolCallJson,
  type SovereignToolBroker,
} from './tools.js';

export class BobChatBroker {
  constructor(
    private readonly providers: ModelProviderStore,
    private readonly tools: SovereignToolBroker,
    private readonly audit = new SovereignDesktopAudit(),
  ) {}

  async respond(request: BobChatRequest): Promise<BobChatResponse> {
    const trimmed = request.prompt.trim();
    const result = this.audit.seal(
      'desktop.chat',
      {
        prompt: trimmed,
        toolsEnabled: request.toolsEnabled,
      },
      true,
      'chat request accepted',
    );
    const provider = await this.providers.resolveActive();
    const toolEvents: DesktopToolEvent[] = [];
    let content: string;

    if (provider.providerId === 'local') {
      content = buildBobReply(trimmed, result.verdict.kind, result.lastSeal);
    } else {
      try {
        content = await callConfiguredModel({
          prompt: trimmed,
          history: request.messages,
          provider,
          tools: request.toolsEnabled ? this.tools.list() : [],
        });

        const toolCall = request.toolsEnabled ? parseToolCall(content) : undefined;
        if (toolCall) {
          const toolEvent = await this.tools.execute(toolCall);
          toolEvents.push(toolEvent);
          const cleaned = removeToolCallJson(content);
          const final = await callConfiguredModel({
            prompt: trimmed,
            history: [
              ...request.messages,
              { role: 'bob', content: cleaned || `Calling ${toolCall.name}.`, timestamp: new Date().toISOString() },
              { role: 'tool', content: toolEvent.output, timestamp: new Date().toISOString() },
            ],
            provider,
            tools: this.tools.list(),
            toolResult: formatToolResultForModel(toolCall, toolEvent),
          });
          content = final.trim() || [
            cleaned,
            `Tool ${toolEvent.name} ${toolEvent.ok ? 'passed' : 'failed'}.`,
            toolEvent.output,
          ].filter(Boolean).join('\n\n');
        }
      } catch (error) {
        const reason = error instanceof Error ? error.message : String(error);
        content = [
          buildBobReply(trimmed, result.verdict.kind, result.lastSeal),
          `Provider ${provider.label} unavailable: ${reason}`,
        ].join('\n\n');
      }
    }

    return {
      message: {
        role: 'bob',
        content,
        timestamp: new Date().toISOString(),
        seal: result.lastSeal,
        provider: provider.providerId,
      },
      seal: result.lastSeal,
      verdict: result.verdict.kind,
      provider: provider.providerId,
      toolEvents,
      trace: result.trace,
    };
  }
}

export function buildBobReply(prompt: string, verdict: string, seal: string): string {
  const lower = prompt.toLowerCase();

  if (!prompt) {
    return `BOB local mode. Ask for a file change, a repo check, or a sandbox command. Verdict ${verdict}. Seal ${seal}.`;
  }

  if (lower.includes('test') || lower.includes('verify') || lower.includes('build')) {
    return [
      'BOB plan: run the smallest Sovereign Engine evidence gate that proves the change.',
      'Use python -m pytest for behavior, python -m compileall src tests for syntax, or the routing trace test for bridge evidence.',
      `Verdict ${verdict}. Seal ${seal}.`,
    ].join(' ');
  }

  if (lower.includes('bash') || lower.includes('terminal') || lower.includes('command')) {
    return [
      'BOB terminal is sandboxed. Allowed commands are Python evidence gates, read-only git status/diff, and rg workspace search.',
      'Denied commands are sealed but not executed.',
      `Verdict ${verdict}. Seal ${seal}.`,
    ].join(' ');
  }

  if (lower.includes('file') || lower.includes('editor') || lower.includes('code')) {
    return [
      'BOB editor path: open a file from Explorer, edit in Monaco, save through the preload bridge, then run a governed check.',
      'The renderer has no Node access.',
      `Verdict ${verdict}. Seal ${seal}.`,
    ].join(' ');
  }

  return [
    'BOB received the task in Sovereign Engine desktop mode.',
    'State the target file, bridge check, tool, command, or proof gate and I will keep the action inside the local sandbox.',
    `Verdict ${verdict}. Seal ${seal}.`,
  ].join(' ');
}

export function userChatMessage(content: string): BobChatMessage {
  return {
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
  };
}
