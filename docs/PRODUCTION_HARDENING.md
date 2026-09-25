# Deployment readiness

This replaces the former agent-directed implementation plan. It records concrete integration gaps in the inspected source baseline, rather than promised delivery dates or completion claims.

| Area | Current behavior | Required verification |
|---|---|---|
| Root runner | Expert callbacks return synchronous dictionaries | Supply awaitable callbacks and test selected-expert success |
| Unified engine | Calls continuity task methods absent from the manager | Align task lifecycle interfaces and test completion/failure |
| Agent call | Engine passes string/`context`; agent accepts Task/`initial_context` | Align input types and test one complete task |
| Evidence calls | Ledger append is synchronous with an event-type argument | Check all call sites and persisted record verification |
| Provider interfaces | BedrockBackend has `generate`; MultiProvider has `invoke_model` | Adapt the specific consumer/provider pair explicitly |
| HTTP agent endpoint | Uses `task_id`; Task entity defines `id` | Validate request-to-entity and response contracts |
| Tool execution | Bridge calls handlers directly | Apply schema validation, authorization, timeouts, and sandbox controls |
| HTTP exposure | Wildcard CORS; no authentication middleware | Restrict transport and implement authenticated authorization |
| Node gate | Partial script and metadata loader | Complete and test signature, expiry, release binding, and denial paths |
| Persistence | Several backends; no single established crash-recovery guarantee | Test kill/restart and resource cleanup for the chosen configuration |
| Dependencies | Full imports exceed root package metadata | Verify clean installation for each supported entrypoint |
| Formal/native sources | Separate language/toolchain requirements | Record exact build/checker commands and results |

Sources: [engine](../src/sovereign.py), [runner](../run.py), [agent](../src/agents/react.py), [continuity](../src/continuity/manager.py), [ledger](../src/core/evidence.py), [HTTP bridge](../src/bridge/http_server.py), [entities](../src/models/entities.py), and [gate](../scripts/sovereign_gate.py).

## Evidence required for a release

A release record should name the commit, dependency/toolchain versions, selected entrypoint, applicable test results, backend used, and known failures. A successful mock route is not a successful provider call. A hash seal is not a build or security review.

Start with the [validated local examples](VALIDATION.md), then add integration tests for the selected deployment path. The documentation update does not repair the implementation gaps above.
