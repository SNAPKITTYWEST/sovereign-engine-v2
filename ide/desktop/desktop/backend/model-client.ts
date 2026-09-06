import type { BobChatMessage, DesktopToolSummary, ModelProviderId } from '../shared.js';
import type { ResolvedModelProvider } from './providers.js';

export interface ModelChatInput {
  readonly prompt: string;
  readonly history: ReadonlyArray<BobChatMessage>;
  readonly provider: ResolvedModelProvider;
  readonly tools: ReadonlyArray<DesktopToolSummary>;
  readonly toolResult?: string;
}

const REQUEST_TIMEOUT_MS = 90_000;

export async function callConfiguredModel(input: ModelChatInput): Promise<string> {
  switch (input.provider.providerId) {
    case 'ollama':
      return callOllama(input);
    case 'anthropic':
      return callAnthropic(input);
    case 'openrouter':
    case 'opencode':
    case 'llama':
    case 'openai-compatible':
      return callOpenAICompatible(input);
    case 'local':
      throw new Error('Local provider uses deterministic BOB fallback.');
  }
}

export function requiresApiKey(providerId: ModelProviderId): boolean {
  return providerId === 'anthropic' || providerId === 'openrouter';
}

export function buildSystemPrompt(tools: ReadonlyArray<DesktopToolSummary>): string {
  return [
    'You are BOB inside the local Sovereign Engine Desktop IDE.',
    'Be direct and operational. Do not claim you ran a tool unless a tool result is provided.',
    'Never ask the user for secret keys in chat. Keys are managed only through the IDE provider settings.',
    'Prefer Sovereign Engine bridge tools for engine state, routing, key status, and registered tool inventory.',
    'You may request one tool call when useful. To call a tool, reply with only JSON in this shape:',
    '{"tool_call":{"name":"workspace.search","input":{"pattern":"RoutingPipeline","path":"src"}}}',
    'Available tools:',
    JSON.stringify(tools, null, 2),
  ].join('\n');
}

function buildMessages(input: ModelChatInput): Array<{ role: 'system' | 'user' | 'assistant'; content: string }> {
  const messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }> = [
    { role: 'system', content: buildSystemPrompt(input.tools) },
  ];

  for (const message of input.history.slice(-8)) {
    if (message.role === 'tool') continue;
    messages.push({
      role: message.role === 'bob' ? 'assistant' : 'user',
      content: message.content,
    });
  }

  if (input.toolResult) {
    messages.push({
      role: 'user',
      content: [
        'Tool result returned to the model.',
        input.toolResult,
        'Now answer the original user request using this result.',
      ].join('\n\n'),
    });
  } else {
    messages.push({ role: 'user', content: input.prompt });
  }

  return messages;
}

async function callOllama(input: ModelChatInput): Promise<string> {
  const response = await postJson(`${input.provider.baseUrl}/api/chat`, {
    model: input.provider.model,
    stream: false,
    messages: buildMessages(input).map(message => ({
      role: message.role,
      content: message.content,
    })),
  });

  const content = responseJson(response, ['message', 'content']);
  if (content) return content;
  throw new Error('Ollama response did not include message.content');
}

async function callAnthropic(input: ModelChatInput): Promise<string> {
  if (!input.provider.apiKey) {
    throw new Error('Anthropic API key is not configured.');
  }

  const messages = buildMessages(input);
  const system = messages.find(message => message.role === 'system')?.content ?? buildSystemPrompt(input.tools);
  const conversational = messages.filter(message => message.role !== 'system');
  const response = await postJson(`${input.provider.baseUrl}/v1/messages`, {
    model: input.provider.model,
    max_tokens: 4096,
    temperature: 0.2,
    system,
    messages: conversational.map(message => ({
      role: message.role === 'assistant' ? 'assistant' : 'user',
      content: message.content,
    })),
  }, {
    'x-api-key': input.provider.apiKey,
    'anthropic-version': '2023-06-01',
  });

  const blocks = responseValue(response, ['content']);
  if (Array.isArray(blocks)) {
    const text = blocks
      .map(block => typeof block?.text === 'string' ? block.text : '')
      .filter(Boolean)
      .join('\n');
    if (text) return text;
  }

  throw new Error('Anthropic response did not include text content');
}

async function callOpenAICompatible(input: ModelChatInput): Promise<string> {
  if (requiresApiKey(input.provider.providerId) && !input.provider.apiKey) {
    throw new Error(`${input.provider.label} API key is not configured.`);
  }

  const headers: Record<string, string> = {};
  if (input.provider.apiKey) headers.Authorization = `Bearer ${input.provider.apiKey}`;
  if (input.provider.providerId === 'openrouter') {
    headers['HTTP-Referer'] = 'https://local.sovereign-engine.desktop';
    headers['X-Title'] = 'Sovereign Engine Desktop IDE';
  }

  const response = await postJson(`${input.provider.baseUrl}/chat/completions`, {
    model: input.provider.model,
    temperature: 0.2,
    messages: buildMessages(input),
  }, headers);

  const content = responseJson(response, ['choices', '0', 'message', 'content']);
  if (content) return content;
  throw new Error(`${input.provider.label} response did not include choices[0].message.content`);
}

async function postJson(
  url: string,
  body: unknown,
  headers: Record<string, string> = {},
): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const text = await response.text();
    if (!response.ok) {
      throw new Error(`Model request failed ${response.status}: ${text.slice(0, 600)}`);
    }
    return text ? JSON.parse(text) : {};
  } finally {
    clearTimeout(timer);
  }
}

function responseJson(value: unknown, path: ReadonlyArray<string>): string | undefined {
  const found = responseValue(value, path);
  return typeof found === 'string' ? found : undefined;
}

function responseValue(value: unknown, path: ReadonlyArray<string>): unknown {
  let current: unknown = value;
  for (const segment of path) {
    if (Array.isArray(current) && /^\d+$/.test(segment)) {
      current = current[Number(segment)];
      continue;
    }
    if (typeof current !== 'object' || current === null || !(segment in current)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return current;
}
