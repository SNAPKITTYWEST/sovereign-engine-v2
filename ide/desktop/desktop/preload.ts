import { contextBridge, ipcRenderer } from 'electron';

import type {
  BobChatResponse,
  DesktopCommandChunk,
  DesktopCommandRequest,
  DesktopCommandResult,
  DesktopFileEntry,
  DesktopFileSnapshot,
  DesktopToolSummary,
  ModelProviderSummary,
  ModelProviderUpdate,
  ShadowDesktopApi,
  WorkspaceOverview,
} from './shared.js';

const api: ShadowDesktopApi = {
  workspace: () => ipcRenderer.invoke('desktop:workspace') as Promise<WorkspaceOverview>,
  list: (path?: string) => ipcRenderer.invoke('desktop:list', path) as Promise<ReadonlyArray<DesktopFileEntry>>,
  readFile: (path: string) => ipcRenderer.invoke('desktop:read-file', path) as Promise<DesktopFileSnapshot>,
  saveFile: (path: string, content: string) => (
    ipcRenderer.invoke('desktop:save-file', path, content) as Promise<DesktopFileSnapshot>
  ),
  runCommand: (request: DesktopCommandRequest) => (
    ipcRenderer.invoke('desktop:run-command', request) as Promise<DesktopCommandResult>
  ),
  listModelProviders: () => (
    ipcRenderer.invoke('desktop:list-model-providers') as Promise<ReadonlyArray<ModelProviderSummary>>
  ),
  saveModelProvider: (update: ModelProviderUpdate) => (
    ipcRenderer.invoke('desktop:save-model-provider', update) as Promise<ReadonlyArray<ModelProviderSummary>>
  ),
  listTools: () => ipcRenderer.invoke('desktop:list-tools') as Promise<ReadonlyArray<DesktopToolSummary>>,
  bobChat: request => ipcRenderer.invoke('desktop:bob-chat', request) as Promise<BobChatResponse>,
  onCommandChunk: (listener: (chunk: DesktopCommandChunk) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, chunk: DesktopCommandChunk): void => listener(chunk);
    ipcRenderer.on('desktop:command-chunk', handler);
    return () => ipcRenderer.removeListener('desktop:command-chunk', handler);
  },
};

contextBridge.exposeInMainWorld('shadowDesktop', api);
