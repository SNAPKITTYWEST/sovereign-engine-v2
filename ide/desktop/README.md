# Sovereign Engine desktop workbench

Electron/TypeScript workbench sources for this repository. The main process derives the workspace from the package location; it does not require a particular user's home directory.

See the [IDE development guide](../../docs/IDE.md) for package commands, build outputs, provider storage, and validation scope. See [bridge contracts](../../docs/ASR_AND_BRIDGE.md) before enabling bridge-backed tools.

The [package scripts](package.json) expose `typecheck`, `test`, `build`, `verify`, and `desktop`. Their presence is not evidence that the current checkout builds successfully.
