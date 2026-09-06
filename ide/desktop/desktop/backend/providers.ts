import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

import { safeStorage } from 'electron';

import type { ModelProviderId, ModelProviderSummary, ModelProviderUpdate } from '../shared.js';

export interface ResolvedModelProvider {
  readonly providerId: ModelProviderId;
  readonly label: string;
  readonly model: string;
  readonly baseUrl: string;
  readonly apiKey?: string;
}

interface StoredProvider {
  providerId: ModelProviderId;
  model?: string;
  baseUrl?: string;
  apiKeyCipher?: string;
  updatedAt?: string;
}

interface StoredProviderFile {
  activeProvider: ModelProviderId;
  providers: Partial<Record<ModelProviderId, StoredProvider>>;
}

export const PROVIDER_DEFAULTS: Record<ModelProviderId, Omit<ModelProviderSummary, 'hasApiKey' | 'isActive' | 'updatedAt'>> = {
  local: {
    providerId: 'local',
    label: 'Local BOB',
    model: 'deterministic-local',
    baseUrl: 'local://sovereign-engine',
  },
  ollama: {
    providerId: 'ollama',
    label: 'Ollama',
    model: 'llama3.1',
    baseUrl: 'http://127.0.0.1:11434',
  },
  anthropic: {
    providerId: 'anthropic',
    label: 'Anthropic',
    model: 'claude-sonnet-4-5',
    baseUrl: 'https://api.anthropic.com',
  },
  openrouter: {
    providerId: 'openrouter',
    label: 'OpenRouter',
    model: 'anthropic/claude-sonnet-4.5',
    baseUrl: 'https://openrouter.ai/api/v1',
  },
  opencode: {
    providerId: 'opencode',
    label: 'OpenCode',
    model: 'opencode/default',
    baseUrl: 'http://127.0.0.1:4096/v1',
  },
  llama: {
    providerId: 'llama',
    label: 'Llama API',
    model: 'llama3.1',
    baseUrl: 'http://127.0.0.1:8080/v1',
  },
  'openai-compatible': {
    providerId: 'openai-compatible',
    label: 'OpenAI-compatible',
    model: 'llama-local',
    baseUrl: 'http://127.0.0.1:8080/v1',
  },
};

const PROVIDER_IDS = Object.keys(PROVIDER_DEFAULTS) as ModelProviderId[];

export class ModelProviderStore {
  constructor(private readonly storePath: string) {}

  static fromUserData(userDataPath: string): ModelProviderStore {
    return new ModelProviderStore(resolve(userDataPath, 'sovereign-engine-desktop', 'providers.json'));
  }

  async list(): Promise<ReadonlyArray<ModelProviderSummary>> {
    const state = await this.readState();
    return PROVIDER_IDS.map(providerId => {
      const stored = state.providers[providerId];
      const defaults = PROVIDER_DEFAULTS[providerId];
      return {
        ...defaults,
        model: stored?.model?.trim() || defaults.model,
        baseUrl: stored?.baseUrl?.trim() || defaults.baseUrl,
        hasApiKey: Boolean(stored?.apiKeyCipher),
        isActive: state.activeProvider === providerId,
        updatedAt: stored?.updatedAt,
      };
    });
  }

  async save(update: ModelProviderUpdate): Promise<ReadonlyArray<ModelProviderSummary>> {
    const state = await this.readState();
    const existing = state.providers[update.providerId] ?? { providerId: update.providerId };
    const next: StoredProvider = {
      ...existing,
      providerId: update.providerId,
      model: update.model?.trim() || existing.model,
      baseUrl: update.baseUrl?.trim() || existing.baseUrl,
      apiKeyCipher: existing.apiKeyCipher,
      updatedAt: new Date().toISOString(),
    };

    if (update.clearApiKey) {
      state.providers[update.providerId] = { ...next, apiKeyCipher: undefined };
    } else if (typeof update.apiKey === 'string' && update.apiKey.trim()) {
      state.providers[update.providerId] = {
        ...next,
        apiKeyCipher: encryptSecret(update.apiKey.trim()),
      };
    } else {
      state.providers[update.providerId] = next;
    }

    if (update.setActive) {
      state.activeProvider = update.providerId;
    }

    await this.writeState(state);
    return this.list();
  }

  async resolveActive(): Promise<ResolvedModelProvider> {
    const state = await this.readState();
    const providerId = state.activeProvider;
    const defaults = PROVIDER_DEFAULTS[providerId];
    const stored = state.providers[providerId];
    return {
      providerId,
      label: defaults.label,
      model: stored?.model?.trim() || defaults.model,
      baseUrl: trimTrailingSlash(stored?.baseUrl?.trim() || defaults.baseUrl),
      apiKey: stored?.apiKeyCipher ? decryptSecret(stored.apiKeyCipher) : undefined,
    };
  }

  private async readState(): Promise<StoredProviderFile> {
    try {
      const raw = await readFile(this.storePath, 'utf8');
      const parsed = JSON.parse(raw) as StoredProviderFile;
      return {
        activeProvider: parsed.activeProvider && PROVIDER_IDS.includes(parsed.activeProvider)
          ? parsed.activeProvider
          : 'local',
        providers: parsed.providers ?? {},
      };
    } catch {
      return { activeProvider: 'local', providers: {} };
    }
  }

  private async writeState(state: StoredProviderFile): Promise<void> {
    await mkdir(dirname(this.storePath), { recursive: true });
    await writeFile(this.storePath, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
  }
}

function encryptSecret(secret: string): string {
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error('Electron safeStorage is unavailable; refusing to persist API key as plaintext.');
  }
  return safeStorage.encryptString(secret).toString('base64');
}

function decryptSecret(cipher: string): string {
  return safeStorage.decryptString(Buffer.from(cipher, 'base64'));
}

function trimTrailingSlash(value: string): string {
  return value.endsWith('/') ? value.slice(0, -1) : value;
}
