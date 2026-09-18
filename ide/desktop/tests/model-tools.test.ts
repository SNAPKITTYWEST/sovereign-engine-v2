import { buildSystemPrompt } from '../desktop/backend/model-client.js';
import {
  formatToolResultForModel,
  parseToolCall,
  removeToolCallJson,
  SOVEREIGN_TOOLS,
} from '../desktop/backend/tools.js';

test('model system prompt exposes only the allowlisted sovereign tools', () => {
  const prompt = buildSystemPrompt(SOVEREIGN_TOOLS);

  expect(prompt).toContain('Never ask the user for secret keys');
  expect(prompt).toContain('workspace.search');
  expect(prompt).toContain('engine.routing_trace_test');
  expect(prompt).toContain('engine.list_tools');
  expect(prompt).not.toContain('git push');
  expect(prompt).not.toContain('shell');
});

test('model tool call parser accepts raw and fenced JSON requests', () => {
  expect(parseToolCall('{"name":"repo.status","input":{}}')).toEqual({
    name: 'repo.status',
    input: {},
  });

  expect(parseToolCall([
    '```json',
    '{"tool_call":{"name":"workspace.read_file","input":{"path":"README.md"}}}',
    '```',
  ].join('\n'))).toEqual({
    name: 'workspace.read_file',
    input: { path: 'README.md' },
  });
});

test('tool call cleanup removes JSON control payloads from chat-visible text', () => {
  const fenced = [
    '```json',
    '{"tool_call":{"name":"repo.status","input":{}}}',
    '```',
  ].join('\n');

  expect(removeToolCallJson(fenced)).toBe('');
  expect(removeToolCallJson(`Need context.\n\n${fenced}`)).toBe('Need context.');
});

test('tool result formatter returns a structured model followup payload', () => {
  expect(formatToolResultForModel(
    { name: 'repo.status', input: {} },
    { name: 'repo.status', ok: true, output: '## main' },
  )).toContain('"tool_result"');
});
