# Engine test entry points

| File | Purpose | Dependency on external services |
|---|---|---|
| [stress_test_no_drift.py](stress_test_no_drift.py) | Repeated deterministic VM/routing operations | Inspect imports and assertions; not an LLM-quality benchmark |
| [live_routing_test.py](live_routing_test.py) | Routing/inference demonstration | Can use Bedrock or a mock fallback |
| [test_routing_trace_endpoints.py](test_routing_trace_endpoints.py) | Trace HTTP endpoint examples | Requires the relevant bridge/server setup |

The independent research-router suite is under [research/sparse-routing/tests/](../research/sparse-routing/tests/), not this directory. Its recorded 57 passing tests do not imply this directory's integration paths passed.

Use [Testing and troubleshooting](../docs/TESTING.md) for commands and [Validation](../docs/VALIDATION.md) for executed checks. A `__main__` block is an entrypoint, not automatically a self-test or proof of correct behavior.
