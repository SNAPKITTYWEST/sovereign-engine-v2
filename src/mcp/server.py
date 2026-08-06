"""
MCP Server Implementation
Part of SOVEREIGN PYTHON LLM ENGINE

JSON-RPC 2.0 server implementing Model Context Protocol.
"""

from typing import Any, Callable
from dataclasses import dataclass
import json
import asyncio
from datetime import datetime
import uuid

from ..tools.registry import ToolRegistry, ToolDefinition
from ..tools.approval import ApprovalEngine
from ..core.evidence import WORMLedger


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 request"""
    jsonrpc: str = "2.0"
    method: str = ""
    params: dict | list | None = None
    id: str | int | None = None


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 response"""
    jsonrpc: str = "2.0"
    result: Any = None
    error: dict | None = None
    id: str | int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        response = {"jsonrpc": self.jsonrpc}

        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result

        if self.id is not None:
            response["id"] = self.id

        return response


class MCPServer:
    """
    MCP (Model Context Protocol) server.

    Implements JSON-RPC 2.0 protocol with MCP methods:
    - initialize
    - tools/list
    - tools/call
    - resources/list
    - resources/read
    - prompts/list
    - prompts/get
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        approval_engine: ApprovalEngine | None = None,
        worm_ledger: WORMLedger | None = None
    ):
        """
        Initialize MCP server.

        Args:
            tool_registry: Tool registry
            approval_engine: Optional approval engine
            worm_ledger: Optional WORM ledger
        """
        self.tool_registry = tool_registry
        self.approval_engine = approval_engine
        self.worm_ledger = worm_ledger

        self.session_id = str(uuid.uuid4())
        self.initialized = False

        # Register handlers
        self.handlers: dict[str, Callable] = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "ping": self._handle_ping,
        }

    async def handle_request(self, request_data: str) -> str:
        """
        Handle JSON-RPC request.

        Args:
            request_data: JSON string

        Returns:
            JSON response string
        """
        try:
            # Parse request
            data = json.loads(request_data)

            # Handle batch requests
            if isinstance(data, list):
                responses = []
                for item in data:
                    response = await self._process_request(item)
                    if response:
                        responses.append(response.to_dict())
                return json.dumps(responses)

            # Handle single request
            response = await self._process_request(data)
            if response:
                return json.dumps(response.to_dict())

            # Notification (no response)
            return ""

        except json.JSONDecodeError as e:
            error_response = JSONRPCResponse(
                error={
                    "code": -32700,
                    "message": "Parse error",
                    "data": str(e)
                },
                id=None
            )
            return json.dumps(error_response.to_dict())

        except Exception as e:
            error_response = JSONRPCResponse(
                error={
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                },
                id=None
            )
            return json.dumps(error_response.to_dict())

    async def _process_request(self, data: dict) -> JSONRPCResponse | None:
        """Process single request"""
        # Validate JSON-RPC structure
        if data.get("jsonrpc") != "2.0":
            return JSONRPCResponse(
                error={
                    "code": -32600,
                    "message": "Invalid Request",
                    "data": "jsonrpc must be '2.0'"
                },
                id=data.get("id")
            )

        method = data.get("method")
        if not method:
            return JSONRPCResponse(
                error={
                    "code": -32600,
                    "message": "Invalid Request",
                    "data": "method is required"
                },
                id=data.get("id")
            )

        params = data.get("params")
        request_id = data.get("id")

        # Find handler
        handler = self.handlers.get(method)
        if not handler:
            return JSONRPCResponse(
                error={
                    "code": -32601,
                    "message": "Method not found",
                    "data": f"Unknown method: {method}"
                },
                id=request_id
            )

        # Execute handler
        try:
            result = await handler(params or {})

            # Don't send response for notifications
            if request_id is None:
                return None

            return JSONRPCResponse(
                result=result,
                id=request_id
            )

        except Exception as e:
            return JSONRPCResponse(
                error={
                    "code": -32000,
                    "message": "Server error",
                    "data": str(e)
                },
                id=request_id
            )

    async def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request"""
        protocol_version = params.get("protocolVersion", "1.0.0")
        client_info = params.get("clientInfo", {})

        self.initialized = True

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "mcp_initialize",
                "session_id": self.session_id,
                "protocol_version": protocol_version,
                "client_info": client_info,
                "timestamp": datetime.utcnow().isoformat()
            })

        return {
            "protocolVersion": "1.0.0",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
                "logging": {},
            },
            "serverInfo": {
                "name": "sovereign-engine-mcp",
                "version": "1.0.0"
            }
        }

    async def _handle_tools_list(self, params: dict) -> dict:
        """Handle tools/list request"""
        if not self.initialized:
            raise Exception("Server not initialized")

        # Get all tools from registry
        tools = self.tool_registry.list_all()

        # Convert to MCP format
        mcp_tools = []
        for tool in tools:
            mcp_tools.append({
                "name": tool.tool_id,
                "description": tool.description,
                "inputSchema": tool.input_schema
            })

        return {"tools": mcp_tools}

    async def _handle_tools_call(self, params: dict) -> dict:
        """Handle tools/call request"""
        if not self.initialized:
            raise Exception("Server not initialized")

        tool_name = params.get("name")
        if not tool_name:
            raise ValueError("Tool name is required")

        arguments = params.get("arguments", {})

        # Get tool from registry
        tool = self.tool_registry.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Check approval
        if self.approval_engine:
            approved, reason = await self.approval_engine.check_approval(
                tool,
                arguments,
                actor="mcp_client"
            )

            if not approved:
                raise PermissionError(f"Tool execution denied: {reason}")

        # Execute tool
        try:
            result = await tool.handler(**arguments)

            # Log to WORM
            if self.worm_ledger:
                await self.worm_ledger.append({
                    "event": "mcp_tool_call",
                    "session_id": self.session_id,
                    "tool": tool_name,
                    "arguments": arguments,
                    "success": True,
                    "timestamp": datetime.utcnow().isoformat()
                })

            # Format response
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result)
                    }
                ]
            }

        except Exception as e:
            # Log error to WORM
            if self.worm_ledger:
                await self.worm_ledger.append({
                    "event": "mcp_tool_call_error",
                    "session_id": self.session_id,
                    "tool": tool_name,
                    "arguments": arguments,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })

            raise e

    async def _handle_resources_list(self, params: dict) -> dict:
        """Handle resources/list request"""
        if not self.initialized:
            raise Exception("Server not initialized")

        # No resources implemented yet
        return {"resources": []}

    async def _handle_resources_read(self, params: dict) -> dict:
        """Handle resources/read request"""
        if not self.initialized:
            raise Exception("Server not initialized")

        uri = params.get("uri")
        if not uri:
            raise ValueError("URI is required")

        raise NotImplementedError("Resources not implemented")

    async def _handle_prompts_list(self, params: dict) -> dict:
        """Handle prompts/list request"""
        if not self.initialized:
            raise Exception("Server not initialized")

        # No prompts implemented yet
        return {"prompts": []}

    async def _handle_prompts_get(self, params: dict) -> dict:
        """Handle prompts/get request"""
        if not self.initialized:
            raise Exception("Server not initialized")

        name = params.get("name")
        if not name:
            raise ValueError("Prompt name is required")

        raise NotImplementedError("Prompts not implemented")

    async def _handle_ping(self, params: dict) -> dict:
        """Handle ping request"""
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


class MCPToolAdapter:
    """
    Adapter to convert ToolRegistry tools to MCP format.

    Helper for servers that want to expose tools via MCP.
    """

    @staticmethod
    def tool_to_mcp(tool: ToolDefinition) -> dict:
        """
        Convert ToolDefinition to MCP tool format.

        Args:
            tool: Tool definition

        Returns:
            MCP tool dict
        """
        return {
            "name": tool.tool_id,
            "description": tool.description,
            "inputSchema": tool.input_schema
        }

    @staticmethod
    def tools_to_mcp(tools: list[ToolDefinition]) -> list[dict]:
        """Convert multiple tools to MCP format"""
        return [MCPToolAdapter.tool_to_mcp(tool) for tool in tools]
