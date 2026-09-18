import { resolve } from 'node:path';

import { buildBobReply } from '../desktop/backend/bob.js';
import { classifyCommand, parseCommandLine } from '../desktop/backend/sandbox.js';
import { languageForPath, resolveWorkspacePath } from '../desktop/backend/workspace.js';

const repoRoot = resolve(process.cwd());

test('desktop sandbox allows approved evidence commands', () => {
  expect(classifyCommand('python -m pytest').allowed).toBe(true);
  expect(classifyCommand('python -m pytest tests').allowed).toBe(true);
  expect(classifyCommand('python -m compileall src tests').allowed).toBe(true);
  expect(classifyCommand('git status -sb').allowed).toBe(true);
  expect(classifyCommand('git diff --check').allowed).toBe(true);
  expect(classifyCommand('rg RoutingPipeline src').allowed).toBe(true);
});

test('desktop sandbox denies uncontrolled shell behavior', () => {
  expect(classifyCommand('npm install left-pad').allowed).toBe(false);
  expect(classifyCommand('git reset --hard').allowed).toBe(false);
  expect(classifyCommand('python -m pytest && git push').allowed).toBe(false);
  expect(classifyCommand('rm -rf dist').allowed).toBe(false);
});

test('desktop command parser preserves quoted arguments', () => {
  expect(parseCommandLine('rg "public reasoning" tests')).toEqual([
    'rg',
    'public reasoning',
    'tests',
  ]);
});

test('desktop workspace resolver is confined to the repo sandbox', () => {
  expect(resolveWorkspacePath(repoRoot, 'desktop/renderer.ts')).toBe(resolve(repoRoot, 'desktop/renderer.ts'));
  expect(() => resolveWorkspacePath(repoRoot, '../outside.txt')).toThrow('Path escapes workspace');
  expect(() => resolveWorkspacePath(repoRoot, 'node_modules/electron/package.json')).toThrow('editor sandbox');
});

test('desktop language detection maps editor file types', () => {
  expect(languageForPath('desktop/renderer.ts')).toBe('typescript');
  expect(languageForPath('package.json')).toBe('json');
  expect(languageForPath('README.md')).toBe('markdown');
});

test('BOB desktop reply is deterministic and sealed', () => {
  const reply = buildBobReply('run tests and verify', 'ALLOW', 'seal-123');

  expect(reply).toContain('python -m pytest');
  expect(reply).toContain('python -m compileall');
  expect(reply).toContain('Verdict ALLOW');
  expect(reply).toContain('seal-123');
});
