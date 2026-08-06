# ⚡ SOVEREIGN ENGINE — QUICK REFERENCE

## Start Server

```bash
cd c:/tmp/sovereign-reverse/engine
python -m src.bridge.http_server
```

Server starts on: `http://127.0.0.1:19000`

---

## Test C Client

```bash
cd C:/Users/jessi/Desktop/sovereign-ide/native/bridge
gcc -o example.exe example.c bridge_http.c -lwinhttp
./example.exe
```

---

## API Endpoints

### Health
```bash
GET /health
→ {"status": "ok", "timestamp": "..."}
```

### Tools
```bash
GET /tools
→ {"tools": [{"id": "filesystem.read", ...}]}

POST /tool/execute
{"tool": "filesystem.read", "args": {"path": "file.txt"}}
→ {"result": {...}}
```

### Keys
```bash
POST /keys/set
{"provider": "openrouter", "key": "sk-or-v1-..."}
→ {"success": true, "expires_in_hours": 24}

GET /keys/status
→ {"keys": {"openrouter": {...}}}

DELETE /keys/openrouter
→ {"success": true}
```

### Agent
```bash
POST /agent/run
{"task": "List files in current directory"}
→ {"result": "...", "task_id": "..."}
```

### Chat
```bash
POST /chat
{"message": "Hello!"}
→ {"reply": "..."}
```

---

## C Bridge API

```c
#include "bridge.h"

BridgeConfig config = {
    .transport = BRIDGE_TRANSPORT_HTTP,
    .http_host = "127.0.0.1",
    .http_port = 19000,
    .request_timeout = 30000
};

Bridge* bridge = bridge_init(&config);

// Health
bool ok = bridge_health_check(bridge);

// Tools
char* tools = bridge_tools_list(bridge);
char* result = bridge_tool_execute(bridge, "filesystem.read", "{\"path\":\"file.txt\"}");

// Keys
char* response = bridge_set_key(bridge, "openrouter", "sk-or-v1-...");
char* status = bridge_get_key_status(bridge);

// Agent
char* output = bridge_agent_run(bridge, "List files");

// Chat
char* reply = bridge_chat_message(bridge, "Hello!");

// Cleanup
free(result); free(tools); // etc
bridge_shutdown(bridge);
```

---

## Available Tools

### Filesystem
- `filesystem.read` — Read file
- `filesystem.write` — Write file
- `filesystem.list` — List directory

### Code
- `code.execute_python` — Run Python code

### Git (TODO)
- `git.status`
- `git.commit`
- `git.diff`

### Documents (TODO)
- `documents.pdf.parse`
- `documents.docx.parse`

---

## Providers

### OpenRouter (Free)
Models: Nemotron 70B, Mistral 7B  
Setup: Get key from https://openrouter.ai/keys  
Rotation: Daily (24h expiration)

### Ollama (Local)
Models: Llama 3.2, CodeLlama, Muse 1.0  
Setup: `ollama pull llama3.2`  
Cost: Free forever

### MoE Routing
- Code tasks → Nemotron 70B
- Reasoning → Nemotron 70B
- Creative → Mistral 7B
- Chat → Mistral 7B
- Fallback → Ollama

---

## File Locations

### Python Engine
```
c:/tmp/sovereign-reverse/engine/
  src/
    core/         # Crypto, types, evidence
    runtime/      # Providers, effects
    tools/        # Tool namespaces
    agents/       # ReAct, MCTS
    retrieval/    # RAG, parallel
    scanner/      # AST, dependencies
    mcp/          # MCP server
    bridge/       # HTTP, stdio, keys
```

### C Bridge
```
C:/Users/jessi/Desktop/sovereign-ide/
  native/bridge/
    bridge.h
    bridge_http.c
    example.c
    test_keys.c
    test_tools.c
```

### Keys Storage
```
~/.sovereign/keys.json
```

---

## Common Issues

### Port 19000 in use
```bash
# Kill process on Windows
netstat -ano | findstr 19000
taskkill /PID <pid> /F
```

### Health check fails
- Check server is running
- Check firewall not blocking
- Verify correct port (19000)

### Tools return "not found"
- Server needs restart to load tools
- Check `load_all_tools()` called in bridge init

### Key expired
- Set new key via `/keys/set`
- Or use Ollama (no key needed)

---

## Architecture

```
┌─────────────────────────────────────┐
│  C IDE (Win32)                      │
│  - Editor, LSP, Git, Terminal       │
│  - Bridge Client (WinHTTP)          │
└──────────────┬──────────────────────┘
               │ HTTP :19000
┌──────────────▼──────────────────────┐
│  Python Bridge (aiohttp)            │
│  - Key Manager                      │
│  - Tool Registry                    │
│  - Multi-Provider MoE               │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐  ┌──────▼──────┐
│ OpenRouter  │  │   Ollama    │
│ (Cloud)     │  │  (Local)    │
│ Free daily  │  │  Free 4ever │
└─────────────┘  └─────────────┘
```

---

## Stats

- **Total Lines:** 11,643 (29% of 40K)
- **Total Files:** 70
- **Providers:** 6
- **Tools:** 4 registered
- **Layers:** 10/12 complete
- **Accessibility:** 7.5/10

---

**Last Updated:** 2026-08-03  
**Version:** v0.29
