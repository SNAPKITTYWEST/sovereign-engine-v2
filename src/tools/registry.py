"""
Universal Tool Registry with Risk Classification
Part of SOVEREIGN PYTHON LLM ENGINE

Features:
- Tool registration and discovery
- Risk classification (0-8 scale)
- Approval policy enforcement
- JSONSchema validation
- WORM ledger integration
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Awaitable
import jsonschema


# ==========================================
# Risk Classification
# ==========================================

class RiskClass(IntEnum):
    """
    Tool risk classification.

    0-2: Auto-approve (read-only, pure computation)
    3-4: User confirmation (writes with undo)
    5-6: Explicit approval (destructive operations)
    7-8: Admin-only (infrastructure, financial, legal)
    """
    PURE_COMPUTATION = 0              # Math, logic, no I/O
    READ_ONLY_LOCAL = 1               # Read local files
    READ_ONLY_REMOTE = 2              # Read web/APIs
    REVERSIBLE_LOCAL_WRITE = 3        # Write files (backups exist)
    REVERSIBLE_REMOTE_WRITE = 4       # API writes (can be undone)
    DESTRUCTIVE_LOCAL = 5             # Delete files, no undo
    DESTRUCTIVE_REMOTE = 6            # Delete remote resources
    PRIVILEGED_INFRASTRUCTURE = 7     # Deploy, config changes
    FINANCIAL_OR_LEGAL = 8            # Payments, contracts


# ==========================================
# Approval Policy
# ==========================================

class ApprovalPolicy(IntEnum):
    """
    Approval policy for tool execution.
    """
    AUTOMATIC = 0           # No approval needed
    USER_CONFIRMATION = 1   # Ask user before execution
    ADMIN_ONLY = 2         # Require admin privileges
    NEVER = 3              # Tool is disabled


# ==========================================
# Tool Definition
# ==========================================

@dataclass
class ToolDefinition:
    """
    Complete tool definition with metadata and handler.

    Fields:
        tool_id: Unique identifier (e.g., "embeddings.encode_text")
        version: Semantic version (e.g., "1.0.0")
        title: Human-readable title
        description: Tool description (used in prompts)
        input_schema: JSONSchema for input parameters
        output_schema: JSONSchema for output (optional)
        risk_class: Risk classification (0-8)
        approval_policy: Approval policy
        sandbox_required: Whether to run in sandbox
        timeout_ms: Execution timeout in milliseconds
        handler: Async function that executes the tool
        tags: Optional tags for categorization
    """
    tool_id: str
    version: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    risk_class: RiskClass
    approval_policy: ApprovalPolicy
    sandbox_required: bool
    timeout_ms: int
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
    tags: list[str] = field(default_factory=list)

    def validate_input(self, params: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate input parameters against schema.

        Args:
            params: Input parameters

        Returns:
            (is_valid, error_message) tuple
        """
        try:
            jsonschema.validate(instance=params, schema=self.input_schema)
            return True, None
        except jsonschema.ValidationError as e:
            return False, str(e)

    def validate_output(self, result: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate output against schema.

        Args:
            result: Output result

        Returns:
            (is_valid, error_message) tuple
        """
        if self.output_schema is None:
            return True, None

        try:
            jsonschema.validate(instance=result, schema=self.output_schema)
            return True, None
        except jsonschema.ValidationError as e:
            return False, str(e)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary (for serialization).

        Note: handler is excluded (not serializable)
        """
        return {
            'tool_id': self.tool_id,
            'version': self.version,
            'title': self.title,
            'description': self.description,
            'input_schema': self.input_schema,
            'output_schema': self.output_schema,
            'risk_class': self.risk_class.value,
            'approval_policy': self.approval_policy.value,
            'sandbox_required': self.sandbox_required,
            'timeout_ms': self.timeout_ms,
            'tags': self.tags
        }


# ==========================================
# Tool Registry
# ==========================================

class ToolRegistry:
    """
    Central registry for all tools.

    Features:
    - Register/unregister tools
    - Lookup by ID, namespace, risk class, tags
    - Validate tools before registration
    """

    def __init__(self):
        """Initialize empty registry"""
        self.tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """
        Register a tool.

        Args:
            tool: Tool definition

        Raises:
            ValueError: If tool_id already exists or tool is invalid
        """
        if tool.tool_id in self.tools:
            raise ValueError(f"Tool already registered: {tool.tool_id}")

        # Validate tool
        if not tool.tool_id:
            raise ValueError("tool_id cannot be empty")

        if not tool.handler:
            raise ValueError("handler is required")

        if '.' not in tool.tool_id:
            raise ValueError("tool_id must include namespace (e.g., 'embeddings.encode')")

        # Register
        self.tools[tool.tool_id] = tool

    def unregister(self, tool_id: str) -> None:
        """
        Unregister a tool.

        Args:
            tool_id: Tool identifier

        Raises:
            KeyError: If tool not found
        """
        if tool_id not in self.tools:
            raise KeyError(f"Tool not found: {tool_id}")

        del self.tools[tool_id]

    def get(self, tool_id: str) -> ToolDefinition | None:
        """
        Get tool by ID.

        Args:
            tool_id: Tool identifier

        Returns:
            ToolDefinition if found, None otherwise
        """
        return self.tools.get(tool_id)

    def has(self, tool_id: str) -> bool:
        """
        Check if tool is registered.

        Args:
            tool_id: Tool identifier

        Returns:
            True if tool exists
        """
        return tool_id in self.tools

    def list_all(self) -> list[ToolDefinition]:
        """
        List all registered tools.

        Returns:
            List of all tools
        """
        return list(self.tools.values())

    def list_by_namespace(self, namespace: str) -> list[ToolDefinition]:
        """
        List all tools in namespace.

        Args:
            namespace: Namespace (e.g., "embeddings")

        Returns:
            List of tools in namespace
        """
        prefix = f"{namespace}."
        return [
            tool for tool in self.tools.values()
            if tool.tool_id.startswith(prefix)
        ]

    def list_by_risk_class(
        self,
        max_risk: RiskClass,
        min_risk: RiskClass = RiskClass.PURE_COMPUTATION
    ) -> list[ToolDefinition]:
        """
        List tools by risk class range.

        Args:
            max_risk: Maximum risk class (inclusive)
            min_risk: Minimum risk class (inclusive)

        Returns:
            List of tools in risk range
        """
        return [
            tool for tool in self.tools.values()
            if min_risk <= tool.risk_class <= max_risk
        ]

    def list_by_tags(self, tags: list[str], match_all: bool = False) -> list[ToolDefinition]:
        """
        List tools by tags.

        Args:
            tags: Tags to filter by
            match_all: If True, tool must have all tags (AND), else any tag (OR)

        Returns:
            List of matching tools
        """
        if match_all:
            return [
                tool for tool in self.tools.values()
                if all(tag in tool.tags for tag in tags)
            ]
        else:
            return [
                tool for tool in self.tools.values()
                if any(tag in tool.tags for tag in tags)
            ]

    def list_namespaces(self) -> list[str]:
        """
        List all unique namespaces.

        Returns:
            List of namespace strings
        """
        namespaces = set()
        for tool_id in self.tools:
            namespace = tool_id.split('.')[0]
            namespaces.add(namespace)
        return sorted(namespaces)

    def search(self, query: str) -> list[ToolDefinition]:
        """
        Search tools by query string.

        Searches in tool_id, title, description, tags.

        Args:
            query: Search query

        Returns:
            List of matching tools
        """
        query_lower = query.lower()
        results = []

        for tool in self.tools.values():
            # Check tool_id
            if query_lower in tool.tool_id.lower():
                results.append(tool)
                continue

            # Check title
            if query_lower in tool.title.lower():
                results.append(tool)
                continue

            # Check description
            if query_lower in tool.description.lower():
                results.append(tool)
                continue

            # Check tags
            if any(query_lower in tag.lower() for tag in tool.tags):
                results.append(tool)
                continue

        return results

    def get_stats(self) -> dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with statistics
        """
        risk_distribution = {}
        for tool in self.tools.values():
            risk_class = tool.risk_class.name
            risk_distribution[risk_class] = risk_distribution.get(risk_class, 0) + 1

        approval_distribution = {}
        for tool in self.tools.values():
            approval_policy = tool.approval_policy.name
            approval_distribution[approval_policy] = approval_distribution.get(approval_policy, 0) + 1

        return {
            'total_tools': len(self.tools),
            'namespaces': self.list_namespaces(),
            'risk_distribution': risk_distribution,
            'approval_distribution': approval_distribution,
            'sandbox_required_count': sum(1 for t in self.tools.values() if t.sandbox_required)
        }

    def export_catalog(self) -> dict[str, Any]:
        """
        Export tool catalog (for documentation).

        Returns:
            Dictionary with all tool definitions
        """
        return {
            'version': '1.0.0',
            'tools': [tool.to_dict() for tool in self.tools.values()],
            'stats': self.get_stats()
        }


# ==========================================
# Global Registry Instance
# ==========================================

# Global registry (singleton pattern)
_global_registry: ToolRegistry | None = None


def get_global_registry() -> ToolRegistry:
    """
    Get global tool registry.

    Returns:
        Global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(tool: ToolDefinition) -> None:
    """
    Register tool in global registry.

    Args:
        tool: Tool definition
    """
    registry = get_global_registry()
    registry.register(tool)


def get_tool(tool_id: str) -> ToolDefinition | None:
    """
    Get tool from global registry.

    Args:
        tool_id: Tool identifier

    Returns:
        ToolDefinition if found, None otherwise
    """
    registry = get_global_registry()
    return registry.get(tool_id)


# ==========================================
# Tool Decorator
# ==========================================

def tool(
    tool_id: str,
    version: str = "1.0.0",
    title: str = "",
    description: str = "",
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    risk_class: RiskClass = RiskClass.PURE_COMPUTATION,
    approval_policy: ApprovalPolicy = ApprovalPolicy.AUTOMATIC,
    sandbox_required: bool = False,
    timeout_ms: int = 30000,
    tags: list[str] | None = None
):
    """
    Decorator for registering tools.

    Example:
        @tool(
            tool_id="math.add",
            description="Add two numbers",
            input_schema={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
            risk_class=RiskClass.PURE_COMPUTATION
        )
        async def add_numbers(params: dict[str, Any]) -> dict[str, Any]:
            return {"result": params["a"] + params["b"]}
    """
    def decorator(func: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]):
        tool_def = ToolDefinition(
            tool_id=tool_id,
            version=version,
            title=title or tool_id,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema,
            risk_class=risk_class,
            approval_policy=approval_policy,
            sandbox_required=sandbox_required,
            timeout_ms=timeout_ms,
            handler=func,
            tags=tags or []
        )

        register_tool(tool_def)
        return func

    return decorator
