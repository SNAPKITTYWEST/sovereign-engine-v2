export interface DesktopFileEntry {
  readonly name: string;
  readonly relativePath: string;
  readonly kind: 'file' | 'directory';
  readonly size: number;
}

export interface DesktopFileSnapshot {
  readonly relativePath: string;
  readonly content: string;
  readonly language: string;
}

export interface DesktopCommandRequest {
  readonly command: string;
}

export interface DesktopCommandChunk {
  readonly runId: string;
  readonly stream: 'stdout' | 'stderr' | 'system';
  readonly text: string;
}

export interface DesktopCommandResult {
  readonly runId: string;
  readonly command: string;
  readonly allowed: boolean;
  readonly exitCode: number | null;
  readonly signal: NodeJS.Signals | null;
  readonly stdout: string;
  readonly stderr: string;
  readonly reason?: string;
  readonly seal?: string;
  readonly trace: ReadonlyArray<{
    readonly phase: string;
    readonly summary: string;
  }>;
}

export type ModelProviderId =
  | 'local'
  | 'ollama'
  | 'anthropic'
  | 'openrouter'
  | 'opencode'
  | 'llama'
  | 'openai-compatible';

export interface ModelProviderSummary {
  readonly providerId: ModelProviderId;
  readonly label: string;
  readonly model: string;
  readonly baseUrl: string;
  readonly hasApiKey: boolean;
  readonly isActive: boolean;
  readonly updatedAt?: string;
}

export interface ModelProviderUpdate {
  readonly providerId: ModelProviderId;
  readonly model?: string;
  readonly baseUrl?: string;
  readonly apiKey?: string;
  readonly clearApiKey?: boolean;
  readonly setActive?: boolean;
}

export interface DesktopToolSummary {
  readonly name: string;
  readonly description: string;
  readonly inputSchema: Record<string, unknown>;
}

export interface DesktopToolEvent {
  readonly name: string;
  readonly ok: boolean;
  readonly output: string;
}

export interface BobChatMessage {
  readonly role: 'user' | 'bob' | 'tool';
  readonly content: string;
  readonly timestamp: string;
  readonly seal?: string;
  readonly provider?: ModelProviderId;
}

export interface BobChatRequest {
  readonly prompt: string;
  readonly messages: ReadonlyArray<BobChatMessage>;
  readonly toolsEnabled: boolean;
}

export interface BobChatResponse {
  readonly message: BobChatMessage;
  readonly seal: string;
  readonly verdict: string;
  readonly provider: ModelProviderId;
  readonly toolEvents: ReadonlyArray<DesktopToolEvent>;
  readonly trace: ReadonlyArray<{
    readonly phase: string;
    readonly summary: string;
  }>;
}

export interface WorkspaceOverview {
  readonly root: string;
  readonly entries: ReadonlyArray<DesktopFileEntry>;
}

export interface ShadowDesktopApi {
  workspace(): Promise<WorkspaceOverview>;
  list(path?: string): Promise<ReadonlyArray<DesktopFileEntry>>;
  readFile(path: string): Promise<DesktopFileSnapshot>;
  saveFile(path: string, content: string): Promise<DesktopFileSnapshot>;
  runCommand(request: DesktopCommandRequest): Promise<DesktopCommandResult>;
  listModelProviders(): Promise<ReadonlyArray<ModelProviderSummary>>;
  saveModelProvider(update: ModelProviderUpdate): Promise<ReadonlyArray<ModelProviderSummary>>;
  listTools(): Promise<ReadonlyArray<DesktopToolSummary>>;
  bobChat(request: BobChatRequest): Promise<BobChatResponse>;
  onCommandChunk(listener: (chunk: DesktopCommandChunk) => void): () => void;
}
