# Tool registration and execution

[ToolRegistry](../src/tools/registry.py) stores definitions. [load_all_tools](../src/tools/loader.py) registers filesystem, code, Git, database, document, web, embedding, audio, and PyTorch tools. Individual modules can have additional dependencies; a module existing on disk does not mean its tool is registered.

## Local example: register and validate a pure tool

Requires `jsonschema`. Save as `tool_example.py` at the repository root:

```python
import asyncio
from src.tools.registry import (
    ToolRegistry, ToolDefinition, RiskClass, ApprovalPolicy,
)

async def add(params):
    return {"value": params["a"] + params["b"]}

async def main():
    registry = ToolRegistry()
    definition = ToolDefinition(
        tool_id="example.add", version="1.0.0", title="Add",
        description="Add two integers.",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"], "additionalProperties": False,
        },
        output_schema={
            "type": "object", "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
        risk_class=RiskClass.PURE_COMPUTATION,
        approval_policy=ApprovalPolicy.AUTOMATIC,
        sandbox_required=False, timeout_ms=1000, handler=add,
    )
    registry.register(definition)
    params = {"a": 2, "b": 3}
    valid, error = definition.validate_input(params)
    assert valid, error
    result = await asyncio.wait_for(definition.handler(params), timeout=1)
    valid, error = definition.validate_output(result)
    assert valid, error
    assert result == {"value": 5}
    print(result)

asyncio.run(main())
```

This example explicitly validates input/output and applies a timeout. Merely attaching schemas, approval metadata, or `timeout_ms` to a definition does not enforce them on a direct handler call.

## Inspect the installed catalog

Use `registry.list_all()`, `list_namespaces()`, `list_by_namespace(name)`, `get(tool_id)`, or `export_catalog()`. A current catalog is more useful than a frozen count of “34 tools.”

## Risk and approval

Risk classes range from 0 (pure computation) through local/remote reads, reversible writes, destructive writes, privileged infrastructure, and 8 (financial/legal). Approval policies are `AUTOMATIC`, `USER_CONFIRMATION`, `ADMIN_ONLY`, and `NEVER`.

[ApprovalEngine](../src/tools/approval.py) is separate from registration. Review the calling path to confirm it invokes the approval engine, schema validators, sandbox, and path/network controls. In particular, the HTTP bridge's `/tool/execute` handler directly invokes the registered handler; it does not provide the same checks merely because an ApprovalEngine was constructed.

## Native dispatch

[opcode_registry.py](../src/tools/opcode_registry.py) maps tools to opcodes. [ipc_router.py](../src/tools/ipc_router.py) implements native routing and fallback behavior. The C dispatcher is under [native/dispatcher/](../native/dispatcher/). Registering a Python tool does not prove a corresponding native implementation exists. See [Security](SECURITY.md) and [Machine runtime](MACHINE_CODE.md).
