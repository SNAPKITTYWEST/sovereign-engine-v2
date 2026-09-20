# Desktop development guide

The repository contains a native Windows client, an Electron workbench, and BEAM-style WebAssembly sources. Build them independently.

## Native Windows client

The [CMake project](../ide/CMakeLists.txt) requires CMake 3.24+, Windows, a C17/C++17 toolchain, and Windows SDK libraries including Direct2D/DirectWrite. From the repository root:

```powershell
cmake -S ide -B ide/build -G "Visual Studio 17 2022"
cmake --build ide/build --config Release
```

The build definition is in `ide/`, not `ide/native/`. The native source tree includes editor buffers/views, ConPTY, LSP, chat transport, Git operations, and graphics. Source inspection is not a successful build; this documentation update did not compile the IDE.

For bridge behavior and startup constraints, read [ASR and bridge](ASR_AND_BRIDGE.md).

## Electron workbench

The package is [ide/desktop/package.json](../ide/desktop/package.json). From a Node/npm environment compatible with that package's dependencies:

```bash
cd ide/desktop
npm ci
npm run typecheck
npm test
npm run desktop
```

`desktop` runs the TypeScript/Vite build and then Electron. TypeScript emits to `dist/`; Vite targets `_site/`. The main process derives the workspace root from its package location, so no user-specific absolute path is required.

The Vite configuration names `desktop/index.html` as its renderer input, which is present in the inspected checkout. A complete desktop build was not run during this documentation update.

Provider credentials are encrypted using Electron safeStorage, and persistence rejects unavailable encryption. Bridge-backed tools use `SOVEREIGN_ENGINE_BRIDGE_URL` or `http://127.0.0.1:19000`. The desktop's automatic tool path rejects missing risk metadata or risk classes greater than 2. That client check does not protect direct callers of the HTTP service.

## BEAM-style WebAssembly

[ide/beam/](../ide/beam/) is a separate source collection. Do not infer that it replaces either desktop implementation or has been integrated into their builds.

For current validation boundaries, see [Testing](TESTING.md).
