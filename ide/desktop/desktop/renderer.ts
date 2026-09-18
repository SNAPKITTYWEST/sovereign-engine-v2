import { createIcons, icons } from 'lucide';
import * as monaco from 'monaco-editor';

import cssWorker from 'monaco-editor/language/css/css.worker?worker';
import htmlWorker from 'monaco-editor/language/html/html.worker?worker';
import jsonWorker from 'monaco-editor/language/json/json.worker?worker';
import tsWorker from 'monaco-editor/language/typescript/ts.worker?worker';
import editorWorker from 'monaco-editor/editor/editor.worker?worker';

import './styles.css';
import type {
  BobChatMessage,
  DesktopCommandChunk,
  DesktopFileEntry,
  DesktopToolEvent,
  DesktopToolSummary,
  ModelProviderId,
  ModelProviderSummary,
  ModelProviderUpdate,
  ShadowDesktopApi,
} from './shared.js';

declare global {
  interface Window {
    readonly shadowDesktop?: ShadowDesktopApi;
  }

  interface WindowOrWorkerGlobalScope {
    MonacoEnvironment?: monaco.Environment;
  }
}

self.MonacoEnvironment = {
  getWorker(_workerId: string, label: string): Worker {
    if (label === 'json') return new jsonWorker();
    if (label === 'css' || label === 'scss' || label === 'less') return new cssWorker();
    if (label === 'html' || label === 'handlebars' || label === 'razor') return new htmlWorker();
    if (label === 'typescript' || label === 'javascript') return new tsWorker();
    return new editorWorker();
  },
};

const api = window.shadowDesktop;
const expandedDirectories = new Set<string>(['.']);
const directoryCache = new Map<string, ReadonlyArray<DesktopFileEntry>>();
const chatMessages: BobChatMessage[] = [];
const modelProviderIds: ReadonlyArray<ModelProviderId> = [
  'local',
  'ollama',
  'anthropic',
  'openrouter',
  'opencode',
  'llama',
  'openai-compatible',
];

let currentFilePath = 'README.md';
let editor: monaco.editor.IStandaloneCodeEditor;
let commandRunning = false;
let modelProviders: ReadonlyArray<ModelProviderSummary> = [];
let sovereignTools: ReadonlyArray<DesktopToolSummary> = [];

