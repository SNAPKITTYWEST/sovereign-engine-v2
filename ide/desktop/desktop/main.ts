import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { app, BrowserWindow, ipcMain, Menu, shell } from 'electron';

import { BobChatBroker, userChatMessage } from './backend/bob.js';
import { ModelProviderStore } from './backend/providers.js';
import { DesktopCommandBroker } from './backend/sandbox.js';
import { SovereignToolBroker } from './backend/tools.js';
import {
  getWorkspaceOverview,
  listWorkspaceEntries,
  readWorkspaceTextFile,
  saveWorkspaceTextFile,
} from './backend/workspace.js';
import type { BobChatRequest, DesktopCommandRequest, ModelProviderUpdate } from './shared.js';

const moduleDir = dirname(fileURLToPath(import.meta.url));
const packageRoot = moduleDir.replaceAll('\\', '/').endsWith('/dist/desktop')
  ? resolve(moduleDir, '..', '..')
  : resolve(moduleDir, '..');
const repoRoot = resolve(packageRoot, '..', '..');
const preloadPath = resolve(moduleDir, 'preload.js');
const builtRendererPath = resolve(packageRoot, '_site', 'desktop', 'index.html');
const sourceRendererPath = resolve(packageRoot, 'desktop', 'index.html');

let commands: DesktopCommandBroker;
let providers: ModelProviderStore;
let tools: SovereignToolBroker;
let chat: BobChatBroker;

let mainWindow: BrowserWindow | null = null;

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 720,
    title: 'Sovereign Engine Desktop IDE',
    backgroundColor: '#111318',
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  Menu.setApplicationMenu(null);

  const devUrl = process.env.SHADOW_DESKTOP_DEV_URL;
  if (devUrl) {
    await mainWindow.loadURL(devUrl);
  } else {
    const rendererPath = existsSync(builtRendererPath) ? builtRendererPath : sourceRendererPath;
    await mainWindow.loadURL(pathToFileURL(rendererPath).toString());
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function registerIpc(): void {
  commands = new DesktopCommandBroker(repoRoot);
  providers = ModelProviderStore.fromUserData(app.getPath('userData'));
  tools = new SovereignToolBroker(repoRoot, commands);
  chat = new BobChatBroker(providers, tools);

  ipcMain.handle('desktop:workspace', () => getWorkspaceOverview(repoRoot));
  ipcMain.handle('desktop:list', (_event, path?: string) => listWorkspaceEntries(repoRoot, path));
  ipcMain.handle('desktop:read-file', (_event, path: string) => readWorkspaceTextFile(repoRoot, path));
  ipcMain.handle('desktop:save-file', (_event, path: string, content: string) => (
    saveWorkspaceTextFile(repoRoot, path, content)
  ));
  ipcMain.handle('desktop:list-model-providers', () => providers.list());
  ipcMain.handle('desktop:save-model-provider', (_event, update: ModelProviderUpdate) => (
    providers.save(update)
  ));
  ipcMain.handle('desktop:list-tools', () => tools.list());
  ipcMain.handle('desktop:bob-chat', (_event, request: BobChatRequest) => {
    userChatMessage(request.prompt);
    return chat.respond(request);
  });
  ipcMain.handle('desktop:run-command', async (_event, request: DesktopCommandRequest) => (
    commands.run(request, chunk => mainWindow?.webContents.send('desktop:command-chunk', chunk))
  ));
}

app.on('web-contents-created', (_event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: 'deny' };
  });

  contents.on('will-navigate', event => {
    event.preventDefault();
  });
});

app.whenReady().then(async () => {
  registerIpc();
  await createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
