# Sovereign Engine Desktop IDE

Electron + Monaco desktop workbench for `sovereign-engine-v2`.

## Run

```powershell
cd C:\Users\jessi\sovereign-engine-v2\ide\desktop
npm install
npm run desktop
```

The IDE opens the engine repo root (`C:\Users\jessi\sovereign-engine-v2`) as the workspace.

## Model Keys

Keys are entered from the Models panel and stored by Electron `safeStorage` under the app userData directory:

`sovereign-engine-desktop\providers.json`

No API keys are hardcoded into source files or exposed to the renderer after saving.

Supported provider slots:

- Local BOB fallback
- Ollama
- Anthropic
- OpenRouter
- OpenCode
- Llama API
- OpenAI-compatible endpoint

## Sovereign Tools

The model can request one allowlisted tool call per turn when Tools are enabled. Built-in tool calls include workspace search/read, read-only git status/diff, Python evidence gates, and Sovereign Engine bridge reads.

Bridge-backed tools use `SOVEREIGN_ENGINE_BRIDGE_URL` or `http://127.0.0.1:19000` by default. Start the Python bridge from the engine root when bridge tools are needed:

```powershell
python -m src.bridge.http_server
```

Model auto-tools refuse bridge tool execution for risk classes above `2`; higher-risk tools still require explicit user action outside model auto-tooling.