function byId<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing DOM node: ${id}`);
  return node as T;
}

const nodes = {
  rootPath: byId<HTMLSpanElement>('rootPath'),
  fileTree: byId<HTMLDivElement>('fileTree'),
  editorHost: byId<HTMLDivElement>('editorHost'),
  fileName: byId<HTMLSpanElement>('fileName'),
  fileMeta: byId<HTMLSpanElement>('fileMeta'),
  saveButton: byId<HTMLButtonElement>('saveButton'),
  refreshButton: byId<HTMLButtonElement>('refreshButton'),
  status: byId<HTMLDivElement>('status'),
  commandInput: byId<HTMLInputElement>('commandInput'),
  runButton: byId<HTMLButtonElement>('runButton'),
  terminal: byId<HTMLPreElement>('terminal'),
  trace: byId<HTMLDivElement>('trace'),
  quickCommands: byId<HTMLDivElement>('quickCommands'),
  chatLog: byId<HTMLDivElement>('chatLog'),
  chatInput: byId<HTMLTextAreaElement>('chatInput'),
  chatButton: byId<HTMLButtonElement>('chatButton'),
  providerSelect: byId<HTMLSelectElement>('providerSelect'),
  modelInput: byId<HTMLInputElement>('modelInput'),
  baseUrlInput: byId<HTMLInputElement>('baseUrlInput'),
  apiKeyInput: byId<HTMLInputElement>('apiKeyInput'),
  saveProviderButton: byId<HTMLButtonElement>('saveProviderButton'),
  clearKeyButton: byId<HTMLButtonElement>('clearKeyButton'),
  providerState: byId<HTMLSpanElement>('providerState'),
  toolsEnabled: byId<HTMLInputElement>('toolsEnabled'),
  toolList: byId<HTMLDivElement>('toolList'),
};

const quickCommands = [
  { label: 'Pytest', command: 'python -m pytest', icon: 'flask-conical' },
  { label: 'Compile', command: 'python -m compileall src tests', icon: 'hammer' },
  { label: 'Trace', command: 'python -m pytest tests/test_routing_trace_endpoints.py', icon: 'activity' },
  { label: 'Status', command: 'git status -sb', icon: 'git-branch' },
];

bootstrap().catch(error => {
  setStatus(error instanceof Error ? error.message : String(error), 'error');
});

async function bootstrap(): Promise<void> {
  renderQuickCommands();
  createEditor();
  bindEvents();
  refreshIcons();

  if (!api) {
    setBridgeOffline();
    return;
  }

  api.onCommandChunk(appendTerminalChunk);
  await Promise.all([loadModelProviders(), loadTools()]);
  const workspace = await api.workspace();
  nodes.rootPath.textContent = workspace.root;
  directoryCache.set('.', workspace.entries);
  renderExplorer();
  await openFile(currentFilePath);
  addChatMessage({
    role: 'bob',
    content: 'BOB desktop bridge online. Local runtime sealed.',
    timestamp: new Date().toISOString(),
  });
  setStatus('Desktop bridge online', 'ok');
}

function createEditor(): void {
  editor = monaco.editor.create(nodes.editorHost, {
    value: '',
    language: 'markdown',
    theme: 'vs-dark',
    automaticLayout: true,
    minimap: { enabled: true },
    fontSize: 14,
    fontFamily: 'Cascadia Code, Consolas, monospace',
    lineNumbersMinChars: 4,
    scrollBeyondLastLine: false,
    fixedOverflowWidgets: true,
    padding: { top: 16, bottom: 16 },
  });
}

function bindEvents(): void {
  nodes.saveButton.addEventListener('click', () => void saveCurrentFile());
  nodes.refreshButton.addEventListener('click', () => void refreshWorkspace());
  nodes.runButton.addEventListener('click', () => void runCommand(nodes.commandInput.value));
  nodes.commandInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      void runCommand(nodes.commandInput.value);
    }
  });
  nodes.chatButton.addEventListener('click', () => void sendChat());
  nodes.providerSelect.addEventListener('change', () => renderSelectedProvider());
  nodes.saveProviderButton.addEventListener('click', () => void saveSelectedProvider(false));
  nodes.clearKeyButton.addEventListener('click', () => void saveSelectedProvider(true));
  nodes.toolsEnabled.addEventListener('change', () => {
    setStatus(nodes.toolsEnabled.checked ? 'Model tools enabled' : 'Model tools disabled', 'idle');
  });
  nodes.chatInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      void sendChat();
    }
  });
}

async function refreshWorkspace(): Promise<void> {
  if (!api) return;
  const workspace = await api.workspace();
  directoryCache.set('.', workspace.entries);
  renderExplorer();
  setStatus('Workspace refreshed', 'ok');
}

function renderQuickCommands(): void {
  nodes.quickCommands.replaceChildren(...quickCommands.map(item => {
    const button = document.createElement('button');
    button.className = 'tool-button';
    button.type = 'button';
    button.title = item.command;
    button.innerHTML = `<i data-lucide="${item.icon}"></i><span>${item.label}</span>`;
    button.addEventListener('click', () => void runCommand(item.command));
    return button;
  }));
}

async function loadModelProviders(): Promise<void> {
  if (!api) return;
  modelProviders = await api.listModelProviders();
  renderModelProviders();
}

function renderModelProviders(): void {
  const active = modelProviders.find(provider => provider.isActive)?.providerId ?? 'local';
  nodes.providerSelect.replaceChildren(...modelProviders.map(provider => {
    const option = document.createElement('option');
    option.value = provider.providerId;
    option.textContent = provider.label;
    return option;
  }));
  nodes.providerSelect.value = active;
  renderSelectedProvider();
}

function renderSelectedProvider(): void {
  const selected = selectedProviderId();
  const provider = modelProviders.find(item => item.providerId === selected);
  if (!provider) {
    nodes.providerState.textContent = 'Provider unavailable';
    return;
  }

  const isLocal = provider.providerId === 'local';
  nodes.modelInput.value = provider.model;
  nodes.baseUrlInput.value = provider.baseUrl;
  nodes.apiKeyInput.value = '';
  nodes.modelInput.disabled = isLocal;
  nodes.baseUrlInput.disabled = isLocal;
  nodes.apiKeyInput.disabled = isLocal;
  nodes.clearKeyButton.disabled = isLocal || !provider.hasApiKey;
  nodes.saveProviderButton.disabled = false;

  const keyState = isLocal
    ? 'No key needed'
    : provider.hasApiKey
      ? 'Key stored'
      : providerNeedsApiKey(provider.providerId)
        ? 'Needs key'
        : 'Key optional';
  nodes.providerState.textContent = `${provider.isActive ? 'Active' : 'Inactive'} | ${keyState}`;
}

async function saveSelectedProvider(clearApiKey: boolean): Promise<void> {
  if (!api) return;

  const providerId = selectedProviderId();
  const key = nodes.apiKeyInput.value.trim();
  const update: ModelProviderUpdate = {
    providerId,
    model: nodes.modelInput.value,
    baseUrl: nodes.baseUrlInput.value,
    setActive: true,
    clearApiKey,
    ...(!clearApiKey && key ? { apiKey: key } : {}),
  };

  nodes.saveProviderButton.disabled = true;
  nodes.clearKeyButton.disabled = true;
  setStatus(clearApiKey ? 'Clearing provider key' : 'Saving provider settings', 'idle');

  try {
    modelProviders = await api.saveModelProvider(update);
    renderModelProviders();
    const provider = modelProviders.find(item => item.providerId === providerId);
    setStatus(`${provider?.label ?? providerId} provider saved`, 'ok');
  } catch (error) {
    setStatus(error instanceof Error ? error.message : String(error), 'error');
    renderSelectedProvider();
  }
}

async function loadTools(): Promise<void> {
  if (!api) return;
  sovereignTools = await api.listTools();
  renderToolList();
}

function renderToolList(): void {
  if (sovereignTools.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'tool-pill';
    empty.textContent = 'No tools loaded';
    nodes.toolList.replaceChildren(empty);
    return;
  }

  nodes.toolList.replaceChildren(...sovereignTools.map(tool => {
    const row = document.createElement('div');
    row.className = 'tool-pill';
    row.title = JSON.stringify(tool.inputSchema);
    row.innerHTML = `<span>${escapeHtml(tool.name)}</span><small>${escapeHtml(tool.description)}</small>`;
    return row;
  }));
}

function renderExplorer(): void {
  const rootEntries = directoryCache.get('.') ?? [];
  nodes.fileTree.replaceChildren(...renderEntries(rootEntries, 0));
  refreshIcons();
}

function renderEntries(entries: ReadonlyArray<DesktopFileEntry>, depth: number): HTMLElement[] {
  const rendered: HTMLElement[] = [];

  for (const entry of entries) {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = `tree-row ${entry.kind}`;
    row.style.setProperty('--depth', String(depth));
    row.title = entry.relativePath;

    const isExpanded = expandedDirectories.has(entry.relativePath);
    const icon = entry.kind === 'directory'
      ? isExpanded ? 'chevron-down' : 'chevron-right'
      : iconForFile(entry.relativePath);
    row.innerHTML = `<i data-lucide="${icon}"></i><span>${entry.name}</span>`;

    if (entry.kind === 'directory') {
      row.addEventListener('click', () => void toggleDirectory(entry.relativePath));
    } else {
      row.addEventListener('click', () => void openFile(entry.relativePath));
    }

    rendered.push(row);

    if (entry.kind === 'directory' && isExpanded) {
      rendered.push(...renderEntries(directoryCache.get(entry.relativePath) ?? [], depth + 1));
    }
  }

  return rendered;
}

async function toggleDirectory(path: string): Promise<void> {
  if (!api) return;

  if (expandedDirectories.has(path)) {
    expandedDirectories.delete(path);
    renderExplorer();
    return;
  }

  expandedDirectories.add(path);
  if (!directoryCache.has(path)) {
    directoryCache.set(path, await api.list(path));
  }
  renderExplorer();
}

async function openFile(path: string): Promise<void> {
  if (!api) return;

  try {
    const snapshot = await api.readFile(path);
    currentFilePath = snapshot.relativePath;
    nodes.fileName.textContent = snapshot.relativePath;
    nodes.fileMeta.textContent = snapshot.language;
    const previousModel = editor.getModel();
    previousModel?.dispose();
    const model = monaco.editor.createModel(
      snapshot.content,
      snapshot.language,
      monaco.Uri.parse(`shadow://${snapshot.relativePath}`),
    );
    editor.setModel(model);
    setStatus(`Opened ${snapshot.relativePath}`, 'ok');
  } catch (error) {
    setStatus(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function saveCurrentFile(): Promise<void> {
  if (!api) return;

  try {
    const content = editor.getValue();
    const snapshot = await api.saveFile(currentFilePath, content);
    nodes.fileMeta.textContent = `${snapshot.language} saved`;
    setStatus(`Saved ${snapshot.relativePath}`, 'ok');
  } catch (error) {
    setStatus(error instanceof Error ? error.message : String(error), 'error');
  }
}

async function runCommand(command: string): Promise<void> {
  if (!api || commandRunning) return;

  const trimmed = command.trim();
  if (!trimmed) return;

  commandRunning = true;
  nodes.runButton.disabled = true;
  nodes.commandInput.value = trimmed;
  appendTerminal(`\n> ${trimmed}\n`, 'system');

  try {
    const result = await api.runCommand({ command: trimmed });
    renderTrace(result.trace);
    if (!result.allowed) appendTerminal(`DENIED: ${result.reason ?? 'policy denied'}\n`, 'stderr');
    setStatus(result.allowed ? `Command exited ${result.exitCode}` : 'Command denied', result.allowed ? 'ok' : 'error');
  } catch (error) {
    setStatus(error instanceof Error ? error.message : String(error), 'error');
  } finally {
    commandRunning = false;
    nodes.runButton.disabled = false;
  }
}

async function sendChat(): Promise<void> {
  if (!api) return;

  const prompt = nodes.chatInput.value.trim();
  if (!prompt) return;

  nodes.chatInput.value = '';
  const history = [...chatMessages];
  addChatMessage({
    role: 'user',
    content: prompt,
    timestamp: new Date().toISOString(),
  });

  nodes.chatButton.disabled = true;
  setStatus(`BOB thinking via ${activeProviderLabel()}`, 'idle');

  try {
    const response = await api.bobChat({
      prompt,
      messages: history,
      toolsEnabled: nodes.toolsEnabled.checked,
    });
    for (const event of response.toolEvents) {
      addChatMessage(toolEventMessage(event, response.provider));
    }
    addChatMessage(response.message);
    renderTrace(response.trace);
    const toolSummary = response.toolEvents.length > 0
      ? ` | ${response.toolEvents.length} tool${response.toolEvents.length === 1 ? '' : 's'}`
      : '';
    setStatus(`BOB sealed ${response.seal} via ${response.provider}${toolSummary}`, 'ok');
  } catch (error) {
    setStatus(error instanceof Error ? error.message : String(error), 'error');
  } finally {
    nodes.chatButton.disabled = false;
  }
}

function addChatMessage(message: BobChatMessage): void {
  chatMessages.push(message);

  const item = document.createElement('article');
  item.className = `chat-message ${message.role}`;
  const footer = [message.provider ? `provider:${message.provider}` : '', message.seal ?? '']
    .filter(Boolean)
    .join(' | ');
  item.innerHTML = [
    `<header><span>${chatRoleLabel(message.role)}</span><time>${formatTime(message.timestamp)}</time></header>`,
    `<p>${escapeHtml(message.content)}</p>`,
    footer ? `<footer>${footer}</footer>` : '',
  ].join('');

  nodes.chatLog.append(item);
  nodes.chatLog.scrollTop = nodes.chatLog.scrollHeight;
}

function renderTrace(trace: ReadonlyArray<{ readonly phase: string; readonly summary: string }>): void {
  nodes.trace.replaceChildren(...trace.map(event => {
    const row = document.createElement('div');
    row.className = 'trace-row';
    row.innerHTML = `<span>${event.phase}</span><p>${escapeHtml(event.summary)}</p>`;
    return row;
  }));
}

function appendTerminalChunk(chunk: DesktopCommandChunk): void {
  appendTerminal(chunk.text, chunk.stream);
}

function appendTerminal(text: string, stream: DesktopCommandChunk['stream']): void {
  const span = document.createElement('span');
  span.className = stream;
  span.textContent = text;
  nodes.terminal.append(span);
  nodes.terminal.scrollTop = nodes.terminal.scrollHeight;
}

function setStatus(message: string, kind: 'ok' | 'error' | 'idle' = 'idle'): void {
  nodes.status.textContent = message;
  nodes.status.dataset.kind = kind;
}

function setBridgeOffline(): void {
  setStatus('Desktop bridge offline', 'error');
  nodes.rootPath.textContent = 'Electron preload unavailable';
  nodes.saveButton.disabled = true;
  nodes.runButton.disabled = true;
  nodes.chatButton.disabled = true;
  nodes.providerSelect.disabled = true;
  nodes.modelInput.disabled = true;
  nodes.baseUrlInput.disabled = true;
  nodes.apiKeyInput.disabled = true;
  nodes.saveProviderButton.disabled = true;
  nodes.clearKeyButton.disabled = true;
  nodes.toolsEnabled.disabled = true;
  addChatMessage({
    role: 'bob',
    content: 'Desktop bridge offline. Open through Electron.',
    timestamp: new Date().toISOString(),
  });
}

function iconForFile(path: string): string {
  if (path.endsWith('.ts')) return 'braces';
  if (path.endsWith('.json')) return 'brackets';
  if (path.endsWith('.md')) return 'file-text';
  if (path.endsWith('.html')) return 'layout-panel-top';
  if (path.endsWith('.css')) return 'palette';
  if (path.endsWith('.yml') || path.endsWith('.yaml')) return 'workflow';
  return 'file-code';
}

function selectedProviderId(): ModelProviderId {
  const value = nodes.providerSelect.value;
  return modelProviderIds.includes(value as ModelProviderId) ? value as ModelProviderId : 'local';
}

function providerNeedsApiKey(providerId: ModelProviderId): boolean {
  return providerId === 'anthropic' || providerId === 'openrouter';
}

function activeProviderLabel(): string {
  const active = modelProviders.find(provider => provider.isActive);
  return active?.label ?? 'Local BOB';
}

function toolEventMessage(event: DesktopToolEvent, provider: ModelProviderId): BobChatMessage {
  return {
    role: 'tool',
    content: [
      `${event.name}: ${event.ok ? 'ok' : 'failed'}`,
      truncateForChat(event.output),
    ].filter(Boolean).join('\n\n'),
    timestamp: new Date().toISOString(),
    provider,
  };
}

function chatRoleLabel(role: BobChatMessage['role']): string {
  if (role === 'bob') return 'BOB';
  if (role === 'tool') return 'TOOL';
  return 'YOU';
}

function refreshIcons(): void {
  createIcons({ icons });
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function truncateForChat(value: string): string {
  const limit = 2400;
  if (value.length <= limit) return value;
  return `${value.slice(0, limit)}\n\n[truncated in chat]`;
}
