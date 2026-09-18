import { mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { dirname, extname, isAbsolute, relative, resolve } from 'node:path';

import type { DesktopFileEntry, DesktopFileSnapshot, WorkspaceOverview } from '../shared.js';

const IGNORED_ROOTS = new Set([
  '.git',
  '.continuity',
  '.mypy_cache',
  '.pytest_cache',
  '.ruff_cache',
  '__pycache__',
  'node_modules',
  'dist',
  '_site',
]);

const MAX_READ_BYTES = 1_000_000;

export function resolveWorkspacePath(root: string, requestedPath = '.'): string {
  const cleanRequest = requestedPath.trim() || '.';
  const target = resolve(root, cleanRequest);
  const relativePath = relative(root, target);

  if (relativePath && (relativePath.startsWith('..') || isAbsolute(relativePath))) {
    throw new Error(`Path escapes workspace: ${requestedPath}`);
  }

  const firstSegment = normalizeRelativePath(relativePath).split('/').filter(Boolean)[0];
  if (firstSegment && IGNORED_ROOTS.has(firstSegment)) {
    throw new Error(`Path is outside the editor sandbox: ${requestedPath}`);
  }

  return target;
}

export async function getWorkspaceOverview(root: string): Promise<WorkspaceOverview> {
  return {
    root,
    entries: await listWorkspaceEntries(root, '.'),
  };
}

export async function listWorkspaceEntries(root: string, requestedPath = '.'): Promise<ReadonlyArray<DesktopFileEntry>> {
  const target = resolveWorkspacePath(root, requestedPath);
  const entries = await readdir(target, { withFileTypes: true });
  const visible = entries.filter(entry => !IGNORED_ROOTS.has(entry.name));
  const snapshots = await Promise.all(visible.map(async entry => {
    const absolutePath = resolve(target, entry.name);
    const info = await stat(absolutePath);
    const relativePath = normalizeRelativePath(relative(root, absolutePath));
    return {
      name: entry.name,
      relativePath,
      kind: entry.isDirectory() ? 'directory' as const : 'file' as const,
      size: info.size,
    };
  }));

  return snapshots
    .sort((left, right) => {
      if (left.kind !== right.kind) return left.kind === 'directory' ? -1 : 1;
      return left.name.localeCompare(right.name);
    })
    .slice(0, 300);
}

export async function readWorkspaceTextFile(root: string, requestedPath: string): Promise<DesktopFileSnapshot> {
  const target = resolveWorkspacePath(root, requestedPath);
  const info = await stat(target);

  if (!info.isFile()) {
    throw new Error(`Not a file: ${requestedPath}`);
  }
  if (info.size > MAX_READ_BYTES) {
    throw new Error(`File is too large for the editor sandbox: ${requestedPath}`);
  }

  return {
    relativePath: normalizeRelativePath(relative(root, target)),
    content: await readFile(target, 'utf8'),
    language: languageForPath(target),
  };
}

export async function saveWorkspaceTextFile(
  root: string,
  requestedPath: string,
  content: string,
): Promise<DesktopFileSnapshot> {
  const target = resolveWorkspacePath(root, requestedPath);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, content, 'utf8');
  return readWorkspaceTextFile(root, requestedPath);
}

export function normalizeRelativePath(path: string): string {
  return path.replaceAll('\\', '/');
}

export function languageForPath(path: string): string {
  switch (extname(path).toLowerCase()) {
    case '.ts':
    case '.tsx':
      return 'typescript';
    case '.js':
    case '.mjs':
    case '.cjs':
      return 'javascript';
    case '.json':
      return 'json';
    case '.md':
      return 'markdown';
    case '.html':
      return 'html';
    case '.css':
      return 'css';
    case '.yml':
    case '.yaml':
      return 'yaml';
    default:
      return 'plaintext';
  }
}
